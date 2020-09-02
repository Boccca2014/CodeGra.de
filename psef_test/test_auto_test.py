# SPDX-License-Identifier: AGPL-3.0-only
import io
import os
import re
import sys
import copy
import json
import time
import uuid
import shutil
import socket
import getpass
import tempfile
import threading
import multiprocessing
from datetime import timedelta
from textwrap import dedent

import lxc
import flask
import pytest
import requests
import freezegun
import pytest_cov
from werkzeug.local import LocalProxy
from werkzeug.datastructures import FileStorage

import psef
import helpers
import psef.models as m
import cg_worker_pool
import requests_stubs
from helpers import get_id
from cg_dt_utils import DatetimeWithTimezone
from psef.exceptions import APICodes, APIException


@pytest.fixture(params=[False])
def poll_after_done(request):
    yield request.param


@pytest.fixture(params=[False])
def fail_wget_attach(request):
    yield request.param


@pytest.fixture
def make_failer(app, session):
    def creator(
        amount, orig, on_first_fail=lambda: False, on_fail=lambda _: False
    ):
        successes = multiprocessing.Value('i', 0)
        failures = multiprocessing.Value('i', 0)
        failed_at_least_once = False

        def failer(*args, **kwargs):
            nonlocal successes
            nonlocal failed_at_least_once
            if successes.value < amount:
                successes.value += 1
                return orig(*args, **kwargs)

            if not failed_at_least_once:
                if on_first_fail():
                    return orig(*args, **kwargs)
                failed_at_least_once = True

            if on_fail(failures.value):
                failures.value = 0
                successes.value = 1
                return orig(*args, **kwargs)

            failures.value += 1

            return False

        failer.failed_at_least_once = lambda: failed_at_least_once

        return failer

    yield creator


@pytest.fixture
def monkeypatch_for_run(
    monkeypatch, lxc_stub, stub_function_class, fail_wget_attach,
    poll_after_done
):
    old_run_command = psef.auto_test.StartedContainer._run_command

    monkeypatch.setattr(
        psef.auto_test, '_SYSTEMD_WAIT_CMD',
        ['python', '-c', 'import random; exit(random.randint(0, 1))']
    )

    import shutil
    bash_path = shutil.which('bash')
    monkeypatch.setattr(psef.auto_test, 'BASH_PATH', bash_path)

    monkeypatch.setattr(psef.auto_test, 'FIXTURES_ROOT', '/tmp')
    monkeypatch.setattr(psef.auto_test, 'OUTPUT_DIR', f'/tmp/{uuid.uuid4()}')
    monkeypatch.setattr(os, 'setgroups', stub_function_class())

    def new_run_command(self, cmd_user):
        signal_start = psef.auto_test.StartedContainer._signal_start
        cmd, user = cmd_user

        if cmd[0] in ('/bin/bash', 'bash'):
            cmd[0] = bash_path
            cmd_user = (cmd, user)

        if cmd[0] in {'adduser', 'usermod', 'deluser', 'sudo', 'apt'}:
            signal_start()
            return 0
        elif cmd[0] == bash_path and cmd[2].startswith('adduser'):
            # Don't make the user, as we cannot do that locally
            cmd[2] = '&&'.join(['whoami'] + cmd[2].split('&&')[1:-2])
            cmd_user = (cmd, user)
        elif cmd[0] == bash_path and cmd[2].startswith('mv'):
            # Don't mv as this is not automatically restored as it is in the
            # actual LXC container.
            cmd[2] = cmd[2].replace('mv', 'cp -R')
            cmd_user = (cmd, user)
        elif cmd == ['grep', '-c', getpass.getuser(), '/etc/sudoers']:
            signal_start()
            return 1
        elif '/etc/sudoers' in cmd:
            signal_start()
            return 0
        elif cmd[0] == 'wget' and fail_wget_attach:
            while True:
                time.sleep(5)

        return old_run_command(self, cmd_user)

    monkeypatch.setattr(psef.auto_test, 'CODEGRADE_USER', getpass.getuser())
    monkeypatch.setattr(
        psef.helpers, 'ensure_on_test_server', stub_function_class()
    )

    monkeypatch.setattr(
        psef.auto_test.StartedContainer, '_run_command', new_run_command
    )
    monkeypatch.setattr(lxc, 'Container', lxc_stub)
    monkeypatch.setattr(
        psef.auto_test, '_get_amount_cpus', stub_function_class(lambda: 1)
    )
    monkeypatch.setattr(
        cg_worker_pool, '_make_process',
        stub_function_class(
            lambda *args, **kwargs: threading.Thread(*args, **kwargs),
            with_args=True
        )
    )
    monkeypatch.setattr(
        psef.auto_test.AutoTestRunner, '_get_amount_of_needed_workers',
        stub_function_class(lambda: 1)
    )
    monkeypatch.setattr(
        psef.auto_test.AutoTestRunner, '_should_poll_after_done',
        stub_function_class(lambda: poll_after_done)
    )
    monkeypatch.setattr(
        psef.tasks, 'check_heartbeat_auto_test_run', stub_function_class()
    )
    monkeypatch.setattr(psef.auto_test, '_REQUEST_TIMEOUT', 0.1)

    _old_upload = psef.auto_test.AutoTestRunner._upload_output_folder

    def upload(*args, **kwargs):
        try:
            _old_upload(*args, **kwargs)
        finally:
            for f in os.listdir(psef.auto_test.OUTPUT_DIR):
                path = os.path.join(psef.auto_test.OUTPUT_DIR, f)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.unlink(path)

    monkeypatch.setattr(
        psef.auto_test.AutoTestRunner, '_upload_output_folder', upload
    )

    with tempfile.TemporaryDirectory() as upper_tmpdir:
        tmpdir = upper_tmpdir
        _run_student = psef.auto_test._run_student

        monkeypatch.setattr(
            psef.auto_test, '_get_home_dir',
            stub_function_class(lambda: tmpdir)
        )

        def next_student(*args, **kwargs):
            nonlocal tmpdir

            with tempfile.TemporaryDirectory() as tdir:
                tmpdir = tdir
                for inner in ['/student']:
                    shutil.copytree(upper_tmpdir + inner, tdir + inner)
                return _run_student(*args, **kwargs)

        monkeypatch.setattr(psef.auto_test, '_run_student', next_student)
        yield


@pytest.fixture
def monkeypatch_broker(monkeypatch, live_server_url):
    ses = requests_stubs.Session()
    raised = True
    runner_id = str(uuid.uuid4())

    def raise_next(get_ses=False):
        if get_ses:
            return ses

        nonlocal raised
        raised = False

    def raise_once(*_):
        nonlocal raised
        if raised:
            return
        raised = True
        raise requests.RequestException()

    orig_get = ses.get
    orig_post = ses.post

    def stub_post(path, *args, **kwargs):
        res = orig_post(path, *args, **kwargs)
        if re.match('/api/v1/alive/', path):
            res.json = lambda *args: {'id': runner_id}
        return res

    def stub_get(path, *args, **kwargs):
        res = orig_get(path, *args, **kwargs)
        if f'/api/v1/runners/{runner_id}/jobs/' == path:
            res.json = lambda *args: [{'url': live_server_url}]
        else:
            print(path)
        return res

    monkeypatch.setattr(ses.Response, 'raise_for_status', raise_once)
    monkeypatch.setattr(ses, 'get', stub_get)
    monkeypatch.setattr(ses, 'post', stub_post)
    monkeypatch.setattr(psef.helpers, 'BrokerSession', lambda *_: ses)
    yield raise_next


@pytest.fixture(autouse=True)
def monkeypatch_os_exec(monkeypatch):
    def flush_and_call(func):
        def inner(*args, **kwargs):
            pytest_cov.embed.cleanup()
            if args[0] == 'ping':
                os.execvp('true', ['true'])
            func(*args, **kwargs)

        return inner

    for func in ['execve', 'execvpe', 'execvp', '_exit']:
        orig = getattr(os, func)
        monkeypatch.setattr(os, func, flush_and_call(orig))
    yield


@pytest.fixture
def basic(logged_in, admin_user, test_client, session):
    with logged_in(admin_user):
        course = helpers.create_course(test_client)
        assig_id = helpers.create_assignment(
            test_client,
            course,
            deadline=DatetimeWithTimezone.utcnow() + timedelta(days=30)
        )['id']
        teacher = helpers.create_user_with_role(session, 'Teacher', [course])
        student = helpers.create_user_with_role(session, 'Student', [course])
    yield course, assig_id, teacher, student


def test_create_auto_test(test_client, basic, logged_in, describe):
    course, assig_id, teacher, student = basic

    with describe('Creating a auto test as student is not possible'
                  ), logged_in(student):
        test_client.req(
            'post',
            '/api/v1/auto_tests/',
            data={'assignment_id': assig_id},
            status_code=403,
            result=helpers.create_error_template(),
        )

    with describe('Creating a simple test'), logged_in(teacher):
        test_client.req(
            'post',
            '/api/v1/auto_tests/',
            data={'assignment_id': assig_id},
            status_code=200,
            result={
                'id': int,
                'fixtures': [],
                'setup_script': '',
                'run_setup_script': '',
                'finalize_script': '',
                'sets': [],
                'assignment_id': assig_id,
                'grade_calculation': None,
                'runs': [],
                'results_always_visible': None,
                'prefer_teacher_revision': None,
            }
        )

    with describe('Creating another test in the same assignment fails'
                  ), logged_in(teacher):
        test_client.req(
            'post',
            '/api/v1/auto_tests/',
            data={'assignment_id': assig_id},
            status_code=409,
            result=helpers.create_error_template(),
        )


def test_create_auto_test_set(basic, test_client, logged_in, describe):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(teacher):
            test = helpers.create_auto_test(test_client, assig_id, 0, 0)
            rubric = test_client.req(
                'put',
                f'/api/v1/assignments/{assig_id}/rubrics/',
                200,
                data=helpers.get_simple_rubric()
            )

        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('Students cannot create suites'), logged_in(student):
        test_client.req('post', f'{url}/sets/', 403)

        with describe('No set should be created'), logged_in(teacher):
            test_client.req('get', url, 200, result=test)

    with describe('Teacher can create sets'), logged_in(teacher):
        test_client.req('post', f'{url}/sets/', 200)

        with describe('Created sets should have correct default values'):
            test_client.req(
                'get',
                url,
                200,
                result={
                    **test,
                    'sets': [
                        *test['sets'],
                        {'id': int, 'suites': [], 'stop_points': 0}
                    ],
                }
            )


