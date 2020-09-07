# SPDX-License-Identifier: AGPL-3.0-only
"""Here be dragons, watch out!
"""
import os
import copy
import time
import datetime
from random import shuffle

import pytest
from werkzeug.local import LocalProxy

import psef
import psef.models as m
import psef.features as feats
from helpers import create_marker
from psef.permissions import CoursePermission as CPerm

run_error = create_marker(pytest.mark.run_error)
perm_error = create_marker(pytest.mark.perm_error)
get_works = create_marker(pytest.mark.get_works)

ALL_LINTERS = sorted([
    'Flake8', 'MixedWhitespace', 'Pylint', 'Checkstyle', 'PMD', 'ESLint'
])

CHECKSTYLE_INVALID_EL = open(
    os.path.join(
        os.path.dirname(__file__), '..', 'test_data', 'test_linter',
        'checkstyle_invalid_el.xml'
    )
).read()
CHECKSTYLE_INVALID_MODULE = open(
    os.path.join(
        os.path.dirname(__file__), '..', 'test_data', 'test_linter',
        'checkstyle_invalid_module.xml'
    )
).read()
CHECKSTYLE_INVALID_PROP_WITH_CHILDREN = open(
    os.path.join(
        os.path.dirname(__file__), '..', 'test_data', 'test_linter',
        'checkstyle_invalid_prop_with_children.xml'
    )
).read()
CHECKSTYLE_INVALID_PROPS = open(
    os.path.join(
        os.path.dirname(__file__), '..', 'test_data', 'test_linter',
        'checkstyle_invalid_props.xml'
    )
).read()
CHECKSTYLE_GOOGLE = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'resources',
        'checkstyle',
        'google.xml',
    )
).read()

PMD_XPATH = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'test_data',
        'test_linter',
        'pmd_xpath.xml',
    )
).read()
PMD_MAVEN = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'resources',
        'pmd',
        'maven.xml',
    )
).read()

ESLINT_INVALID_PLUGIN = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'test_data',
        'test_linter',
        'eslint_invalid_plugin.json',
    )
).read()
ESLINT_INVALID_JSON = "'"
ESLINT_INVALID_EXTENDS = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'test_data',
        'test_linter',
        'eslint_invalid_extends.json',
    )
).read()
ESLINT_UNKNOWN_ECMA = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'test_data',
        'test_linter',
        'eslint_unknown_ecma.json',
    )
).read()
ESLINT_EXTENDS_STANDARD = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'test_data',
        'test_linter',
        'eslint_extends_standard.json',
    )
).read()
ESLINT_STANDARD = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'resources',
        'eslint',
        'standard.json',
    )
).read()


