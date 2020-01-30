# SPDX-License-Identifier: AGPL-3.0-only
import re

import pytest

import psef.models as m
from helpers import create_marker
from psef.permissions import CoursePermission as CPerm

perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)
late_error = create_marker(pytest.mark.late_error)
only_own = create_marker(pytest.mark.only_own)


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student1'),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'data', [
        data_error('err'),
        data_error({}),
        data_error({'sr': 'err'}),
        data_error({'comment': 5}),
        {'comment': 'correct'},
        {'comment': '\0', 'expected_result': ''},
    ]
)
def test_add_feedback(
    named_user, request, logged_in, test_client, assignment_real_works,
    session, data, error_template, ta_user, teacher_user, monkeypatch_celery
):
    assignment, work = assignment_real_works
    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error') is not None

    code_id = session.query(m.File.id).filter(
        m.File.work_id == work['id'],
        m.File.parent != None,  # NOQA
        m.File.name != '__init__',
    ).first()[0]

    if perm_err:
        code = perm_err.kwargs['error']
    elif data_err:
        code = 400
    else:
        code = 204

    def get_result():
        if data_err or perm_err:
            return {}
        msg = data.get('expected_result', data['comment'])
        return {'0': {'line': 0, 'msg': msg, 'author': dict}}

    with logged_in(named_user):
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            code,
            data=data,
            result=None if code == 204 else error_template
        )

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'feedback'},
            result=get_result()
        )
        if not (data_error or perm_error):
            assert res['author']['id'] == named_user.id

    with logged_in(named_user):
        if not data_err:
            data['comment'] = 'bye'
            data['expected_result'] = 'bye'
            test_client.req(
                'put',
                f'/api/v1/code/{code_id}/comments/0',
                code,
                data=data,
                result=None if code == 204 else error_template
            )

    with logged_in(ta_user):
        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'feedback'},
            result=get_result()
        )

    with logged_in(teacher_user):
        test_client.req('delete', f'/api/v1/submissions/{work["id"]}', 204)

        # You cannot comment on deleted submissions
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            404,
            data=data,
            result=error_template,
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=403)('admin'),
        pytest.param(
            'Student1',
            marks=[
                pytest.mark.late_error,
                pytest.mark.list_error,
            ]
        ),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
def test_get_feedback(
    named_user, request, logged_in, test_client, assignment_real_works,
    session, error_template, ta_user
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

    with logged_in(ta_user):
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            204,
            data={'comment': 'for line 0'},
        )
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/1',
            204,
            data={'comment': 'for line - 1'},
        )

    with logged_in(named_user):
        code = perm_err.kwargs['error'] if perm_err else 200

        if perm_err:
            res = error_template
        elif late_err:
            res = {}
        else:
            res = {
                '0': {
                    'line': 0,
                    'msg': 'for line 0',
                    'author': dict,
                }, '1': {
                    'line': 1,
                    'msg': 'for line - 1',
                    'author': dict,
                }
            }
            if list_err:
                del res['0']['author']
                del res['1']['author']

        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            code,
            query={'type': 'feedback'},
            result=res
        )

    assig = session.query(m.Assignment).get(assig_id)
    assig.state = m._AssignmentStateEnum.done
    session.commit()

    with logged_in(named_user):
        code = perm_err.kwargs['error'] if perm_err else 200

        if perm_err:
            res = error_template
        else:
            res = {
                '0': {
                    'line': 0,
                    'msg': 'for line 0',
                    'author': dict,
                }, '1': {
                    'line': 1,
                    'msg': 'for line - 1',
                    'author': dict,
                }
            }
            if list_err:
                del res['0']['author']
                del res['1']['author']

        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            code,
            query={'type': 'feedback'},
            result=res
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize('named_user', ['Thomas Schaper'], indirect=True)
@pytest.mark.parametrize('perm_value', [True, False])
def test_can_see_user_feedback_before_done_permission(
    named_user, request, logged_in, test_client, assignment_real_works,
    session, error_template, ta_user, perm_value
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

    with logged_in(ta_user):
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            204,
            data={'comment': 'for line 0'},
        )
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/1',
            204,
            data={'comment': 'for line - 1'},
        )

    assignment.state = m._AssignmentStateEnum.open

    course = assignment.course
    course_users = course.get_all_users_in_course(include_test_students=False
                                                  ).all()
    course_role = next(r for u, r in course_users if u.id == named_user.id)

    course_role.set_permission(
        CPerm.can_see_user_feedback_before_done, perm_value
    )

    session.commit()

    with logged_in(named_user):
        if perm_value:
            res = {
                '0': {
                    'line': 0,
                    'msg': 'for line 0',
                    'author': dict,
                }, '1': {
                    'line': 1,
                    'msg': 'for line - 1',
                    'author': dict,
                }
            }
        else:
            res = {}

        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'feedback'},
            result=res
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=403)('admin'),
        perm_error(error=403)(('Student1')),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