def test_create_auto_test_suite(basic, test_client, logged_in, describe):
    course, assig_id, teacher, student = basic

    with describe('setup'), logged_in(teacher):
        test = helpers.create_auto_test(test_client, assig_id, 1, 0)
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            200,
            data=helpers.get_simple_rubric()
        )
        set_id = test['sets'][0]['id']
        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('students should not be able to create suite'
                  ), logged_in(student):
        test_client.req('patch', f'{url}/sets/{set_id}/suites/', 403)
        with describe('No suite should be created'), logged_in(teacher):
            test_client.req('get', url, 200, result=test)

    with describe('teachers should be able to create empty suites'
                  ), logged_in(teacher):
        test_client.req(
            'patch',
            f'{url}/sets/{set_id}/suites/',
            200,
            data={
                'steps': [],
                'rubric_row_id': rubric[0]['id'],
                'network_disabled': False,
                'submission_info': False,
            }
        )

        test_client.req(
            'get',
            url,
            200,
            {
                **test,
                'sets': [{
                    **test['sets'][0],
                    'suites': [{
                        'id': int,
                        'rubric_row': {**rubric[0], 'locked': 'auto_test'},
                        'network_disabled': False,
                        'submission_info': False,
                        'steps': [],
                        # This is set in the conftest.py
                        'command_time_limit': 3,
                    }],
                }]
            }
        )

    with describe('rubric rows cannot be connected to two suites'
                  ), logged_in(teacher):
        test_client.req(
            'patch',
            f'{url}/sets/{set_id}/suites/',
            409,
            data={
                'steps': [],
                'rubric_row_id': rubric[0]['id'],
                'network_disabled': False,
                'submission_info': False,
            }
        )


def test_delete_auto_test(basic, test_client, logged_in, describe):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(teacher):
            test = helpers.create_auto_test(test_client, assig_id)
        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('Students cannot delete auto tests'):
        with logged_in(student):
            test_client.req('delete', url, 403)
        with logged_in(teacher):
            test_client.req('get', url, 200, result=test)

    with describe('Teachers can delete auto tests'), logged_in(teacher):
        test_client.req('delete', url, 204)
        test_client.req('get', url, 404)


def test_view_auto_test(basic, test_client, logged_in, describe):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(teacher):
            test = helpers.create_auto_test(test_client, assig_id)
        url = f'/api/v1/auto_tests/{test["id"]}'

        def update_state(state):
            with logged_in(teacher):
                test_client.req(
                    'patch',
                    f'/api/v1/assignments/{assig_id}',
                    200,
                    data={'state': state}
                )

        update_state('open')

    with describe('Students cannot see auto test before deadline'
                  ), logged_in(student):
        test_client.req('get', url, 403)
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}',
            200,
            result={
                '__allow_extra__': True,
                # You are allowed to see the id.
                'auto_test_id': test['id'],
            }
        )

    with describe('Students can se auto test after deadline'):
        update_state('done')

        with logged_in(student):
            test_client.req('get', url, 200, result=test)
            test_client.req(
                'get',
                f'/api/v1/assignments/{assig_id}',
                200,
                result={
                    '__allow_extra__': True,
                    'auto_test_id': test['id'],
                }
            )


def test_start_auto_test_before_complete(
    basic, test_client, logged_in, describe, session, monkeypatch_celery,
    monkeypatch_broker
):
    test = url = None

    def update_test(**new_data):
        nonlocal test, url
        res = rv = None

        if new_data:
            res, rv = test_client.req(
                'patch',
                url,
                new_data.pop('error', 200),
                data=new_data,
                include_response=True,
            )

        with logged_in(teacher):
            old_test = test
            test = test_client.req('get', url, 200)
            assert test['id'] == old_test['id']

        return res, rv

    def start_run(error):
        return test_client.req('post', f'{url}/runs/', error)

    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(teacher):
            test = helpers.create_auto_test(
                test_client,
                assig_id,
                amount_sets=2,
                amount_suites=2,
                grade_calculation=None,
            )
            url = f'/api/v1/auto_tests/{test["id"]}'
            update_test()

    with describe('no grade calculator'), logged_in(teacher):
        err = start_run(409)
        assert 'no grade_calculation' in err['message']
        update_test(grade_calculation='full')

    with describe('no results always visible setting'), logged_in(teacher):
        err = start_run(409)
        assert 'a results_always_visible set' in err['message']
        update_test(results_always_visible=True)

    with describe('no preferred revision'), logged_in(teacher):
        err = start_run(409)
        assert 'not have prefer_teacher_revision set' in err['message']
        update_test(prefer_teacher_revision=False)

    with describe('already has a run'), logged_in(teacher):
        start_run(200)
        err = start_run(409)
        assert 'which has runs' in err['message']
        t = m.AutoTest.query.get(test['id'])
        t.runs = []
        session.commit()

    with describe('weight of zero'), logged_in(teacher):
        suite = next(t.all_suites)
        for step in suite.steps:
            step.weight = 0
        session.commit()
        err = start_run(409)
        assert 'has zero amount of points' in err['message']

        suite.steps[0].weight = 1
        session.commit()

    with describe('no steps in some suites'), logged_in(teacher):
        suite.steps = []
        session.commit()
        err = start_run(409)
        assert 'has no steps in some suites' in err['message']

    with describe('no suites'), logged_in(teacher):
        for s in t.sets:
            s.suites = []
        session.commit()
        err = start_run(409)
        assert 'has no suites' in err['message']

    with describe('no sets'), logged_in(teacher):
        t.sets = []
        session.commit()
        err = start_run(409)
        assert 'has no sets' in err['message']