@pytest.mark.parametrize(
    'filename,linter_cfgs_exp',
    [
        (
            'test_flake8.tar.gz', [(
                'Flake8', '', [
                    (1, 'W191'),
                    (1, 'E211'),
                    (1, 'E201'),
                    (1, 'E202'),
                ]
            )]
        ),
        run_error(error=400)(('test_flake8.tar.gz', [(6, '666', '')])),
        run_error(error=400)(('test_flake8.tar.gz', [('Flake8', False, '')])),
        run_error(crash='Pylint')(
            ('test_flake8.tar.gz', [('Pylint', '[MASTER]\njobs=-1', '')])
        ),
        run_error(crash='Flake8')((
            'test_flake8.tar.gz', [(
                'Flake8', '[flake8]\ndisable_noqa=Trues # This should crash',
                ''
            )]
        )),
        run_error(error=400)(
            ('test_checkstyle.tar.gz', [('Checkstyle', 'not xml', '')])
        ),
        run_error(error=400)((
            'test_checkstyle.tar.gz',
            [('Checkstyle', '<?xml version="1.0"?><module/>', '')]
        )),
        run_error(error=400
                  )(('test_checkstyle.tar.gz', [('PMD', 'NOT XML!', '')])),
        run_error(error=400
                  )(('test_checkstyle.tar.gz', [('PMD', PMD_XPATH, '')])),
        *[
            run_error(error=400
                      )(('test_checkstyle.tar.gz', [('Checkstyle', cfg, '')]))
            for cfg in [
                CHECKSTYLE_INVALID_EL, CHECKSTYLE_INVALID_MODULE,
                CHECKSTYLE_INVALID_PROP_WITH_CHILDREN, CHECKSTYLE_INVALID_PROPS
            ]
        ],
        (
            'test_pmd.tar.gz', [(
                'PMD', PMD_MAVEN, [
                    (14, 'Error Prone'),
                    (16, 'Error Prone'),
                    (18, 'Best Practices'),
                    (18, 'Design'),
                ]
            )]
        ),
        (
            'test_checkstyle.tar.gz', [(
                'Checkstyle', CHECKSTYLE_GOOGLE, [
                    (13, 'warning'),
                    (13, 'warning'),
                    (14, 'warning'),
                    (15, 'warning'),
                    (16, 'warning'),
                    (17, 'warning'),
                    (18, 'warning'),
                    (19, 'warning'),
                    (20, 'warning'),
                ]
            )]
        ),
        run_error(crash='Checkstyle')
        (('test_invalid_java.tar.gz', [('Checkstyle', CHECKSTYLE_GOOGLE, [])])
         ),
        (
            'test_pylint.tar.gz', [(
                'Pylint', '', [
                    (0, 'C0114'),
                    (0, 'C0103'),
                    (0, 'C0103'),
                    (0, 'C0116'),
                    (0, 'W0613'),
                    (1, 'W0311'),
                ]
            )]
        ),
        run_error(crash='Pylint')(('test_flake8.tar.gz', [('Pylint', '', [])])
                                  ),
        run_error(crash='Pylint')((
            'test_flake8.tar.gz', [('Pylint', '', []),
                                   (
                                       'Flake8', '', [
                                           (1, 'W191'),
                                           (1, 'E211'),
                                           (1, 'E201'),
                                           (1, 'E202'),
                                       ]
                                   )]
        )),
        *[
            run_error(error=400)(('test_eslint.tar.gz', [('ESLint', cfg, '')]))
            for cfg in [
                ESLINT_INVALID_EXTENDS, ESLINT_INVALID_JSON,
                ESLINT_INVALID_PLUGIN
            ]
        ],
        *[(
            'test_eslint.tar.gz', [(
                'ESLint', cfg, [
                    (15, 'comma-dangle'),
                    (185, 'semi'),
                    (204, 'indent'),
                    (224, 'comma-dangle'),
                    (330, 'no-undef'),
                ]
            )]
        ) for cfg in [ESLINT_STANDARD, ESLINT_EXTENDS_STANDARD]],
        run_error(crash='ESLint'
                  )(('test_flake8.tar.gz', [('ESLint', ESLINT_STANDARD, [])])),
        run_error(crash='ESLint')(
            ('test_eslint.tar.gz', [('ESLint', ESLINT_UNKNOWN_ECMA, [])])
        ),
    ],
    indirect=['filename'],
)
def test_linters(
    teacher_user, test_client, logged_in, assignment_real_works,
    linter_cfgs_exp, request, error_template, session, monkeypatch_celery
):
    assignment, single_work = assignment_real_works
    assig_id = assignment.id
    del assignment
    run_err = request.node.get_closest_marker('run_error')

    if run_err:
        run_err = copy.deepcopy(run_err.kwargs)
    else:
        run_err = {}

    with logged_in(teacher_user):
        for linter, cfg, _ in linter_cfgs_exp:
            data = {}
            if linter != False:  # NOQA
                data['name'] = linter
            if cfg != False:  # NOQA
                data['cfg'] = cfg

            code = run_err.get('error') or 200

            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assig_id}/linter',
                code,
                data=data,
                result=error_template if run_err.get('error') else {
                    'done': int,
                    'working': int,
                    'id': str,
                    'crashed': int,
                    'name': linter,
                }
            )

            if not run_err.get('error'):
                linter_id = res['id']
                for _ in range(60):
                    res = test_client.req(
                        'get',
                        f'/api/v1/linters/{linter_id}',
                        code,
                        data=data,
                        result=error_template if run_err.get('error') else dict
                    )
                    print(run_err.get('crash'), linter, res)
                    if run_err.get('crash') == linter and res['crashed'] == 3:
                        assert res['done'] == 0
                        assert res['working'] == 0
                        break
                    elif res['done'] == 3:
                        assert res['crashed'] == 0
                        assert res['working'] == 0
                        break
                    time.sleep(0.1)
                else:
                    assert False

        result = []
        for linter in ALL_LINTERS:
            tried_linter = [
                True for lint in linter_cfgs_exp if lint[0] == linter
            ]
            item = {
                'name': linter,
                'desc': str,
                'opts': dict,
            }
            if run_err.get('crash') == linter:
                item['state'] = 'crashed'
                item['id'] = str
            elif not run_err.get('error') and tried_linter:
                item['state'] = 'done'
                item['id'] = str
            else:
                item['state'] = 'new'

            result.append(item)

        linter_result = test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/linters/',
            200,
            result=result,
        )

        for linter in linter_result:
            if [True for lint in linter_cfgs_exp if lint[0] == linter['name']]:
                if 'id' not in linter:
                    assert run_err.get('crash') != linter['name']
                    continue
                lname = linter['name']
                test_client.req(
                    'get',
                    f'/api/v1/linters/{linter["id"]}',
                    200,
                    result={
                        'name': linter['name'],
                        'done': 0 if run_err.get('crash') == lname else 3,
                        'working': 0,
                        'id': str,
                        'crashed': 3 if run_err.get('crash') == lname else 0,
                    }
                )

    with logged_in(teacher_user):
        code_id = session.query(m.File.id).filter(
            m.File.work_id == single_work['id'],
            m.File.parent != None,  # NOQA
            m.File.name != '__init__.py',
        ).first()[0]

        linters = {}
        for linter, _, exp in linter_cfgs_exp:
            linters[linter] = list(exp)

        res = sorted(
            test_client.req(
                'get',
                f'/api/v1/code/{code_id}',
                200,
                query={'type': 'linter-feedback'},
            ).items(),
            key=lambda el: el[0]
        )

        try:
            for _, feedbacks in res:
                for name, linter_comm in feedbacks:
                    val = linters[name].pop(0)
                    assert val[0] == linter_comm['line']
                    assert val[1] == linter_comm['code']
        except:
            print(res)
            raise

        assert not any(linters.values())

        for linter in linter_result:
            if 'id' not in linter:
                continue

            test_client.req(
                'delete',
                f'/api/v1/linters/{linter["id"]}',
                204,
            )
            test_client.req(
                'get',
                f'/api/v1/linters/{linter["id"]}',
                404,
                result=error_template
            )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_linters_permissions(
    teacher_user, student_user, test_client, logged_in, assignment_real_works,
    request, error_template, session, monkeypatch_celery
):
    assignment, single_work = assignment_real_works
    linter, cfgs = 'Flake8', ''
    student_user2 = LocalProxy(
        session.query(m.User).filter_by(name="Student2").one
    )
    data = {'name': linter, 'cfg': cfgs}
    assig_id = assignment.id

    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/linter',
            403,
            data=data,
            result=error_template,
        )
    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/linter',
            200,
            data=data,
        )
    with logged_in(student_user):
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/linters/',
            403,
            result=error_template,
        )

    code_id = session.query(m.File.id).filter(
        m.File.work_id == single_work['id'],
        m.File.parent != None,  # NOQA
        m.File.name != '__init__.py',
    ).first()[0]
    with logged_in(student_user):
        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'linter-feedback'},
        )
    with logged_in(student_user2):
        # Other student cannot view linter feedback
        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            403,
            query={'type': 'linter-feedback'},
        )

    with logged_in(teacher_user):
        linter_result = test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/linters/',
            200,
        )
    assert any('id' in l for l in linter_result)

    with logged_in(student_user):
        for linter in linter_result:
            if 'id' not in linter:
                continue
            test_client.req(
                'delete',
                f'/api/v1/linters/{linter["id"]}',
                403,
                result=error_template,
            )
    with logged_in(teacher_user):
        for linter in linter_result:
            if 'id' not in linter:
                continue
            test_client.req(
                'get',
                f'/api/v1/linters/{linter["id"]}',
                200,
            )


