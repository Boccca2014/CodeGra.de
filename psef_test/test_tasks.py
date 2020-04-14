import time
import uuid
from datetime import timedelta

import pytest

import psef
import helpers
import requests_stubs
from psef import tasks as t
from psef import models as m
from helpers import create_auto_test, create_assignment, create_submission
from conftest import DESCRIBE_HOOKS
from cg_celery import TaskStatus
from cg_dt_utils import DatetimeWithTimezone
from cg_flask_helpers import callback_after_this_request


def flush_callbacks():
    t.celery._call_callbacks(TaskStatus.success)
    t.celery._after_task_callbacks = []


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
def test_check_heartbeat(
    session, describe, monkeypatch, stub_function_class, app,
    assignment_real_works, monkeypatch_celery
):
    assignment, submission = assignment_real_works
    sub2_id = m.Work.query.filter_by(assignment_id=assignment.id
                                     ).filter(m.Work.id != submission['id']
                                              ).first().id

    with describe('setup'):
        stub_heart = stub_function_class()
        monkeypatch.setattr(t, 'check_heartbeat_auto_test_run', stub_heart)

        stub_notify_new = stub_function_class()
        monkeypatch.setattr(t, '_notify_broker_of_new_job_1', stub_notify_new)

        orig_kill_and_adjust = t._kill_runners_and_adjust_1
        kill_and_adjust = stub_function_class(orig_kill_and_adjust)
        monkeypatch.setattr(t, 'kill_runners_and_adjust', kill_and_adjust)

        stub_notify_stop = stub_function_class()
        monkeypatch.setattr(t, 'notify_broker_end_of_job', stub_notify_stop)

        stub_notify_kill_single = stub_function_class()
        monkeypatch.setattr(
            t, 'notify_broker_kill_single_runner', stub_notify_kill_single
        )

        test = m.AutoTest(
            setup_script='', run_setup_script='', assignment=assignment
        )
        run = m.AutoTestRun(
            _job_id=uuid.uuid4(), auto_test=test, batch_run_done=False
        )
        run.results = [
            m.AutoTestResult(work_id=sub2_id, final_result=False),
            m.AutoTestResult(work_id=submission['id'], final_result=False)
        ]
        run.results[0].state = m.AutoTestStepResultState.running
        run.results[1].state = m.AutoTestStepResultState.passed
        session.add(run)

        with app.test_request_context('/non_existing', {}):
            run.add_active_runner('localhost')
        runner = run.runners[0]
        run.results[0].runner = runner
        run.results[1].runner = runner

        with app.test_request_context('/non_existing', {}):
            run.add_active_runner('localhost2')

        assert runner.run
        session.commit()

    with describe('not expired'):
        t._check_heartbeat_stop_test_runner_1(runner.id.hex)
        flush_callbacks()
        now = DatetimeWithTimezone.utcnow()

        # As the heartbeats have not expired yet a new check should be
        # scheduled
        assert len(stub_heart.all_args) == 1
        assert stub_heart.all_args[0][0] == (runner.id.hex, )
        assert (stub_heart.all_args[0]['eta'] - now).total_seconds() > 0

        assert not stub_notify_new.called
        assert not kill_and_adjust.called
        assert not stub_notify_stop.all_args
        assert not stub_notify_kill_single.all_args

    with describe('expired'):
        runner.last_heartbeat = DatetimeWithTimezone.utcfromtimestamp(0)
        old_job_id = run.get_job_id()
        session.commit()
        run = runner.run
        t._check_heartbeat_stop_test_runner_1(runner.id.hex)
        flush_callbacks()

        assert not stub_heart.called
        assert len(stub_notify_new.all_args) == 0
        assert len(kill_and_adjust.args) == 1
        assert len(stub_notify_stop.all_args) == 0
        assert len(stub_notify_kill_single.all_args) == 0

        run.get_job_id() != old_job_id
        assert runner.run is None
        assert (
            run.results[0].state == m.AutoTestStepResultState.not_started
        ), 'The results should be cleared'
        assert (
            run.results[1].state == m.AutoTestStepResultState.passed
        ), 'Passed results should not be cleared'

    with describe('With non existing runner'):
        t._check_heartbeat_stop_test_runner_1(uuid.uuid4().hex)
        flush_callbacks()

        assert not stub_heart.called
        assert not stub_notify_new.called
        assert not stub_notify_stop.called
        assert not stub_notify_kill_single.called