def test_update_auto_test(
    basic, test_client, logged_in, describe, assert_similar, app, session
):
    test = url = None

    def update_test(**new_data):
        nonlocal test, url
        res = rv = None

        if new_data:
            data = {}
            for key in list(new_data.keys()):
                if key.startswith('fixture') and key != 'fixtures':
                    data[key] = new_data.pop(key)
            data['json'] = (
                io.BytesIO(
                    json.dumps(
                        {**test, **new_data, 'has_new_fixtures': bool(data)}
                    ).encode()
                ), 'json'
            )

            res, rv = test_client.req(
                'patch',
                url,
                new_data.pop('error', 200),
                real_data=data,
                include_response=True,
            )

        with logged_in(teacher):
            old_test = test
            test = test_client.req('get', url, 200)
            assert test['id'] == old_test['id']

        return res, rv

    with describe('setup'):
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            # We need to make a submission, otherwise we cannot start tests
            helpers.create_submission(test_client, assig_id)

            test = helpers.create_auto_test(test_client, assig_id)
            url = f'/api/v1/auto_tests/{test["id"]}'
            update_test()

    with describe('students cannot update'), logged_in(student):
        update_test(error=403)

    with describe('update grade calculation'), logged_in(teacher):
        assert test['grade_calculation'] is None
        update_test(grade_calculation='not valid', error=404)
        assert test['grade_calculation'] is None
        update_test(grade_calculation='full')
        assert test['grade_calculation'] == 'full'
        update_test(grade_calculation='partial')

    with describe('update setup script'), logged_in(teacher):
        new_script = uuid.uuid4().hex
        update_test(setup_script=new_script)
        assert test['setup_script'] == new_script
        update_test(setup_script='')
        assert test['setup_script'] == ''

    with describe('run setup script'), logged_in(teacher):
        new_script = uuid.uuid4().hex
        update_test(run_setup_script=new_script)
        assert test['run_setup_script'] == new_script
        update_test(run_setup_script='')
        assert test['run_setup_script'] == ''

    with describe('add fixtures'), logged_in(teacher):
        update_test(fixture1=(io.BytesIO(b'hello'), 'file1'))
        fixture, = test['fixtures']
        assert_similar(fixture, {'hidden': True, 'id': str, 'name': 'file1'})

        res = test_client.get(f'{url}/fixtures/{fixture["id"]}')
        assert res.status_code == 200
        assert res.get_data(as_text=True) == 'hello'

        with logged_in(student):
            # Fixture is hidden so student may not see it
            res = test_client.get(f'{url}/fixtures/{fixture["id"]}')
            assert res.status_code == 403

        test_client.req('delete', f'{url}/fixtures/{fixture["id"]}/hide', 204)

        with logged_in(student):
            # Fixture is not hidden, but the student cannot see the AutoTest
            # yet.
            res = test_client.get(f'{url}/fixtures/{fixture["id"]}')
            assert res.status_code == 403

        update_test(results_always_visible=True)
        update_test(prefer_teacher_revision=False)
        t = m.AutoTest.query.get(test['id'])
        with app.test_request_context('/'):
            t.start_test_run()

        with logged_in(student):
            # Fixture is not hidden anymore so student may see it
            res = test_client.get(f'{url}/fixtures/{fixture["id"]}')
            assert res.status_code == 200
            test_client.req(
                'get',
                url,
                200,
                result={
                    '__allow_extra__': True,
                    'fixtures': [dict],
                }
            )

        t._runs = []
        session.commit()
        test_client.req('post', f'{url}/fixtures/{fixture["id"]}/hide', 204)
        with app.test_request_context('/'):
            t.start_test_run()

        with logged_in(student):
            # Fixture is hidden so it should not be send
            assert res.status_code == 200
            test_client.req(
                'get',
                url,
                200,
                result={
                    '__allow_extra__': True,
                    'fixtures': [],
                }
            )

        t._runs = []
        session.commit()

        update_test(fixtures=[])
        assert test['fixtures'] == []

    with describe('upload same fixture twice'), logged_in(teacher):
        update_test(fixture1=(io.BytesIO(b'hello1'), 'file2'))
        _, rv = update_test(fixture1=(io.BytesIO(b'hello2'), 'file2'))
        assert 'Warning' in rv.headers
        assert 'were renamed' in rv.headers['Warning']

        fixture1, fixture2 = test['fixtures']
        assert_similar(
            test['fixtures'],
            [{'hidden': True, 'id': str, 'name': 'file2'},
             {'hidden': True, 'id': str, 'name': 'file2 (1)'}]
        )

        res = test_client.get(f'{url}/fixtures/{fixture1["id"]}')
        assert res.get_data(as_text=True) == 'hello1'

        res = test_client.get(f'{url}/fixtures/{fixture2["id"]}')
        assert res.get_data(as_text=True) == 'hello2'

    with describe('cannot update when there are runs'), logged_in(teacher):
        update_test(error=200)
        t = m.AutoTest.query.get(test['id'])
        with app.test_request_context('/'):
            t.start_test_run()
        update_test(error=409)


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
def test_run_auto_test(
    monkeypatch_celery, monkeypatch_broker, basic, test_client, logged_in,
    describe, live_server, lxc_stub, monkeypatch, app, session, assert_similar,
    monkeypatch_for_run, make_function_spy, stub_function_class
):
    with describe('setup'):
        course, assig_id, teacher, student1 = basic
        student2 = helpers.create_user_with_role(session, 'Student', [course])
        adjust_spy = make_function_spy(psef.tasks, 'adjust_amount_runners')

        with logged_in(teacher):
            test = helpers.create_auto_test(
                test_client,
                assig_id,
                amount_sets=2,
                amount_suites=2,
                amount_fixtures=1,
                stop_points=[0.5, None],
                grade_calculation='partial',
            )
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig_id}',
                200,
                data={'state': 'open'}
            )
        url = f'/api/v1/auto_tests/{test["id"]}'

        with logged_in(student1):
            work1_old = helpers.create_submission(test_client, assig_id)

        with logged_in(student2):
            prog = """
            import sys
            if len(sys.argv) > 1:
                print("hello {}!".format(sys.argv[1]))
            else:
                print("hello stranger!")
            """
            work2 = helpers.create_submission(
                test_client,
                assig_id,
                submission_data=(io.BytesIO(dedent(prog).encode()), 'test.py')
            )

    with describe('start_auto_test'):
        t = m.AutoTest.query.get(test['id'])
        with logged_in(teacher):
            test_client.req(
                'post',
                f'{url}/runs/',
                200,
                data={
                    'continuous_feedback_run': False,
                }
            )
            session.commit()
        run = t.run

        with logged_in(student1):
            work1 = helpers.create_submission(test_client, assig_id)
            with logged_in(teacher):
                test_client.req(
                    'patch',
                    f'/api/v1/submissions/{work1["id"]}',
                    200,
                    data={'grade': 5.0}
                )

        assert session.query(
            m.AutoTestResult
        ).filter_by(work_id=work1_old['id']).one().state.name == 'skipped'

        res1 = LocalProxy(
            lambda: session.query(m.AutoTestResult).
            filter_by(work_id=work1['id']).one().id
        )
        res2 = LocalProxy(
            lambda: session.query(m.AutoTestResult).
            filter_by(work_id=work2['id']).one().id
        )

        with logged_in(teacher):
            test_client.req(
                'get',
                f'{url}/runs/{run.id}/results/{res2}',
                200,
                result={
                    'approx_waiting_before': 0,
                    '__allow_extra__': True,
                }
            )
            test_client.req(
                'get',
                f'{url}/runs/{run.id}/results/{res1}',
                200,
                result={
                    'approx_waiting_before': 1,
                    '__allow_extra__': True,
                }
            )

        monkeypatch_broker()
        live_server_url, stop_server = live_server(get_stop=True)
        with logged_in(teacher, yield_token=True) as token:
            response = requests.get(
                f'{live_server_url}{url}/runs/{run.id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            response.raise_for_status()

        thread = threading.Thread(
            target=psef.auto_test.start_polling, args=(app.config, )
        )
        thread.start()
        thread.join()

        with logged_in(teacher, yield_token=True) as token:
            response = requests.get(
                f'{live_server_url}{url}/runs/{run.id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            response.raise_for_status()
            assert_similar(
                response.json(),
                {
                    'id': run.id,
                    'created_at': str,
                    'state': 'running',  # This is always running
                    'results': [object, object, object],
                    'setup_stderr': str,
                    'setup_stdout': str,
                    'is_continuous': False,
                }
            )

            # Latest only show the latest results
            assert_similar(
                requests.get(
                    f'{live_server_url}{url}/runs/{run.id}?latest_only',
                    headers={'Authorization': f'Bearer {token}'}
                ).json(), {
                    'results': [object, object],
                    '__allow_extra__': True,
                }
            )

        with logged_in(student1):
            # A student cannot see results before the assignment is done
            test_client.req('get', f'{url}/runs/{run.id}/results/{res1}', 403)
            run.auto_test.results_always_visible = True
            # Can see if results are always visible
            session.commit()
            assert not any(
                s['auto_test_step']['hidden'] for s in test_client.req(
                    'get', f'{url}/runs/{run.id}/results/{res1}', 200
                )['step_results']
            )

            # Can get all results of own runs
            test_client.req(
                'get',
                f'{url}/runs/{run.id}/users/{student1.id}/results/',
                200,
                result=[
                    {'__allow_extra__': True, 'work_id': work1_old['id']},
                    {'__allow_extra__': True, 'work_id': work1['id']},
                ]
            )

            # Cannot get results of other user
            test_client.req(
                'get',
                f'{url}/runs/{run.id}/users/{student2.id}/results/',
                200,
                result=[]
            )

            run.auto_test.results_always_visible = False
            session.commit()

            # Can no longer see our results
            test_client.req(
                'get',
                f'{url}/runs/{run.id}/users/{student1.id}/results/',
                403,
            )

        with logged_in(teacher):
            # A teacher can see the results before done
            test_client.req('get', f'{url}/runs/{run.id}/results/{res1}', 200)
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig_id}',
                200,
                data={'state': 'done'}
            )

        with logged_in(student1):
            # A student cannot see the results of another student
            test_client.req('get', f'{url}/runs/{run.id}/results/{res2}', 403)

            # You should be able to see your own results
            res = test_client.req(
                'get',
                f'{url}/runs/{run.id}/results/{res1}',
                200,
                result={
                    'id': int, 'points_achieved': 0, '__allow_extra__': True
                }
            )
            # There should be only two results as all other tests should be
            # skipped
            len(res['step_results']) == 2
            test_client.req(
                'get',
                f'/api/v1/submissions/{work1["id"]}',
                200,
                result={
                    '__allow_extra__': True,
                    'grade': 5.0,
                    'grade_overridden': True,
                }
            )

        with logged_in(student2):
            # We can only see our own result
            test_client.req(
                'get',
                f'{url}/runs/{run.id}',
                200,
                result={
                    '__allow_extra__': True, 'results': [{
                        '__allow_extra__': True,
                        'id': res2,
                    }]
                }
            )

            # You should be able to see your own results
            res = test_client.req(
                'get',
                f'{url}/runs/{run.id}/results/{res2}',
                200,
                result={
                    # The last two run programs should time out, so 2 * 3 + 2 *
                    # (3 - 1) = 10 points achieved
                    'id': int,
                    'points_achieved': 10,
                    'step_results': list,
                    '__allow_extra__': True,
                }
            )

            # Nothing should be skipped, so all steps added
            len(res['step_results']) == 4 * 2 * 2
            test_client.req(
                'get',
                f'/api/v1/submissions/{work2["id"]}',
                200,
                result={
                    '__allow_extra__': True,
                    'grade': 10.0,
                }
            )

            # Now you should not be able to see step details anymore
            for step in m.AutoTestStepBase.query:
                step.hidden = True
            session.commit()

            old_step_results = res['step_results']
            res = test_client.req(
                'get', f'{url}/runs/{run.id}/results/{res2}', 200
            )

            for step_res1, step_res2 in zip(
                res['step_results'], old_step_results
            ):
                assert step_res1['id'] == step_res2['id']

                assert step_res1['auto_test_step']['hidden']
                assert not step_res2['auto_test_step']['hidden']

                if step_res1['achieved_points']:
                    assert step_res1['log'] != step_res2['log']
                else:
                    # IO tests do have the steps key.
                    assert (
                        step_res1['log'] == {} or
                        step_res1['log'] == {'steps': []}
                    )

    with describe('getting wrong result'), logged_in(student2):
        with describe('cannot get with wrong test id'):
            wrong_url = '/api/v1/auto_tests/404'
            res = test_client.req(
                'get', f'{wrong_url}/runs/{run.id}/results/{res2}', 404
            )
        with describe('cannot get with wrong run id'):
            res = test_client.req('get', f'{url}/runs/404/results/{res2}', 404)
        with describe('cannot get with deleted work'):
            session.query(m.AutoTestResult).get(int(res2)).work.deleted = True
            session.commit()
            res = test_client.req(
                'get', f'{url}/runs/{run.id}/results/{res2}', 404
            )
            session.query(m.AutoTestResult).get(int(res2)).work.deleted = False
            session.commit()

    with describe('restarting result'), logged_in(teacher):
        assert session.query(m.AutoTestResult).get(int(res2)).is_finished
        test_client.req(
            'post', f'{url}/runs/{run.id}/results/{res2}/restart', 200
        )
        assert adjust_spy.called_amount == 1
        result = session.query(m.AutoTestResult).get(int(res2))
        assert result.state == m.AutoTestStepResultState.not_started

        # Can also restart the result while it is running
        result.state = m.AutoTestStepResultState.running
        result.runner = m.AutoTestRunner.query.first()
        session.commit()

        stop_runners = stub_function_class()
        with monkeypatch.context() as m_context:
            m_context.setattr(m.AutoTestRun, 'stop_runners', stop_runners)
            test_client.req(
                'post', f'{url}/runs/{run.id}/results/{res2}/restart', 200
            )
        result = session.query(m.AutoTestResult).get(int(res2))
        assert result.state == m.AutoTestStepResultState.not_started
        assert stop_runners.called_amount == 1

    with describe('delete result'):
        with logged_in(student1):
            test_client.req('delete', f'{url}/runs/{run.id}', 403)
        with logged_in(teacher):
            test_client.req('delete', f'{url}/runs/{run.id}', 204)
            test_client.req('get', f'{url}/runs/{run.id}', 404)
            test_client.req(
                'get',
                f'/api/v1/submissions/{work2["id"]}',
                200,
                result={
                    '__allow_extra__': True,
                    'grade': None,
                }
            )