def test_delete_feedback(
    named_user, request, logged_in, test_client, assignment_real_works,
    session, error_template, ta_user
):
    assignment, work = assignment_real_works
    perm_err = request.node.get_closest_marker('perm_error')

    code_id = session.query(m.File.id).filter(
        m.File.work_id == work['id'],
        m.File.parent != None,  # NOQA
        m.File.name != '__init__',
    ).first()[0]

    result = {
        '0': {
            'line': 0,
            'msg': 'for line 0',
            'author': dict,
        }, '1': {
            'line': 1,
            'msg': 'line1',
            'author': dict,
        }
    }

    with logged_in(ta_user):
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/1',
            204,
            data={'comment': 'line1'},
        )
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            204,
            data={'comment': 'for line 0'},
        )

        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'feedback'},
            result=result
        )

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/code/{code_id}/comments/0',
            perm_err.kwargs['error'] if perm_err else 204,
        )

    if not perm_err:
        result.pop('0')

    with logged_in(ta_user):
        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'feedback'},
            result=result
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=403)('admin'),
        pytest.param(
            'Student1',
            marks=[
                pytest.mark.late_error,
                pytest.mark.list_error,
            ]
        ),
    ],
    indirect=True
)
def test_get_all_feedback(
    named_user, request, logged_in, test_client, assignment_real_works,
    session, error_template, teacher_user, monkeypatch, monkeypatch_celery
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
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            204,
            data={'comment': 'for line 0'},
        )
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/1',
            204,
            data={'comment': 'for line - 1'},
        )

        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/linter',
            200,
            data={'name': 'Flake8', 'cfg': ''}
        )

    expected = re.compile(
        r'Assignment: TEST COURSE\n'
        r'Grade: \n'
        r'General feedback:\n'
        r'\n'
        r'\n'
        r'Comments:\n'
        r'test.py:1:1: for line 0\n'
        r'test.py:2:1: for line - 1\n'
        r'\nLinter comments:\n'
        r'(test.py:2:1: \(Flake8 .*\) .*\n)+\n*'
    )

    with logged_in(named_user):
        work_id = work['id']

        if perm_err:
            code = perm_err.kwargs['error']
        else:
            code = 200

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            code,
            result={'name': str, 'output_name': str}
            if code == 200 else error_template,
            query={'type': 'feedback'},
        )

        if not (late_err or perm_err):
            file_name = res['name']

            res = test_client.get(f'/api/v1/files/{file_name}')
            assert res.status_code == 200

            assert expected.match(res.data.decode('utf8'))

            res = test_client.get(f'/api/v1/files/{file_name}')
            assert res.status_code == 404

    assig = session.query(m.Assignment).get(assig_id)
    assig.state = m._AssignmentStateEnum.done
    session.commit()

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work["id"]}',
            perm_err.kwargs['error'] if perm_err else 200,
            result=error_template
            if perm_err else {'name': str, 'output_name': str},
            query={'type': 'feedback'}
        )

        if not perm_err:
            file_name = res['name']

            res = test_client.get(f'/api/v1/files/{file_name}')
            assert res.status_code == 200

            assert expected.match(res.data.decode('utf8'))

    with logged_in(named_user):
        if perm_err:
            out = {
                'general': '',
                'user': {},
                'linter': {},
                'authors': None,
            }
        else:
            out = {
                'user': dict,
                'general': str,
                'linter': dict,
                'authors': None,
            }
            if not list_err:
                out['authors'] = dict

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work["id"]}/feedbacks/',
            200,
            result=out,
        )

        if not perm_err:
            assert str(code_id) in res['user']
            assert res['user'][str(code_id)] == {
                '0': 'for line 0',
                '1': 'for line - 1',
            }
            assert str(code_id) in res['linter']
            assert '1' in res['linter'][str(code_id)]
            assert isinstance(res['linter'][str(code_id)]['1'], list)
            assert isinstance(res['linter'][str(code_id)]['1'][0], list)
            assert isinstance(res['linter'][str(code_id)]['1'][0][0], str)
            assert isinstance(res['linter'][str(code_id)]['1'][0][1], dict)


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=403)('admin'),
        only_own(('Student1')),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
def test_get_assignment_all_feedback(
    named_user, request, logged_in, test_client, assignment_real_works,
    session, error_template, ta_user, monkeypatch_celery, teacher_user
):
    assignment, work = assignment_real_works
    assig_id = assignment.id
    perm_err = request.node.get_closest_marker('perm_error')
    only_own_subs = request.node.get_closest_marker('only_own')

    code_id = session.query(m.File.id).filter(
        m.File.work_id == work['id'],
        m.File.parent != None,  # NOQA
        m.File.name != '__init__',
    ).first()[0]

    with logged_in(ta_user):
        res = test_client.req(
            'patch',
            f'/api/v1/submissions/{work["id"]}',
            200,
            data={'grade': 5, 'feedback': 'Niet zo goed\0'},
            result=dict
        )
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            204,
            data={'comment': 'for line 0'},
        )
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/1',
            204,
            data={'comment': 'for line - 1'},
        )

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/linter',
            200,
            data={'name': 'Flake8', 'cfg': ''}
        )

    def match_res(res):
        general = 'Niet zo goed'
        user = ['test.py:1:1: for line 0', 'test.py:2:1: for line - 1']
        assert len(res) == 1 if only_own_subs else 3
        linter = None

        for key, val in res.items():
            if key == str(work['id']):
                assert val['user'] == user
                assert val['general'] == general
                assert len(val['linter']) >= 1
            else:
                assert not val['user']
                assert val['general'] == ''
                assert len(val['linter']) >= 1

            if linter is None:
                linter = val['linter']
            else:
                assert linter == val['linter']

    with logged_in(named_user):
        if perm_err:
            code = perm_err.kwargs['error']
        else:
            code = 200

        if only_own_subs:
            ex_res = {
                str(work["id"]): {'user': [], 'linter': [], 'general': ''}
            }
        elif code == 200:
            ex_res = dict
        else:
            ex_res = error_template
        res = test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/feedbacks/',
            code,
            result=ex_res,
        )

        if not (perm_err or only_own_subs):
            match_res(res)

    assig = session.query(m.Assignment).get(assig_id)
    assig.state = m._AssignmentStateEnum.done
    session.commit()

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/feedbacks/',
            code,
            result=dict if code == 200 else error_template,
        )

        if not perm_err:
            match_res(res)