def test_after_this_request_in_celery(monkeypatch_celery):
    res = []
    amount = -1

    @t.celery.task
    def test_task():
        nonlocal amount
        if amount == -1:
            amount += 2
            test_task()

        @callback_after_this_request
        def after():
            res.append(3)

        res.append(amount)
        amount += 1

    test_task.delay()
    assert res == [1, 2, 3, 3]


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
def test_adjust_amomunt_runners(
    session, describe, monkeypatch, stub_function_class, app,
    assignment_real_works, monkeypatch_celery
):
    assignment, submission = assignment_real_works

    with describe('setup'):
        stub_notify_new = stub_function_class()
        monkeypatch.setattr(t, '_notify_broker_of_new_job_1', stub_notify_new)

        test = m.AutoTest(
            setup_script='', run_setup_script='', assignment=assignment
        )
        run = m.AutoTestRun(
            _job_id=uuid.uuid4(), auto_test=test, batch_run_done=False
        )
        run.results = [
            m.AutoTestResult(work_id=submission['id'], final_result=False)
        ]
        run.results[0].state = m.AutoTestStepResultState.passed
        session.add(run)

        with app.test_request_context('/non_existing', {}):
            run.add_active_runner('localhost')
        runner = run.runners[0]
        assert runner.run
        session.commit()

    with describe("Should not request runners when we don't need any"):
        t.adjust_amount_runners(run.id)
        assert not stub_notify_new.called

    with describe('Should be called when there are results'):
        run.results.append(
            m.AutoTestResult(work_id=submission['id'], final_result=False)
        )
        run.results[-1].state = m.AutoTestStepResultState.not_started
        session.commit()

        t.adjust_amount_runners(run.id)
        assert stub_notify_new.called

    with describe('Should be called when we have enough'):
        run.runners_requested = 1
        session.commit()

        t.adjust_amount_runners(run.id)
        assert not stub_notify_new.called

    with describe('Should be called when we have too many'):
        run.runners_requested = 2
        session.commit()

        t.adjust_amount_runners(run.id)
        assert stub_notify_new.called


def test_batch_run_auto_test(
    test_client, logged_in, admin_user, session, monkeypatch,
    stub_function_class, monkeypatch_celery
):
    now = DatetimeWithTimezone.utcnow()
    five_minutes = timedelta(minutes=5)

    all_args = []

    def stub_stop_runners(*args, **kwargs):
        all_args.append({
            **{idx: val
               for idx, val in enumerate(args)},
            **kwargs,
        })

    stub_clear = stub_function_class()

    monkeypatch.setattr(m.AutoTestRun, 'stop_runners', stub_stop_runners)
    monkeypatch.setattr(
        m.AutoTestResult, 'clear', lambda *args: stub_clear(*args)
    )
    monkeypatch.setattr(t, 'adjust_amount_runners', stub_function_class())
    monkeypatch.setattr(
        t, 'update_latest_results_in_broker', stub_function_class()
    )

    def make_assig(*args, **kwargs):
        hidden = kwargs.pop('has_hidden', False)
        with logged_in(admin_user):
            assig_id = create_assignment(*args, **kwargs)['id']
            create_auto_test(test_client, assig_id, has_hidden_steps=hidden)
        assig = m.Assignment.query.get(assig_id)
        run = m.AutoTestRun(
            _job_id=uuid.uuid4(),
            auto_test=assig.auto_test,
            batch_run_done=False
        )
        session.add(run)
        session.commit()

        with logged_in(admin_user):
            sub_id = create_submission(test_client, assig.id)['id']
        assert run.id is not None
        session.add(
            m.AutoTestResult(
                final_result=False, work_id=sub_id, auto_test_run_id=run.id
            )
        )
        session.commit()

        return assig

    assig1 = make_assig(
        test_client, deadline=now + five_minutes, has_hidden=True
    )
    assig2 = make_assig(
        test_client, deadline=now - five_minutes, has_hidden=True
    )
    assig3 = make_assig(test_client, deadline=now - 2 * five_minutes)

    t._run_autotest_batch_runs_1()
    # We shouldn't stop the runners for assig3, as this assignment doesn't have
    # hidden steps.
    assert len(all_args) == 1
    assert all_args[0][0] == assig2.auto_test.run
    assert assig3.auto_test.run.batch_run_done
    assert not assig1.auto_test.run.batch_run_done
    assert stub_clear.called

    assert stub_clear.all_args[0][0].work.assignment.id == assig2.id