def test_update_auto_test_set(basic, test_client, logged_in, describe):
    test = set_id = suite_url = suite = url = None

    def update_test():
        with logged_in(teacher):
            nonlocal test, set_id, suite, suite_url, url
            old_test = test
            test = test_client.req('get', url, 200)
            assert test['id'] == old_test['id']

            set_id = test['sets'][0]['id']
            assert old_test['sets'][0]['id'] == set_id

            suite = test['sets'][0]['suites'][0]
            suite_url = f'{url}/sets/{set_id}/suites/'

    def update_suite(**new_data):
        test_client.req(
            'patch',
            suite_url,
            new_data.pop('error', 200),
            data={
                **suite,
                'rubric_row_id': suite['rubric_row']['id'],
                **new_data,
            }
        )
        update_test()

    def update_set(**new_data):
        test_client.req(
            'patch',
            f'{url}/sets/{set_id}',
            new_data.pop('error', 200),
            data={
                **test['sets'][0],
                **new_data,
            }
        )
        update_test()

    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(teacher):
            test = helpers.create_auto_test(test_client, assig_id)
            url = f'/api/v1/auto_tests/{test["id"]}'
            update_test()

    with describe('update stop points'), logged_in(teacher):
        update_set(stop_points=-1, error=400)
        update_set(stop_points=23, error=400)
        update_set(stop_points=0.5)
        assert test['sets'][0]['stop_points'] == 0.5

    with describe('Suite internet can be enabled and disabled'
                  ), logged_in(teacher):
        update_suite(network_disabled=False)
        assert suite['network_disabled'] is False

        update_suite(network_disabled=True)
        assert suite['network_disabled'] is True

    with describe('Suite submission info can be enabled and disabled'
                  ), logged_in(teacher):
        update_suite(submission_info=True)
        assert suite['submission_info'] is True

        update_suite(submission_info=False)
        assert suite['submission_info'] is False

    with describe('Remove steps'), logged_in(teacher):
        assert suite['steps']
        update_suite(steps=[])
        assert suite['steps'] == []

    with describe('Add new step'), logged_in(teacher):
        update_suite(steps=[helpers.get_auto_test_run_program_step()])
        assert suite['steps'][0]['type'] == 'run_program'
        assert isinstance(suite['steps'][0]['id'], int)

    with describe('Unknown step types result in a 404'), logged_in(teacher):
        old_steps = suite['steps']
        update_suite(
            steps=[{**helpers.get_auto_test_io_step(), 'type': 'UNKOWN'}],
            error=400,
        )
        assert suite['steps'] == old_steps

    with describe('Cannot change the type of a step'), logged_in(teacher):
        old_steps = suite['steps']
        update_suite(steps=[{**old_steps[0], 'type': 'io_test'}], error=404)
        assert suite['steps'] == old_steps

    with describe('Cannot set the time limit to < 1'), logged_in(teacher):
        update_suite(command_time_limit=2, error=200)
        assert suite['command_time_limit'] == 2
        update_suite(command_time_limit=0.5, error=400)
        assert suite['command_time_limit'] == 2
        update_suite(command_time_limit=-1, error=400)
        assert suite['command_time_limit'] == 2
        update_suite(command_time_limit=20, error=200)
        assert suite['command_time_limit'] == 20

    with describe('delete suite'), logged_in(teacher):
        test_client.req('delete', f'{suite_url}{suite["id"]}', 204)
        test_client.req(
            'get',
            url,
            200,
            result={
                'sets': [{'__allow_extra__': True, 'suites': []}],
                '__allow_extra__': True,
            }
        )

    with describe('delete set'), logged_in(teacher):
        test_client.req('delete', f'{url}/sets/{set_id}', 204)
        test_client.req(
            'get', url, 200, result={'sets': [], '__allow_extra__': True}
        )


def test_internal_api_auth(test_client, app, describe, session):
    with describe('setup'):
        ipaddr = object()
        other_ipaddr = object()
        run = m.AutoTestRun()
        runner = m.AutoTestRunner(_ipaddr=ipaddr, run=run, id=uuid.uuid4())
        assert runner.id

        verify_runner = psef.v_internal.auto_tests._verify_and_get_runner

    with describe('Without correct global password'):
        test_client.req(
            'get',
            '/api/v-internal/auto_tests/',
            401,
            headers={'CG-Internal-Api-Password': 'INVALID!'}
        )

    with describe('no runner to verify_runner'):
        with pytest.raises(psef.exceptions.PermissionException):
            verify_runner(None, ('', False))

    with describe('wrong password to any verify_runner'):
        with pytest.raises(psef.exceptions.PermissionException):
            verify_runner(run, ('', False))

        with pytest.raises(psef.exceptions.PermissionException):
            verify_runner(run, ('Not correct', False))

    with app.test_request_context(
        '/', environ_base={'REMOTE_ADDR': other_ipaddr}
    ):
        with describe('Wrong ip address'):
            with pytest.raises(psef.exceptions.PermissionException):
                verify_runner(run, (str(runner.id), True))

            # It should work when verification is turned off
            assert runner == verify_runner(run, (str(runner.id), False))

            runner._ipaddr = other_ipaddr

            # It should work when ip is correct
            assert runner == verify_runner(run, (str(runner.id), True))

        with describe('no run should not work'):
            runner.run = None
            with pytest.raises(psef.exceptions.PermissionException):
                verify_runner(run, (str(runner.id), True))


def test_update_locked_rubric(
    session, basic, test_client, logged_in, describe, app
):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        rubric_data = helpers.get_simple_rubric()
        with logged_in(teacher):
            rubric = test_client.req(
                'put',
                f'/api/v1/assignments/{assig_id}/rubrics/',
                200,
                data=rubric_data
            )
            items = [
                row.items[0].id
                for row in m.RubricRow.query.filter_by(assignment_id=assig_id)
            ]

            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig_id}',
                200,
                data={'state': 'open'}
            )

        with logged_in(student):
            work = helpers.create_submission(test_client, assig_id)

    with describe('can update non locked rubric rows'):
        with logged_in(teacher):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work["id"]}/rubricitems/',
                200,
                data={'items': items}
            )

    with describe('cannot update locked rubric rows'):
        with logged_in(teacher):
            test_id = helpers.create_auto_test(
                test_client, assig_id, 0, 0, grade_calculation='full'
            )['id']
            set_id = test_client.req(
                'post', f'/api/v1/auto_tests/{test_id}/sets/', 200
            )['id']
            _, res = test_client.req(
                'patch',
                f'/api/v1/auto_tests/{test_id}/sets/{set_id}/suites/',
                200,
                data={
                    'steps': [helpers.get_auto_test_io_step()],
                    'rubric_row_id': rubric[0]['id'],
                    'network_disabled': True,
                    'submission_info': False,
                },
                include_response=True,
            )
            assert 'Warning' in res.headers

            # This does not fail as we post the same item
            server_items = test_client.req(
                'patch',
                f'/api/v1/submissions/{work["id"]}/rubricitems/',
                200,
                data={'items': items}
            )['rubric_result']['selected']

            items = [
                row.items[1].id
                for row in m.RubricRow.query.filter_by(assignment_id=assig_id)
            ]
            # This does not work as the item has changed
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work["id"]}/rubricitems/',
                400,
                data={'items': items}
            )

            # We cannot unselect the items either.
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work["id"]}/rubricitems/',
                400,
                data={'items': []}
            )

            # We can use the copy_locked_items function
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work["id"]}/rubricitems/?copy_locked_items',
                200,
                data={'items': []},
                result={
                    '__allow_extra__': True, 'rubric_result': {
                        '__allow_extra__': True,
                        'selected': server_items,
                    }
                }
            )

            # Cannot give items and use copy_locked_items
            err = test_client.req(
                'patch',
                f'/api/v1/submissions/{work["id"]}/rubricitems/?copy_locked_items',
                400,
                data={'items': items}
            )
            assert 'You cannot specify locked rows' in err['message']

    with describe('cannot delete locked rubric rows'), logged_in(teacher):
        res = test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            400,
            data={'rows': []}
        )
        assert 'cannot delete a locked' in res['message']

    with describe('cannot delete a rubric with locked rows'
                  ), logged_in(teacher):
        res = test_client.req(
            'delete',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            409,
        )
        assert 'cannot delete a rubric with locked' in res['message']

    with describe('cannot delete items from locked rubric row after run'
                  ), logged_in(teacher):
        rubric_data = {'rows': rubric}
        old_rubric_data = copy.deepcopy(rubric_data)
        rubric_data['rows'][0]['items'].pop()
        # Before should work
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            200,
            data=rubric_data
        )
        with app.test_request_context('/non_existing', {}):
            assig = m.Assignment.query.get(assig_id)
            assig.auto_test.start_test_run()
            session.commit()
        err = test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            400,
            data=old_rubric_data
        )
        assert 'No items can be added or deleted' in err['message']


def test_hidden_steps(describe, test_client, logged_in, session, basic):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(teacher):
            test = helpers.create_auto_test(test_client, assig_id)
            for step in m.AutoTestStepBase.query:
                step.hidden = True
            session.commit()

            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig_id}',
                200,
                data={'state': 'done'}
            )

        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('student cannot see hidden test'):
        with logged_in(student):
            step = {
                'id': int,
                'name': str,
                'type': str,
                'weight': float,
                'hidden': True,
                'data': {'?inputs?': list},
            }
            test_client.req(
                'get',
                url,
                200,
                result={
                    '__allow_extra__': True,
                    'sets': [{
                        '__allow_extra__': True,
                        'suites': [{
                            '__allow_extra__': True, 'steps': [step] * 4
                        }],
                    }],
                }
            )


def test_get_runs_internal_api(
    test_client, describe, app, session, basic, logged_in
):
    with describe('Get runs without password'):
        test_client.req('get', '/api/v-internal/auto_tests/', 400)

    with describe('Get runs when there are no runs'):
        test_client.req(
            'get',
            '/api/v-internal/auto_tests/?get=tests_to_run',
            204,
            headers={
                'CG-Internal-Api-Password': app.config['AUTO_TEST_PASSWORD']
            }
        )

    with describe('setup'):
        run = m.AutoTestRun(
            started_date=None, auto_test=m.AutoTest(), batch_run_done=False
        )
        session.add(run)
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            test = helpers.create_auto_test(test_client, assig_id)
        run = m.AutoTestRun(
            started_date=None,
            auto_test_id=test['id'],
            batch_run_done=False,
        )
        session.commit()

    with describe('With runs but with failing broker'):
        test_client.req(
            'get',
            '/api/v-internal/auto_tests/?get=tests_to_run',
            204,
            headers={
                'CG-Internal-Api-Password': app.config['AUTO_TEST_PASSWORD']
            }
        )


def test_getting_fixture_no_permission(
    describe, basic, logged_in, test_client, session, app
):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(teacher):
            test = helpers.create_auto_test(
                test_client,
                assig_id,
                amount_sets=2,
                amount_suites=2,
                amount_fixtures=1,
                stop_points=[0.5, None],
                grade_calculation='partial',
            )

            session.commit()

    fixture = m.AutoTestFixture.query.first()
    test_client.req(
        'get',
        '/api/v-internal/auto_tests/{}/fixtures/{}'.format(
            fixture.auto_test_id, fixture.id
        ),
        403,
        headers={'CG-Internal-Api-Password': app.config['AUTO_TEST_PASSWORD']}
    )