@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_whitespace_linter(
    teacher_user, test_client, assignment, logged_in, monkeypatch
):
    called = False

    def patch(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(psef.tasks, 'lint_instances', patch)

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/linter',
            200,
            data={'name': 'MixedWhitespace', 'cfg': 'ANY'},
            result={
                'done': 4,
                'working': 0,
                'id': str,
                'crashed': 0,
                'name': 'MixedWhitespace',
            }
        )
        res = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )
        assert not called
        assert res
        assert res['whitespace_linter']


@pytest.mark.parametrize(
    'filename,exps',
    [
        ('test_flake8.tar.gz', ['W191', 'E211', 'E201', 'E202']),
    ],
)
def test_lint_later_submission(
    test_client, logged_in, assignment, exps, error_template, session,
    filename, teacher_user, student_user, monkeypatch_celery
):
    assig_id = assignment.id

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/linter',
            200,
            data={'name': 'Flake8', 'cfg': ''},
            result={
                'done': 0,
                'working': 0,
                'id': str,
                'crashed': 0,
                'name': 'Flake8',
            }
        )

    with logged_in(student_user):
        single_work = test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/submission',
            201,
            real_data={
                'file': (
                    f'{os.path.dirname(__file__)}/../'
                    f'test_data/test_linter/{filename}', filename
                )
            }
        )

    with logged_in(teacher_user):
        code_id = session.query(m.File.id).filter(
            m.File.work_id == single_work['id'],
            m.File.parent != None,  # NOQA
            m.File.name != '__init__.py',
        ).first()[0]

        res = sorted(
            test_client.req(
                'get',
                f'/api/v1/code/{code_id}',
                200,
                query={'type': 'linter-feedback'},
            ).items(),
            key=lambda el: el[0]
        )

        assert res

        for _, feedbacks in res:
            for name, linter_comm in feedbacks:
                assert exps.pop(0) == linter_comm['code']

        assert not exps