@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.tar.gz'],
    indirect=True
)
def test_delete_submission(
    logged_in, assignment_real_works, session, monkeypatch,
    stub_function_class, describe
):
    assignment, submission = assignment_real_works
    passback = stub_function_class(lambda: True)
    monkeypatch.setattr(psef.lti.LTI, '_passback_grade', passback)

    with describe('deleting submission without lti should work'):
        t._delete_submission_1(submission['id'], assignment.id)

        assert not passback.called

    user_id = submission['user']['id']
    assignment.assignment_results[user_id] = m.AssignmentResult(
        sourcedid='wow', user_id=user_id
    )
    assignment.course.lti_provider = m.LTIProvider(key='my_lti')
    assignment.lti_outcome_service_url = 'http://aaa'
    session.commit()

    with describe('deleting newest submission'):
        t._delete_submission_1(submission['id'], assignment.id)

        assert len(passback.all_args) == 1
        assert passback.all_args[0]['grade'] is None
        passback.reset()

    with describe('deleting non newest should not delete grade'):
        session.add(m.Work(user_id=user_id, assignment=assignment))
        session.commit()

        t._delete_submission_1(submission['id'], assignment.id)
        assert not passback.called

    with describe('deleting in non existing assignment'):
        t._delete_submission_1(submission['id'], None)
        assert not passback.called

    with describe('deleting in non existing submissions'):
        t._delete_submission_1(-1, assignment.id)
        assert not passback.called


def test_notify_broker_kill_single_runner(
    describe, session, assignment, monkeypatch, stub_function_class
):
    with describe('setup'):
        test = m.AutoTest(
            setup_script='', run_setup_script='', assignment=assignment
        )
        run = m.AutoTestRun(
            _job_id=uuid.uuid4(), auto_test=test, batch_run_done=False
        )
        session.flush()
        session.add(run)
        runner = m.AutoTestRunner(
            _ipaddr='localhost', run=run, _job_id=run.get_job_id()
        )
        session.commit()

        ses = requests_stubs.Session()
        DESCRIBE_HOOKS.append(ses.reset)
        monkeypatch.setattr(psef.helpers, 'BrokerSession', lambda *_: ses)

    with describe('kill runner'):
        psef.tasks._notify_broker_kill_single_runner_1(run.id, runner.id.hex)
        call, = ses.calls
        assert call['method'] == 'delete'
        assert runner.job_id in call['args'][0]

    with describe('invalid run'):
        psef.tasks._notify_broker_kill_single_runner_1(-1, runner.id.hex)
        assert not ses.calls

    with describe('invalid runner'):
        psef.tasks._notify_broker_kill_single_runner_1(
            run.id,
            uuid.uuid4().hex
        )
        assert not ses.calls


def test_send_email_as_user(describe, session, stubmailer):
    with describe('setup'):
        user = helpers.create_user_with_perms(session, [], [])
        task_result = m.TaskResult(user)
        session.add(task_result)
        session.commit()

        task_result2 = m.TaskResult(user)
        session.add(task_result2)
        session.commit()

    with describe('can send the first time'):
        psef.tasks._send_email_as_user_1([user.id], 'd', 'b',
                                         task_result.id.hex, user.id)
        assert stubmailer.was_called
        assert m.TaskResult.query.get(
            task_result.id
        ).state == m.TaskResultState.finished

    with describe('Second call should not send'):
        psef.tasks._send_email_as_user_1([user.id], 'd', 'b',
                                         task_result.id.hex, user.id)
        assert not stubmailer.was_called
        assert m.TaskResult.query.get(
            task_result.id
        ).state == m.TaskResultState.finished

    with describe('Should not crash for non existing task id'):
        psef.tasks._send_email_as_user_1([user.id], 'd', 'b',
                                         uuid.uuid4().hex, user.id)
        assert not stubmailer.was_called
        assert m.TaskResult.query.get(
            task_result.id
        ).state == m.TaskResultState.finished

    with describe('task result should indicate failure when function crashes'):
        psef.tasks._send_email_as_user_1([user.id], 'd', 'b',
                                         task_result2.id.hex, -user.id)
        assert not stubmailer.was_called
        assert m.TaskResult.query.get(
            task_result2.id
        ).state == m.TaskResultState.crashed