def test_run_command_too_much_output(
    describe, monkeypatch_for_run, app, monkeypatch, stub_function_class
):
    monkeypatch.setitem(app.config, 'AUTO_TEST_MAX_OUTPUT_TAIL', 64)
    monkeypatch.setitem(app.config, 'AUTO_TEST_OUTPUT_LIMIT', 128)
    cmd = 'echo -n "' + 'a' * 128 + 'b' * 128 + 'c' * 32 + '"'
    with tempfile.TemporaryDirectory(
    ) as tmpdir, psef.auto_test._get_base_container(
        app.config
    ).started_container() as cont:
        os.mkdir(os.path.join(tmpdir, 'student'))

        monkeypatch.setattr(
            psef.auto_test, '_get_home_dir',
            stub_function_class(lambda: tmpdir)
        )
        with describe('without capturing extra output'):
            res = cont.run_student_command(cmd, 6)
            assert res.exit_code == 0
            assert res.stdout == 'a' * 128 + ' <OUTPUT TRUNCATED>\n'
            assert res.stderr == ''
            assert list(res.stdout_tail.data) == []

        with describe('with capturing extra output'):
            res = cont.run_student_command(cmd, 6, keep_stdout_tail=True)
            assert res.exit_code == 0
            assert res.stdout == 'a' * 128 + ' <OUTPUT TRUNCATED>\n'
            assert res.stderr == ''
            assert bytes(res.stdout_tail.data
                         ).decode() == ('b' * 32 + 'c' * 32)


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
def test_ensure_from_latest_work(session, describe, assignment_real_works):
    with describe('setup'):
        assignment, submission = assignment_real_works
        sub2_id = m.Work.query.filter_by(assignment_id=assignment.id).filter(
            m.Work.id != submission['id']
        ).first().id
        new_work = m.Work(
            user_id=submission['user']['id'], assignment_id=assignment.id
        )
        session.add(new_work)
        session.commit()

        test = m.AutoTest(
            setup_script='', run_setup_script='', assignment=assignment
        )
        run = m.AutoTestRun(
            _job_id=uuid.uuid4(),
            auto_test=test,
            batch_run_done=True,
        )
        oldest = m.AutoTestResult(work_id=submission['id'], final_result=True)
        latest2 = m.AutoTestResult(work_id=sub2_id, final_result=True)
        run.results = [latest2, oldest]
        session.commit()
        latest = m.AutoTestResult(work_id=new_work.id, final_result=True)
        run.results.append(latest)
        session.commit()

    with describe('should work with latest'):
        psef.v_internal.auto_tests._ensure_from_latest_work(latest)
        psef.v_internal.auto_tests._ensure_from_latest_work(latest2)

    with describe('should raise for non latest submission'):
        with pytest.raises(APIException) as err:
            psef.v_internal.auto_tests._ensure_from_latest_work(oldest)
        assert err.value.api_code == APICodes.NOT_NEWEST_SUBMSSION


def test_clearing_already_started_result(
    describe, basic, logged_in, test_client, session, app, monkeypatch,
    stub_function_class, monkeypatch_celery
):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(teacher):
            test = m.AutoTest.query.get(
                helpers.create_auto_test(
                    test_client,
                    assig_id,
                    amount_sets=2,
                    amount_suites=2,
                    amount_fixtures=1,
                    stop_points=[0.5, None],
                    grade_calculation='partial',
                )['id']
            )

            run = m.AutoTestRun(auto_test=test, batch_run_done=True)
            run.runners_requested = 1
            session.add(run)

            session.commit()

            stub_update = stub_function_class()
            monkeypatch.setattr(
                psef.tasks, 'update_latest_results_in_broker', stub_update
            )

            stub_adjust = stub_function_class()
            monkeypatch.setattr(
                psef.tasks, 'adjust_amount_runners', stub_adjust
            )

            with logged_in(teacher):
                sub_id = helpers.create_submission(test_client, assig_id)['id']
                assert stub_adjust.called
                assert not stub_update.called

            result = LocalProxy(
                lambda: m.AutoTestResult.query.filter_by(work_id=sub_id).one()
            )
            assert result.state.name == 'not_started'

            runner = m.AutoTestRunner(_ipaddr='localhost', run=run)
            session.commit()

            stub_clear = stub_function_class(result.clear)
            monkeypatch.setattr(m.AutoTestResult, 'clear', stub_clear)

    with describe('updating to started state'):
        test_client.req(
            'patch',
            f'/api/v-internal/auto_tests/{test.id}/results/{result.id}',
            200,
            data={
                'state': m.AutoTestStepResultState.running.name,
                'setup_stdout': 'HELLO'
            },
            headers={
                'CG-Internal-Api-Password': app.config['AUTO_TEST_PASSWORD'],
                'CG-Internal-Api-Runner-Password': str(runner.id)
            },
            environ_base={'REMOTE_ADDR': 'localhost'}
        )
        assert result.state.name == 'running'
        assert result.setup_stdout == 'HELLO'
        assert not stub_clear.called

    with describe('updating state to not started'):
        test_client.req(
            'patch',
            f'/api/v-internal/auto_tests/{test.id}/results/{result.id}',
            200,
            data={
                'state': m.AutoTestStepResultState.not_started.name,
                'setup_stdout': 'HELLO'
            },
            headers={
                'CG-Internal-Api-Password': app.config['AUTO_TEST_PASSWORD'],
                'CG-Internal-Api-Runner-Password': str(runner.id)
            },
            environ_base={'REMOTE_ADDR': 'localhost'}
        )
        assert stub_clear.called
        assert result.state.name == 'not_started'
        assert result.setup_stdout is None


def test_update_result_dates_in_broker(
    describe, basic, logged_in, test_client, session, app, monkeypatch,
    stub_function_class, monkeypatch_celery, monkeypatch_broker, assert_similar
):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        broker_ses = monkeypatch_broker(True)

        with logged_in(teacher):
            test = m.AutoTest.query.get(
                helpers.create_auto_test(
                    test_client,
                    assig_id,
                    amount_sets=2,
                    amount_suites=2,
                    amount_fixtures=1,
                    stop_points=[0.5, None],
                    grade_calculation='partial',
                )['id']
            )

        run = m.AutoTestRun(auto_test=test, batch_run_done=True)
        run.runners_requested = 1
        session.add(run)
        session.commit()

    with describe('handing in new submission'), logged_in(teacher):
        now = DatetimeWithTimezone.utcnow()
        with freezegun.freeze_time(now):
            sub_id = helpers.create_submission(test_client, assig_id)['id']
            other_sub = helpers.create_submission(
                test_client, assig_id, is_test_submission=True
            )

            _, call = broker_ses.calls
            assert call['method'] == 'put'
            assert_similar(
                call['kwargs']['json']['metadata'], {
                    'results': {
                        'not_started': now.isoformat(),
                        'running': None,
                        'passed': None,
                    }
                }
            )

    result = LocalProxy(
        lambda: m.AutoTestResult.query.filter_by(work_id=sub_id).one()
    )
    runner = m.AutoTestRunner(_ipaddr='localhost', run=run)
    session.commit()
    broker_ses.reset()
    headers = {
        'CG-Internal-Api-Password': app.config['AUTO_TEST_PASSWORD'],
        'CG-Internal-Api-Runner-Password': str(runner.id)
    }

    with describe('updating to started state'):
        test_client.req(
            'patch',
            f'/api/v-internal/auto_tests/{test.id}/results/{result.id}',
            200,
            data={
                'state': m.AutoTestStepResultState.running.name,
            },
            headers=headers,
            environ_base={'REMOTE_ADDR': 'localhost'}
        )

        call, = broker_ses.calls

        # We still have one not started result
        assert_similar(
            call['kwargs']['json']['metadata'], {
                'results': {
                    'not_started': str,
                    'running': str,
                    'passed': None,
                }
            }
        )

    broker_ses.reset()

    with describe('updating state to passed state'):
        test_client.req(
            'patch',
            f'/api/v-internal/auto_tests/{test.id}/results/{result.id}',
            200,
            data={
                'state': m.AutoTestStepResultState.passed.name,
            },
            headers=headers,
            environ_base={'REMOTE_ADDR': 'localhost'}
        )

        call, = broker_ses.calls
        # We still have one not started result
        assert_similar(
            call['kwargs']['json']['metadata'], {
                'results': {
                    'not_started': str,
                    'running': None,
                    'passed': str,
                }
            }
        )
    broker_ses.reset()

    with describe('deleting submission should work'), logged_in(teacher):
        test_client.req(
            'delete', f'/api/v1/submissions/{get_id(other_sub)}', 204
        )
        call, = broker_ses.calls
        # We no longer have a non started result
        assert_similar(
            call['kwargs']['json']['metadata'], {
                'results': {
                    'not_started': None,
                    'running': None,
                    'passed': str,
                }
            }
        )

    broker_ses.reset()
    with describe('try task without existing run'):

        psef.tasks.update_latest_results_in_broker(-1)
        assert not broker_ses.calls


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
def test_output_dir(
    monkeypatch_celery, monkeypatch_broker, basic, test_client, logged_in,
    describe, live_server, lxc_stub, monkeypatch, app, session,
    stub_function_class, assert_similar, monkeypatch_for_run
):
    with describe('setup'):
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            # yapf: disable
            test = helpers.create_auto_test_from_dict(
                test_client, assig_id, {
                    'sets': [{
                        'suites': [{
                            'steps': [{
                                'run_p': 'cp -r $STUDENT $AT_OUTPUT',
                                'name': 'Copy all files',
                            }]
                        }, {
                            'steps': [{
                                'run_p': 'echo HELLO > $AT_OUTPUT/hello',
                                'name': 'Create hello file',
                            }, {
                                'run_p': 'echo BYE > $AT_OUTPUT/bye',
                                'name': 'Create bye file',
                            }, {
                                'run_p': 'ln -s /etc/passwd $AT_OUTPUT/passwd',
                                'name': 'Create link',
                            }, {
                                'run_p': 'exit 1',
                                'name': 'Fail',
                            }]
                        }],
                    }, {
                        'suites': [{
                            'steps': [{
                                'run_p': 'sleep 0',
                                'name': 'Do not create a file'
                            }],
                        }],
                    }]
                }
            )
            # yapf: enable
        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('start_auto_test'):
        t = m.AutoTest.query.get(test['id'])
        with logged_in(teacher):
            work = helpers.create_submission(
                test_client, assig_id, for_user=student.username
            )
            work_tree = test_client.req(
                'get', f'/api/v1/submissions/{work["id"]}/files/', 200
            )

            def remove_ids(tree):
                tree['id'] = str
                for entry in tree.get('entries', []):
                    remove_ids(entry)

            remove_ids(work_tree)
            session.commit()

        with logged_in(teacher):
            run_id = test_client.req('post', f'{url}/runs/', 200)['id']
            session.commit()

        monkeypatch_broker()
        live_server_url, stop_server = live_server(get_stop=True)
        thread = threading.Thread(
            target=psef.auto_test.start_polling, args=(app.config, )
        )
        thread.start()
        thread.join()

        res = session.query(m.AutoTestResult).filter_by(work_id=work['id']
                                                        ).one().id

    with describe('Files should be uploaded'):
        with logged_in(teacher):
            suite1 = str(test['sets'][0]['suites'][0]['id'])
            suite2 = str(test['sets'][0]['suites'][1]['id'])
            files = test_client.req(
                'get',
                f'{url}/runs/{run_id}/results/{res}',
                200,
                result={
                    '__allow_extra__': True,
                    'suite_files': {
                        suite1: work_tree['entries'],
                        suite2: [{
                            'name': 'bye',
                            'id': str,
                        }, {
                            'name': 'hello',
                            'id': str,
                        }, {
                            'name': 'passwd',
                            'id': str,
                        }],
                    },
                    'points_achieved': 5,
                }
            )['suite_files']
            sym_link_id = files[suite2][-1]['id']

            response = test_client.get(
                '/api/v1/code/{file_id}'.format(file_id=sym_link_id)
            )
            assert response.status_code == 200
            assert 'symbolic link' in response.get_data(as_text=True)

    with describe('It should never have feedback'):
        with logged_in(teacher):
            file_url = '/api/v1/code/{file_id}'.format(file_id=sym_link_id)
            test_client.req('get', f'{file_url}?type=feedback', 200, result={})
            test_client.req(
                'get', f'{file_url}?type=linter-feedback', 200, result={}
            )
            test_client.req(
                'get',
                f'{file_url}?type=file-url',
                200,
                result={
                    'name': re.compile(r'[\-0-9a-fA-F]'),
                }
            )

    with describe('Students do not see the files by default'):
        with logged_in(student):
            # Students do not have permission to see suite files by default by
            # default.
            test_client.req(
                'get',
                f'{url}/runs/{run_id}/results/{res}',
                200,
                result={
                    '__allow_extra__': True,
                    'suite_files': {},
                    'points_achieved': 5,
                }
            )

            assert test_client.get(
                '/api/v1/code/{file_id}'.format(file_id=sym_link_id)
            ).status_code == 403

    with describe('Can use proxy to view files'):
        proxy_url = f'{url}/runs/{run_id}/results/{res}/suites/{suite2}/proxy'
        with logged_in(teacher):
            proxy = test_client.req(
                'post',
                proxy_url,
                200,
                data={
                    'allow_remote_resources': True,
                    'allow_remote_scripts': True,
                }
            )['id']

        res = test_client.post(
            f'/api/v1/proxies/{proxy}/bye', follow_redirects=False
        )
        assert res.status_code == 303
        res = test_client.get(res.headers['Location'])
        assert res.status_code == 200

        assert test_client.get(
            '/api/v1/proxies/non_existing'
        ).status_code == 404

    with describe('Students cannot use proxy'), logged_in(student):
        proxy = test_client.req(
            'post',
            proxy_url,
            403,
            data={
                'allow_remote_resources': True, 'allow_remote_scripts': True
            }
        )

    with describe('After deleting run results are removed from disk'):
        file = m.AutoTestOutputFile.query.get(sym_link_id)
        assert file is not None
        path = file.get_diskname()
        assert os.path.isfile(path)
        del file

        with logged_in(teacher):
            test_client.req('delete', f'{url}/runs/{run_id}', 204)

        assert not os.path.isfile(path)