@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_already_running_linter(
    teacher_user, test_client, assignment, logged_in, error_template,
    monkeypatch
):
    called = False

    def patch(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(psef.tasks, 'lint_instances', patch)

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/linter',
            200,
            data={'name': 'Flake8', 'cfg': 'ANY'},
            result={
                'done': 0,
                'working': 4,
                'id': str,
                'crashed': 0,
                'name': 'Flake8',
            }
        )
        assert called

        res = test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/linters/',
            200,
        )
        found = 0

        for r in res:
            if r['name'] == 'Flake8':
                found += 1
                assert r['state'] == 'running'
        assert found == 1

        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/linter',
            409,
            data={'name': 'Flake8', 'cfg': 'ANY'},
            result=error_template,
        )


@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_non_existing_linter(
    teacher_user, test_client, assignment, logged_in, error_template
):
    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/linter',
            404,
            data={'name': 'NON_EXISTING', 'cfg': 'ERROR'},
            result=error_template
        )


@pytest.mark.parametrize(
    'filename,exps',
    [
        ('test_flake8.tar.gz', ['W191', 'E211', 'E201', 'E202']),
    ],
)
def test_lint_later_submission_disabled_linters(
    test_client, logged_in, assignment, exps, error_template, session,
    filename, ta_user, student_user, monkeypatch_celery, teacher_user,
    monkeypatch, app
):
    assig_id = assignment.id

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/linter',
            200,
            data={'name': 'Flake8', 'cfg': ''},
            result={
                'done': 0,
                'working': 0,
                'id': str,
                'crashed': 0,
                'name': 'Flake8',
            }
        )

    monkeypatch.setitem(app.config['FEATURES'], feats.Feature.LINTERS, False)

    with logged_in(student_user):
        single_work = test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/submission',
            201,
            real_data={
                'file': (
                    f'{os.path.dirname(__file__)}/../'
                    f'test_data/test_linter/{filename}', filename
                )
            }
        )

    with logged_in(ta_user):
        code_id = session.query(m.File.id).filter(
            m.File.work_id == single_work['id'],
            m.File.parent != None,  # NOQA
            m.File.name != '__init__.py',
        ).first()[0]

        comments = session.query(m.LinterComment).filter_by(
            file_id=code_id,
        ).all()

        assert not comments, "Make sure linter did not run"


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_detail_of_linter(
    teacher_user, student_user, test_client, logged_in, assignment_real_works,
    request, error_template, session, monkeypatch_celery, monkeypatch
):
    assignment, single_work = assignment_real_works
    assig_id = assignment.id

    def error_run(*_, **__):
        raise ValueError

    monkeypatch.setattr(psef.linters.PMD, 'run', error_run)
    monkeypatch.setattr(
        psef.linters.PMD, 'validate_config', lambda *_, **__: None
    )

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/linter',
            200,
            data={'name': 'Pylint', 'cfg': ''},
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/linter',
            200,
            data={'name': 'PMD', 'cfg': ''},
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/linter',
            200,
            data={'name': 'Flake8', 'cfg': ''},
        )
        linter_result = test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/linters/',
            200,
        )
        pylint_seen = False
        for linter in linter_result:
            if 'id' not in linter:
                continue
            result = test_client.req(
                'get',
                f'/api/v1/linters/{linter["id"]}?extended',
                200,
                result={
                    'id': str,
                    'name': str,
                    'tests': list,
                }
            )
            if result['name'] == 'Pylint':
                pylint_seen = True
                assert all(t['state'] == 'crashed' for t in result['tests'])
                with logged_in(student_user):
                    test_client.req(
                        'get',
                        (
                            f'/api/v1/linters/{linter["id"]}/linter_instances/'
                            f'{result["tests"][0]["id"]}'
                        ),
                        403,
                        result=error_template,
                    )

                inst = test_client.req(
                    'get', (
                        f'/api/v1/linters/{linter["id"]}/linter_instances/'
                        f'{result["tests"][0]["id"]}'
                    ),
                    200,
                    result={
                        'id': str,
                        'state': 'crashed',
                        'work': dict,
                        'error_summary': str,
                        'stdout': str,
                        'stderr': str,
                    }
                )
                assert '`__init__`' in inst['error_summary']
            else:
                inst = test_client.req(
                    'get', (
                        f'/api/v1/linters/{linter["id"]}/linter_instances/'
                        f'{result["tests"][0]["id"]}'
                    ),
                    200,
                    result={
                        'id': str,
                        'state': str,
                        'work': dict,
                        'error_summary': str,
                        '__allow_extra__': True,
                    }
                )
                assert 'stdout' in inst
                assert 'stderr' in inst
                assert (result['name'] == 'PMD'
                        ) == (inst['state'] == 'crashed')
                assert bool(inst['error_summary']
                            ) == (inst['state'] == 'crashed')

        assert pylint_seen


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize('named_user', ['Thomas Schaper'], indirect=True)
@pytest.mark.parametrize('perm_value', [True, False])
def test_can_see_linter_feedback_before_done(
    named_user, request, logged_in, test_client, assignment_real_works,
    session, teacher_user, perm_value, monkeypatch_celery
):
    assignment, work = assignment_real_works
    assig_id = assignment.id
    perm_err = request.node.get_closest_marker('perm_error')
    late_err = request.node.get_closest_marker('late_error')
    list_err = request.node.get_closest_marker('list_error')

    code_id = session.query(m.File.id).filter(
        m.File.work_id == work['id'],
        m.File.parent != None,  # NOQA
        m.File.name != '__init__',
    ).first()[0]

    with logged_in(teacher_user):
        data = {'name': 'Flake8', 'cfg': ''}
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/linter',
            200,
            data=data,
        )

        linter_id = res['id']
        for i in range(60):
            res = test_client.req(
                'get',
                f'/api/v1/linters/{linter_id}',
                200,
                data=data,
            )
            if res['done'] == 3:
                assert res['crashed'] == 0
                assert res['working'] == 0
                break
            time.sleep(0.1)
        else:
            assert False

    assignment.state = m.AssignmentStateEnum.open

    course = assignment.course
    course_users = course.get_all_users_in_course(include_test_students=False
                                                  ).all()
    course_role = next(r for u, r in course_users if u.id == named_user.id)

    course_role.set_permission(
        CPerm.can_see_linter_feedback_before_done, perm_value
    )

    session.commit()

    with logged_in(named_user):
        if perm_value:
            res = {'1': list}
        else:
            res = {}

        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'linter-feedback'},
            result=res
        )