def test_copy_auto_test(
    basic, test_client, logged_in, describe, session, admin_user
):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        with logged_in(admin_user):
            new_course = helpers.create_course(test_client)
            new_assig_id = helpers.create_assignment(
                test_client,
                new_course,
                deadline=DatetimeWithTimezone.utcnow() + timedelta(days=30)
            )['id']
            crole = m.CourseRole.query.filter_by(
                name='Teacher',
                course_id=new_course['id'],
            ).one()
            session.add(crole)
            t = teacher._get_current_object()
            s = student._get_current_object()
            t.courses[new_course['id']] = crole
            s.courses[new_course['id']] = crole
            session.commit()

        with logged_in(teacher):
            # yapf: disable
            test = helpers.create_auto_test_from_dict(
                test_client, assig_id, {
                    'sets': [{
                        'suites': [{
                            'steps': [{
                                'run_p': 'cp -r $STUDENT $AT_OUTPUT',
                                'name': 'Copy all files',
                            }]
                        }, {
                            'steps': [{
                                'run_p': 'echo HELLO > $AT_OUTPUT/hello',
                                'name': 'Create hello file',
                            }, {
                                'run_p': 'echo BYE > $AT_OUTPUT/bye',
                                'name': 'Create bye file',
                            }, {
                                'run_p': 'ln -s /etc/passwd $AT_OUTPUT/passwd',
                                'name': 'Create link',
                            }, {
                                'run_p': 'exit 1',
                                'name': 'Fail',
                            }]
                        }],
                    }, {
                        'suites': [{
                            'steps': [{
                                'run_p': 'sleep 0',
                                'name': 'Do not create a file'
                            }],
                        }],
                    }],
                    'fixtures': [io.BytesIO(b'a FILE!')],
                }
            )
            # yapf: enable

        url = f'/api/v1/auto_tests/{test["id"]}'
        assert len(test['fixtures']) == 1

    with describe('students cannot view AT so they cannot copy'
                  ), logged_in(student):
        test_client.req(
            'post',
            f'/api/v1/auto_tests/{test["id"]}/copy',
            403,
            data={'assignment_id': new_assig_id}
        )

    with describe('teachers can copy the AT'), logged_in(teacher):

        def remove_id(dct):
            if isinstance(dct, dict):
                return {
                    key: object if key.endswith('id') else remove_id(value)
                    for key, value in dct.items()
                }
            elif isinstance(dct, list):
                return [remove_id(item) for item in dct]
            return dct

        new_test = test_client.req(
            'post',
            f'/api/v1/auto_tests/{test["id"]}/copy',
            200,
            data={'assignment_id': new_assig_id},
            result=remove_id(test)
        )
        assert new_test['assignment_id'] == new_assig_id

        # Make sure the rubric is also copied
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            200,
            result=remove_id(
                test_client.req(
                    'get',
                    f'/api/v1/assignments/{new_assig_id}/rubrics/',
                    200,
                )
            ),
        )

    with describe('cannot copy to assignment with AT'), logged_in(teacher):
        err = test_client.req(
            'post',
            f'/api/v1/auto_tests/{test["id"]}/copy',
            409,
            data={'assignment_id': new_assig_id}
        )
        assert 'already has an AutoTest' in err['message']


@pytest.mark.parametrize(
    'fresh_db,fail_wget_attach', [(True, True)], indirect=True
)
def test_failing_attach(
    monkeypatch_celery, basic, test_client, logged_in, describe, live_server,
    lxc_stub, monkeypatch, app, session, stub_function_class, assert_similar,
    monkeypatch_for_run, monkeypatch_broker
):
    with describe('setup'):
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            test = helpers.create_auto_test_from_dict(
                test_client, assig_id, {
                    'sets': [{
                        'suites': [{
                            'steps': [{
                                'run_p': 'cp -r $STUDENT $AT_OUTPUT',
                                'name': 'Copy all files',
                            }]
                        }],
                    }]
                }
            )

        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('start_auto_test'):
        with logged_in(teacher):
            work = helpers.create_submission(
                test_client, assig_id, for_user=student.username
            )

            session.commit()

        with logged_in(teacher):
            test_client.req('post', f'{url}/runs/', 200)['id']
            session.commit()

        live_server_url, stop_server = live_server(get_stop=True)
        # It should throw an attach somewhere in the code, which should not
        # make the tests stuck. So the tests pass when this function returns
        # and the result is not finished.
        psef.auto_test.start_polling(app.config)

        res = session.query(m.AutoTestResult).filter_by(work_id=work['id']
                                                        ).one()
        assert res.state == m.AutoTestStepResultState.not_started


def test_starting_at_run_without_submissions(
    basic, test_client, logged_in, describe, session, monkeypatch,
    stub_function_class
):
    with describe('setup'):
        course, assig_id, teacher, student = basic

        stub_notify = stub_function_class()
        monkeypatch.setattr(
            psef.tasks, 'notify_broker_of_new_job', stub_notify
        )

        with logged_in(teacher):
            test = helpers.create_auto_test_from_dict(
                test_client, assig_id, {
                    'sets': [{
                        'suites': [{
                            'steps': [{
                                'run_p': 'cp -r $STUDENT $AT_OUTPUT',
                                'name': 'Copy all files',
                            }]
                        }],
                    }]
                }
            )

        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe("Starting AT run doesn't notify broker"), logged_in(teacher):
        test_client.req('post', f'{url}/runs/', 200)
        assert not stub_notify.called


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
def test_continuous_rubric(
    monkeypatch_celery, monkeypatch_broker, basic, test_client, logged_in,
    describe, live_server, lxc_stub, monkeypatch, app, session,
    stub_function_class, assert_similar, monkeypatch_for_run
):
    with describe('setup'):
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            # yapf: disable
            test = helpers.create_auto_test_from_dict(
                test_client, assig_id, {
                    'sets': [{
                        'suites': [{
                            'steps': [{
                                'run_c': 'echo 0.8',
                                'name': 'Copy all files',
                            }],
                            'rubric_type': 'continuous',
                        }, {
                            'steps': [{
                                'run_c': 'echo 0.75',
                                'name': 'Much',
                                'weight': 9,
                            }, {
                                'run_c': 'echo 1.0',
                                'name': 'Few',
                                'weight': 1,
                            }],
                            'rubric_type': 'continuous',
                        }],
                    }, {
                        'suites': [{
                            'steps': [{
                                'run_c': 'echo 0.5',
                                'name': 'normal rubric'
                            }],
                            'rubric_type': 'normal',
                        }],
                    }]
                }
            )
            # yapf: enable
        url = f'/api/v1/auto_tests/{test["id"]}'

        with logged_in(teacher):
            work = helpers.create_submission(
                test_client, assig_id, for_user=student.username
            )
            rubric = test_client.req(
                'get', f'/api/v1/submissions/{work["id"]}/rubrics/', 200
            )
        assert not rubric['selected']

    with describe('start_auto_test'):
        with logged_in(teacher):
            run_id = test_client.req('post', f'{url}/runs/', 200)['id']
            session.commit()

        monkeypatch_broker()
        live_server_url, stop_server = live_server(get_stop=True)
        thread = threading.Thread(
            target=psef.auto_test.start_polling, args=(app.config, )
        )
        thread.start()
        thread.join()

    with describe('Rubric should be filled in correctly'), logged_in(teacher):
        rubric_result = test_client.req(
            'get',
            f'/api/v1/submissions/{work["id"]}/rubrics/',
            200,
            result={
                **rubric,
                'selected': [{
                    '__allow_extra__': True,
                    'achieved_points': 0.8,
                }, {
                    '__allow_extra__': True,
                    'achieved_points': 7.75,
                }, {
                    '__allow_extra__': True,
                    'achieved_points': 0,
                }],
                'points': {
                    'max': rubric['points']['max'],
                    'selected': 7.75 + 0.8,
                },
            }
        )

    with describe('Rubrics can be copied with copy_locked_items'
                  ), logged_in(teacher):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work["id"]}/rubricitems/?copy_locked_items',
            200,
            data={'items': []}
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work["id"]}/rubrics/',
            200,
            result=rubric_result
        )

    with describe('Cannot copy and give rubric'), logged_in(teacher):
        lookup = {
            item['id']: row['id']
            for row in rubric['rubrics'] for item in row['items']
        }
        patch_data = {
            'items': [{
                'item_id': item['id'],
                'multiplier': item['multiplier'],
                'row_id': lookup[item['id']],
            } for item in rubric_result['selected']]
        }

        err = test_client.req(
            'patch',
            f'/api/v1/submissions/{work["id"]}/rubricitems/?copy_locked_items',
            400,
            data=patch_data
        )
        assert re.search(
            r'You cannot specify locked rows.*copy_locked_items',
            err['message']
        )

        # Can simply give all the values when not doing copy.
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work["id"]}/rubricitems/',
            200,
            data=patch_data
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work["id"]}/rubrics/',
            200,
            result=rubric_result
        )


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
def test_runner_harakiri(
    monkeypatch_celery, monkeypatch_broker, basic, test_client, logged_in,
    describe, live_server, lxc_stub, monkeypatch, app, session,
    stub_function_class, assert_similar, monkeypatch_for_run
):
    with describe('setup'):
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            test = helpers.create_auto_test(
                test_client,
                assig_id,
                amount_sets=2,
                amount_suites=2,
                amount_fixtures=1,
                stop_points=[0.5, None],
                grade_calculation='partial',
            )
        url = f'/api/v1/auto_tests/{test["id"]}'

        with logged_in(teacher):
            helpers.create_submission(test_client, assig_id, for_user=student)

        runners_in_start = multiprocessing.Queue(1000)

        def start_pool(*_, **__):
            with app.app_context():
                runners_in_start.put(len(t.run.runners))

        monkeypatch.setattr(cg_worker_pool.WorkerPool, 'start', start_pool)

    with describe('start_auto_test'):
        t = LocalProxy(lambda: m.AutoTest.query.get(test['id']))
        with logged_in(teacher):
            test_client.req(
                'post',
                f'{url}/runs/',
                200,
                data={'continuous_feedback_run': False},
            )
            session.commit()
        assert t.run is not None

        monkeypatch_broker()
        live_server_url, stop_server = live_server(get_stop=True)
        thread = threading.Thread(
            target=psef.auto_test.start_polling, args=(app.config, )
        )
        thread.start()
        thread.join()

        assert not t.run.runners
        assert runners_in_start.get()


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
def test_failing_container_startup(
    monkeypatch_celery, basic, test_client, logged_in, describe, live_server,
    lxc_stub, monkeypatch, app, session, stub_function_class, assert_similar,
    monkeypatch_broker, monkeypatch_for_run, make_failer
):
    with describe('setup'):
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            test = helpers.create_auto_test_from_dict(
                test_client, assig_id, {
                    'sets': [{
                        'suites': [{
                            'steps': [{
                                'run_p': 'cp -r $STUDENT $AT_OUTPUT',
                                'name': 'Copy all files',
                            }]
                        } for _ in range(7)],
                    }]
                }
            )

        url = f'/api/v1/auto_tests/{test["id"]}'

        def on_first_fail():
            with app.test_request_context('/'):
                # Make sure the result was running while we first fail
                # starting the container.
                res = session.query(
                    m.AutoTestResult
                ).filter_by(work_id=work['id']).one_or_none()
                if res is None:
                    return True
                assert res.state == m.AutoTestStepResultState.running
            return False

        failer = make_failer(6, lxc.Container.start, on_first_fail)
        monkeypatch.setattr(lxc.Container, 'start', failer)

    with describe(
        'Failing startup should stop the runner and reset the result'
    ):
        with logged_in(teacher):
            test_client.req('post', f'{url}/runs/', 200)['id']
            session.commit()

        with logged_in(teacher):
            work = helpers.create_submission(
                test_client, assig_id, for_user=student.username
            )

            session.commit()
            session.commit()

        res = session.query(m.AutoTestResult).filter_by(work_id=work['id']
                                                        ).one()

        # Should begin as not started
        assert res.state == m.AutoTestStepResultState.not_started
        session.expire_all()

        live_server_url, stop_server = live_server(get_stop=True)
        psef.auto_test.start_polling(app.config)
        session.expire_all()

        # Make sure starting failed at least once
        assert failer.failed_at_least_once()
        # The result should be in the state `not_started` ready for another
        # runner to pick up.
        res = session.query(m.AutoTestResult).filter_by(work_id=work['id']
                                                        ).one()
        assert res.state == m.AutoTestStepResultState.not_started


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
def test_failing_container_shutdown(
    monkeypatch_celery, basic, test_client, logged_in, describe, live_server,
    lxc_stub, monkeypatch, app, session, stub_function_class, assert_similar,
    monkeypatch_broker, monkeypatch_for_run, make_failer
):
    with describe('setup'):
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            test = helpers.create_auto_test_from_dict(
                test_client, assig_id, {
                    'sets': [{
                        'suites': [{
                            'steps': [{
                                'run_p': 'ls',
                                'name': f'Simple step {i}',
                            }]
                        } for i in range(2)],
                    }]
                }
            )

        url = f'/api/v1/auto_tests/{test["id"]}'
        failed_at_least_once = False

        def on_fail(amount):
            nonlocal failed_at_least_once

            if amount > 6 or failed_at_least_once:
                failed_at_least_once = True
                return True
            return False

        monkeypatch.setattr(
            lxc.Container,
            'shutdown',
            # Toggle between success and fail
            make_failer(4, lxc.Container.shutdown, on_fail=on_fail)
        )

    with describe('A sometimes failing shutdown should simply work'):
        with logged_in(teacher):
            test_client.req('post', f'{url}/runs/', 200)['id']
            session.commit()

        with logged_in(teacher):
            work = helpers.create_submission(
                test_client, assig_id, for_user=student.username
            )

            session.commit()

        res = session.query(m.AutoTestResult).filter_by(work_id=work['id']
                                                        ).one()
        # Should begin as not started
        assert res.state == m.AutoTestStepResultState.not_started

        live_server_url, stop_server = live_server(get_stop=True)
        psef.auto_test.start_polling(app.config)
        session.expire_all()

        # The result should be in the state `not_started` ready for another
        # runner to pick up.
        res = session.query(m.AutoTestResult).filter_by(work_id=work['id']
                                                        ).one()
        assert res.state == m.AutoTestStepResultState.passed

        # Make sure starting failed at least once
        assert failed_at_least_once


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
@pytest.mark.parametrize('prefer_teacher_revision', [True, False])
@pytest.mark.parametrize('with_teacher_revision', [True, False])
def test_prefer_teacher_revision_option(
    monkeypatch_celery, monkeypatch_broker, basic, test_client, logged_in,
    describe, live_server, lxc_stub, monkeypatch, app, session,
    stub_function_class, assert_similar, monkeypatch_for_run, admin_user,
    prefer_teacher_revision, with_teacher_revision
):
    # TODO: This test fails if it is run _after_ test_running_old_submission,
    # although it is unclear why.
    with describe('setup'):
        course, assig_id, teacher, student = basic

        with logged_in(teacher):
            # yapf: disable
            test = helpers.create_auto_test_from_dict(
                test_client, assig_id, {
                    'prefer_teacher_revision': prefer_teacher_revision,
                    'sets': [{
                        'suites': [{
                            'submission_info': True,
                            'steps': [{
                                'run_p': f'{psef.auto_test.BASH_PATH} script.sh',
                                'name': 'Run script',
                            }]
                        }],
                    }],
                }
            )
            # yapf: enable

        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('start_auto_test'):
        t = m.AutoTest.query.get(test['id'])
        with logged_in(teacher), tempfile.NamedTemporaryFile() as f:
            f.write(b'echo student\n')
            f.flush()

            work = helpers.create_submission(
                test_client,
                assig_id,
                for_user=student.username,
                submission_data=(f.name, 'script.sh'),
            )

            if with_teacher_revision:
                file_id = test_client.req(
                    'get',
                    f'/api/v1/submissions/{work["id"]}/files/',
                    200,
                )['entries'][0]['id']
                test_client.req(
                    'patch',
                    f'/api/v1/code/{file_id}',
                    200,
                    real_data='echo teacher\n',
                )

            run_id = test_client.req('post', f'{url}/runs/', 200)['id']
            session.commit()

        monkeypatch_broker()
        live_server_url, stop_server = live_server(get_stop=True)
        thread = threading.Thread(
            target=psef.auto_test.start_polling, args=(app.config, )
        )
        thread.start()
        thread.join()

        res = session.query(m.AutoTestResult).filter_by(work_id=work['id']
                                                        ).one()

    with describe('should run the correct code'):
        assert res.is_finished
        step_result = res.step_results[0]
        print(step_result.log)

        if prefer_teacher_revision and with_teacher_revision:
            assert step_result.log['stdout'] == 'teacher\n'
        else:
            assert step_result.log['stdout'] == 'student\n'


@pytest.mark.parametrize(
    'fresh_db,poll_after_done', [(True, True)], indirect=True
)
def test_running_old_submission(
    monkeypatch_celery, monkeypatch_broker, basic, test_client, logged_in,
    describe, live_server, lxc_stub, monkeypatch, app, session,
    stub_function_class, assert_similar, monkeypatch_for_run, request
):
    with describe('setup'):
        course, assig_id, teacher, student = basic
        monkeypatch.setitem(app.config, 'AUTO_TEST_CF_SLEEP_TIME', 0.25)
        monkeypatch.setitem(app.config, 'AUTO_TEST_CF_EXTRA_AMOUNT', 4)

        uploaded_once = False

        @flask.signals.request_started.connect_via(app)
        def update_result(*_, **__):
            nonlocal uploaded_once
            if uploaded_once:
                return

            result = m.AutoTestResult.query.get(
                flask.request.view_args.get('result_id', -1)
            )
            if result and result.work_id == sub1['id']:
                # Make sure we only upload a new submission once
                uploaded_once = True
                with app.app_context(), logged_in(teacher):
                    helpers.create_submission(
                        test_client, assig_id, for_user=student
                    )

        request.addfinalizer(
            lambda: flask.signals.request_started.
            disconnect(update_result, app)
        )

        with logged_in(teacher):
            # yapf: disable
            test = helpers.create_auto_test_from_dict(
                test_client, helpers.get_id(assig_id), {
                    'sets': [{
                        'suites': [{
                            'submission_info': True,
                            'steps': [{
                                'run_p': 'sleep 1',
                                'name': 'Short sleep',
                            }, {
                                'run_p': 'sleep 6',
                                'name': 'Longer sleep',
                            }]
                        }],
                    }],
                }
            )
            # yapf: enable
        url = f'/api/v1/auto_tests/{test["id"]}'

        with logged_in(teacher):
            sub1 = helpers.create_submission(
                test_client, assig_id, for_user=student
            )

    with describe('start_auto_test'):
        t = LocalProxy(lambda: m.AutoTest.query.get(test['id']))
        with logged_in(teacher):
            test_client.req(
                'post',
                f'{url}/runs/',
                200,
                data={'continuous_feedback_run': False},
            )
            session.commit()

        monkeypatch_broker()
        live_server_url, stop_server = live_server(get_stop=True)
        thread = threading.Thread(
            target=psef.auto_test.start_polling, args=(app.config, )
        )
        thread.start()
        thread.join()

        assert session.query(
            m.AutoTestResult
        ).filter_by(work_id=sub1['id']).one().state.name == 'skipped'
        latest = helpers.to_db_object(
            assig_id, m.Assignment
        ).get_latest_submission_for_user(
            helpers.to_db_object(student, m.User)
        ).one()
        latest_id = helpers.get_id(latest)
        assert isinstance(latest_id, int)
        assert latest_id != sub1

        with logged_in(teacher):
            res = test_client.req(
                'get',
                f'{url}/runs/{t.run.id}/users/{student.id}/results/',
                200,
                result=[
                    {'__allow_extra__': True, 'work_id': sub1['id']},
                    {'__allow_extra__': True, 'work_id': latest_id},
                ]
            )

        assert session.query(
            m.AutoTestResult
        ).filter_by(work_id=res[-1]['work_id']).one().state.name == 'passed'


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
@pytest.mark.parametrize('deadline', ['tomorrow', None])
def test_submission_info_env_vars(
    monkeypatch_celery, monkeypatch_broker, basic, test_client, logged_in,
    describe, live_server, lxc_stub, monkeypatch, app, session, deadline,
    stub_function_class, assert_similar, monkeypatch_for_run, admin_user
):
    with describe('setup'):
        course, _, teacher, student = basic

        with logged_in(admin_user):
            assig = helpers.create_assignment(
                test_client,
                course,
                deadline=deadline,
            )

        with logged_in(teacher):
            # yapf: disable
            test = helpers.create_auto_test_from_dict(
                test_client, assig['id'], {
                    'sets': [{
                        'suites': [{
                            'submission_info': True,
                            'steps': [{
                                'run_p': 'echo "$CG_INFO"',
                                'name': 'With info',
                            }]
                        }],
                    }, {
                        'suites': [{
                            'submission_info': False,
                            'steps': [{
                                'run_p': 'echo "$CG_INFO"',
                                'name': 'Without info',
                            }]
                        }],
                    }],
                }
            )
            # yapf: enable

        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('start_auto_test'):
        t = m.AutoTest.query.get(test['id'])
        with logged_in(teacher):
            if deadline is None:
                work = helpers.create_submission(
                    test_client, assig['id'], is_test_submission=True
                )
            else:
                work = helpers.create_submission(
                    test_client, assig['id'], for_user=student.username
                )

        with logged_in(teacher):
            run_id = test_client.req('post', f'{url}/runs/', 200)['id']
            session.commit()

        monkeypatch_broker()
        live_server_url, stop_server = live_server(get_stop=True)
        thread = threading.Thread(
            target=psef.auto_test.start_polling, args=(app.config, )
        )
        thread.start()
        thread.join()

        res = session.query(m.AutoTestResult).filter_by(work_id=work['id']
                                                        ).one()

    with describe('should contain expected data only when enabled'):
        expected = {
            'deadline': None if deadline is None else assig['deadline'],
            'submitted_at': work['created_at'],
            'result_id': res.id,
            'student_id': work['user']['id'],
        }

        print(res.step_results)
        assert len(res.step_results) == 2

        for step_result in res.step_results:
            step = step_result.step
            output = json.loads(step_result.log['stdout'])

            if step.suite.submission_info:
                assert output == expected
            else:
                assert output == {}


def test_broker_extra_env_vars(describe):
    cur_user = getpass.getuser()
    cont = psef.auto_test.StartedContainer(None, '', {}, lambda: None)

    # Ensure initial conditions are as expected.
    with describe('env vars "a" and "b" should not exist by default'):
        env = cont._create_env(cur_user)
        assert 'a' not in env
        assert 'b' not in env
        assert env.get('a') is None
        assert env.get('b') is None

    with describe('should include variables in the extra env'):
        with cont.extra_env({'a': 'a'}):
            env = cont._create_env(cur_user)
            assert env.get('a') == 'a'
            assert 'b' not in env

    with describe('should support nesting'):
        with cont.extra_env({'a': 'a'}):
            with cont.extra_env({'b': 'b'}):
                env = cont._create_env(cur_user)
                assert env.get('a') == 'a'
                assert env.get('b') == 'b'

            env = cont._create_env(cur_user)
            assert env.get('a') == 'a'
            assert env.get('b') is None
            assert 'b' not in env

    with describe('inner envs should override outer envs'):
        with cont.extra_env({'a': 'a'}):
            with cont.extra_env({'a': 'b'}):
                env = cont._create_env(cur_user)
                assert env.get('a') == 'b'

            env = cont._create_env(cur_user)
            assert env.get('a') == 'a'

    with describe('should not override standard env vars'):
        with cont.extra_env({'PATH': ''}):
            env = cont._create_env(cur_user)
            assert env['PATH'] != ''


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
def test_update_step_attachment(
    monkeypatch_celery, monkeypatch_broker, basic, test_client, logged_in,
    describe, live_server, lxc_stub, monkeypatch, app, session, admin_user,
    stub_function_class, assert_similar, monkeypatch_for_run
):
    fixtures_dir = f'{os.path.dirname(__file__)}/../test_data'
    junit_xml_files = [
        f'{fixtures_dir}/test_junit_xml/valid.xml',
        f'{fixtures_dir}/test_junit_xml/invalid_xml.xml',
        f'{fixtures_dir}/test_submissions/hello.py',
        None,
    ]

    with describe('setup'):
        course, _, teacher, student = basic
        student2 = helpers.create_user_with_role(session, 'Student', course)

        with logged_in(admin_user):
            assig = helpers.create_assignment(
                test_client,
                course,
                deadline='tomorrow',
            )

        with logged_in(teacher):
            steps = []
            for i, junit_xml in enumerate(junit_xml_files):
                if junit_xml is None:
                    program = 'echo hello world'
                else:
                    program = f'cp "{junit_xml}" "$CG_JUNIT_XML_LOCATION"'

                steps.append({
                    'type': 'junit_test',
                    'data': {'program': program},
                    'name': f'junit test {i}',
                })

            # yapf: disable
            test = helpers.create_auto_test_from_dict(
                test_client, assig['id'], {
                    'sets': [{
                        'suites': [{
                            'submission_info': True,
                            'steps': steps,
                        }],
                    }],
                }
            )
            # yapf: enable

        url = f'/api/v1/auto_tests/{test["id"]}'

    with describe('start_auto_test'):
        t = m.AutoTest.query.get(test['id'])
        with logged_in(teacher):
            work = helpers.create_submission(
                test_client, assig['id'], for_user=student.username
            )
            work2 = helpers.create_submission(
                test_client, assig['id'], for_user=student2.username
            )

            run_id = test_client.req('post', f'{url}/runs/', 200)['id']
            session.commit()

        monkeypatch_broker()
        live_server_url, stop_server = live_server(get_stop=True)
        thread = threading.Thread(
            target=psef.auto_test.start_polling, args=(app.config, )
        )
        thread.start()
        thread.join()

        res = session.query(m.AutoTestResult).filter_by(
            work_id=work['id'],
        ).one()

    with describe('attachment should be uploaded to the server'):
        for i, step_result in enumerate(res.step_results):
            with logged_in(teacher):
                attachment = test_client.get(
                    f'{url}/runs/{run_id}/step_results/{step_result.id}'
                    '/attachment',
                )

            if junit_xml_files[i] is None:
                assert attachment.status_code == 404
            else:
                assert attachment.status_code == 200
                with open(junit_xml_files[i], 'r') as f:
                    assert attachment.get_data(as_text=True) == f.read()

    with describe('should not get points if XML is not created or invalid'):
        for i, step_result in enumerate(res.step_results):
            pts = step_result.log['points']
            path = junit_xml_files[i]
            if path is not None and path.endswith('/valid.xml'):
                assert 0.99 <= pts < 1.0
            else:
                assert pts == 0

    with describe('previous attachment should be deleted from disk'):
        step_result = res.step_results[0]
        old_attachment = step_result.attachment_filename
        assert old_attachment
        assert os.path.exists(f'{app.config["UPLOAD_DIR"]}/{old_attachment}')

        with tempfile.NamedTemporaryFile() as f:
            step_result.update_attachment(FileStorage(f))
        session.commit()

        res = session.query(m.AutoTestResult).filter_by(
            work_id=work['id'],
        ).one()
        step_result = res.step_results[0]
        new_attachment = step_result.attachment_filename

        assert new_attachment != old_attachment
        assert os.path.exists(f'{app.config["UPLOAD_DIR"]}/{new_attachment}')
        assert not os.path.exists(
            f'{app.config["UPLOAD_DIR"]}/{old_attachment}'
        )

    with describe('should fail when step is not in the requested run'):
        with logged_in(teacher):
            attachment = test_client.get(
                f'{url}/runs/0/step_results/{step_result.id}/attachment',
            )

        assert attachment.status_code == 404
        assert ('The requested "AutoTestStepResult" was not found'
                ) in attachment.json['message']

    with describe('should fail when work is deleted'):
        work = session.query(m.Work).filter_by(id=work['id']).one()
        work.deleted = True
        session.commit()

        with logged_in(teacher):
            attachment = test_client.get(
                f'{url}/runs/{run_id}/step_results/{step_result.id}/attachment',
            )

        assert attachment.status_code == 404
        assert ('The requested "AutoTestStepResult" was not found'
                ) in attachment.json['message']

    with describe('should be deleted when the result is reset'):
        work2 = session.query(m.Work).filter_by(id=work2['id']).one()
        res2 = m.AutoTestResult.query.filter_by(work=work2).one()
        attachment2 = os.path.join(
            app.config["UPLOAD_DIR"], res2.step_results[0].attachment_filename
        )
        assert os.path.isfile(attachment2)
        work2.assignment.auto_test.reset_work(work2)
        session.commit()
        assert not os.path.isfile(attachment2)

    with describe('should be deleted when the run is deleted'):
        step_result_id = step_result.id
        with logged_in(teacher):
            test_client.req('delete', f'{url}/runs/{run_id}', 204)
            attachment = test_client.get(
                f'{url}/runs/{run_id}/step_results/{step_result_id}'
                '/attachment'
            )

        assert attachment.status_code == 404
        assert ('The requested "AutoTestStepResult" was not found'
                ) in attachment.json['message']
        assert not os.path.exists(
            f'{app.config["UPLOAD_DIR"]}/{new_attachment}'
        )
