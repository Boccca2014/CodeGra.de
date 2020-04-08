import re

import pytest

import psef
import helpers
import psef.models as m
from dotdict import dotdict
from helpers import get_id, create_marker
from psef.permissions import CoursePermission as CPerm

perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)
late_error = create_marker(pytest.mark.late_error)
only_own = create_marker(pytest.mark.only_own)


@pytest.fixture
def make_add_reply(session, test_client):
    def inner(work_id):
        code_id = session.query(m.File.id).filter(
            m.File.work_id == work_id,
            m.File.parent_id.isnot(None),
            m.File.name != '__init__',
        ).first()[0]

        def add_reply(txt, line=0, include_response=False, include_base=False):
            base = test_client.req(
                'post',
                '/api/v1/comments/',
                200,
                data={
                    'file_id': code_id,
                    'line': line,
                },
                result={
                    'id': int,
                    '__allow_extra__': True,
                }
            )

            res = test_client.req(
                'post',
                f'/api/v1/comments/{get_id(base)}/replies/',
                200,
                data={'comment': txt, 'reply_type': 'markdown'},
                result={
                    'id': int,
                    'reply_type': 'markdown',
                    'comment': txt,
                    '__allow_extra__': True,
                },
                include_response=include_response,
            )
            if include_base:
                base['replies'].append({**res})
                base['replies'][-1].pop('author')
                base['replies'][-1].pop('comment_base_id')
                res = (res, base)
            return res

        return add_reply

    yield inner


@pytest.fixture(autouse=True)
def mail_functions(
    monkeypatch, monkeypatch_celery, stub_function_class, make_function_spy
):
    send_mail = stub_function_class(lambda: None)
    monkeypatch.setattr(psef.mail, '_send_mail', send_mail)
    direct = make_function_spy(psef.mail, 'send_direct_notification_email')
    digest = make_function_spy(psef.mail, 'send_digest_notification_email')

    def any_mails():
        if direct.called:
            print('Direct emails send', direct.all_args, send_mail.all_args)
            return True
        elif digest.called:
            print('Digest emails send', digest.all_args, send_mail.all_args)
            return True
        return False

    def assert_mailed(user, amount=1):
        if amount > 0:
            assert any_mails() and send_mail.called, 'Nobody was mailed'

        user_id = helpers.get_id(user)
        user = m.User.query.get(user_id)
        assert user is not None, f'Given user {user_id} was not found'
        msgs = []

        for args in send_mail.all_args:
            recipients = args.get(2, args.get('recipients'))
            assert recipients, 'A mail was send to nobody'
            for recipient in recipients:
                if isinstance(recipient, tuple):
                    recipient = recipient[1]
                if recipient == user.email:
                    msgs.append(
                        dotdict(
                            msg=args.get(0, args.get('html_body')),
                            subject=args.get(0, args.get('subject')),
                            message_id=args.get('message_id'),
                            in_reply_to=args.get('in_reply_to'),
                            references=args.get('references'),
                        )
                    )
                    amount -= 1

        assert amount == 0, 'The given user was not mailed or mailed to much'
        return msgs

    yield dotdict(
        send_mail=send_mail,
        direct=direct,
        digest=digest,
        any_mails=any_mails,
        assert_mailed=assert_mailed,
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
    request, logged_in, test_client, session, data, error_template, admin_user,
    mail_functions, describe, tomorrow
):
    with describe('setup'), logged_in(admin_user):
        assignment = helpers.create_assignment(
            test_client, state='open', deadline=tomorrow
        )
        course = assignment['course']
        teacher = admin_user
        student = helpers.create_user_with_perms(
            session, [CPerm.can_submit_own_work], course
        )
        work = helpers.create_submission(
            test_client, assignment, for_user=student
        )

        data_err = request.node.get_closest_marker('data_error') is not None

        code_id = session.query(m.File.id).filter(
            m.File.work_id == work['id'],
            m.File.parent_id.isnot(None),
            m.File.name != '__init__',
        ).first()[0]

        if data_err:
            code = 400
        else:
            code = 204

        def get_result(has_author=True):
            if data_err:
                return {}
            msg = data.get('expected_result', data['comment'])
            res = {
                '0': {
                    'line': 0,
                    'msg': msg,
                    'author': {'id': teacher.id, '__allow_extra__': True},
                }
            }
            if not has_author:
                res['0'].pop('author')
            return res

    with describe('teacher can place comments'), logged_in(teacher):
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            code,
            data=data,
            result=None if code == 204 else error_template
        )
        if data_err:
            assert not mail_functions.any_mails()
            return
        assert not mail_functions.any_mails(), 'Student should not be mailed'

        res = test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'feedback'},
            result=get_result()
        )

        data = {
            'comment': 'bye',
            'expected_result': 'bye',
        }
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            code,
            data=data,
        )
        assert not mail_functions.any_mails(), 'No mails for updates'

        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'feedback'},
            result=get_result()
        )

    with describe(
        'Students cannot place comments if they do not have the permission'
    ), logged_in(student):
        test_client.req(
            'put', f'/api/v1/code/{code_id}/comments/1', 403, data=data
        )

    with describe('Students can get comments when assignment is done'):
        with logged_in(student):
            test_client.req(
                'get',
                f'/api/v1/code/{code_id}',
                200,
                query={'type': 'feedback'},
                result={},
            )

            # We don't have the permission to see the notification
            test_client.req(
                'get',
                '/api/v1/notifications/',
                200,
                result={'notifications': []}
            )
            test_client.req(
                'get',
                '/api/v1/notifications/?has_unread',
                200,
                result={'has_unread': False}
            )

        with logged_in(teacher):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment["id"]}',
                200,
                data={'state': 'done'},
            )
            assert not mail_functions.any_mails(), (
                'Should not send old notifications when state changes'
            )

        with logged_in(student):
            test_client.req(
                'get',
                f'/api/v1/code/{code_id}',
                200,
                query={'type': 'feedback'},
                result=get_result(has_author=False),
            )
            # Now we do have this permission
            test_client.req(
                'get',
                '/api/v1/notifications/',
                200,
                result={
                    'notifications': [{
                        'id': int,
                        'reasons': [['author', str]],
                        '__allow_extra__': True,
                        'read': False,
                        'file_id': code_id,
                    }]
                }
            )
            test_client.req(
                'get',
                '/api/v1/notifications/?has_unread',
                200,
                result={'has_unread': True}
            )

    with describe('Cannot get or update feedback after deleting submission'
                  ), logged_in(teacher):
        test_client.req('delete', f'/api/v1/submissions/{work["id"]}', 204)

        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            404,
            query={'type': 'feedback'},
            result=error_template,
        )
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/0',
            404,
            data={'comment': 'Any value'},
            result=error_template,
        )

    with describe('After delete notification should be gone'
                  ), logged_in(student):
        test_client.req(
            'get', '/api/v1/notifications/', 200, result={'notifications': []}
        )
        test_client.req(
            'get',
            '/api/v1/notifications/?has_unread',
            200,
            result={'has_unread': False}
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=403)('admin'),
        pytest.param('Student1', marks=[
            pytest.mark.late_error,
        ]),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
def test_get_feedback(
    named_user, request, logged_in, test_client, assignment_real_works,
    monkeypatch_celery, session, error_template, ta_user
):
    assignment, work = assignment_real_works
    assig_id = assignment.id
    perm_err = request.node.get_closest_marker('perm_error')
    late_err = request.node.get_closest_marker('late_error')

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
    monkeypatch_celery, session, error_template, teacher_user, perm_value
):
    assignment, work = assignment_real_works

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
    'named_user',
    [
        'Robin',
        perm_error(error=404)('admin'),  # not enrolled so 404 on getting com
        perm_error(error=403)(('Student1')),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
def test_delete_feedback(
    named_user, request, logged_in, test_client, assignment_real_works,
    monkeypatch_celery, session, error_template, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']
    perm_err = request.node.get_closest_marker('perm_error')

    code_id = session.query(m.File.id).filter(
        m.File.work_id == work_id,
        m.File.parent_id.isnot(None),
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

    feedbacks_result = {
        '__allow_extra__': True,
        'user': {str(code_id): {'0': 'for line 0', '1': 'line1'}},
    }

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{helpers.get_id(assignment)}',
            200,
            data={'state': 'done'},
        )
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

        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/feedbacks/',
            200,
            result=feedbacks_result,
        )

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/code/{code_id}/comments/0',
            perm_err.kwargs['error'] if perm_err else 204,
        )

    if not perm_err:
        result.pop('0')
        feedbacks_result['user'][str(code_id)].pop('0')

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/code/{code_id}',
            200,
            query={'type': 'feedback'},
            result=result
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/feedbacks/',
            200,
            result=feedbacks_result,
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
    if list_err:
        named_user.courses[assignment.course_id].set_permission(
            CPerm.can_view_feedback_author, False
        )
        session.commit()

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
                'authors': {},
            }
        else:
            out = {
                'user': dict,
                'general': str,
                'linter': dict,
                'authors': {},
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


def test_reply(
    logged_in, test_client, session, admin_user, mail_functions, describe,
    tomorrow, make_add_reply
):

    with describe('setup'), logged_in(admin_user):
        assignment = helpers.create_assignment(
            test_client, state='open', deadline=tomorrow
        )
        course = assignment['course']
        teacher = admin_user
        student = helpers.create_user_with_role(session, 'Student', course)

        work_id = helpers.get_id(
            helpers.create_submission(
                test_client, assignment, for_user=student
            )
        )

        add_reply = make_add_reply(work_id)

        feedback_url = f'/api/v1/submissions/{work_id}/feedbacks/?with_replies'

    with describe('Teachers can give feedback'), logged_in(teacher):
        _, rv = add_reply('base comment', include_response=True)
        assert 'Warning' not in rv.headers
        assert not mail_functions.any_mails(), (
            'Nobody should be emailed for the first reply'
        )

    with describe('Students may not see feedback by default'
                  ), logged_in(student):
        test_client.req(
            'get',
            feedback_url,
            200,
            result={'general': '', 'linter': {}, 'authors': [], 'user': []},
        )

    with describe('But students can place comments'), logged_in(student):
        add_reply('A reply')
        # The teacher should be mailed as a reply was posted
        mail_functions.assert_mailed(teacher, amount=1)
        # A direct mail should be send
        assert mail_functions.direct.called
        assert not mail_functions.digest.called

    with describe('Students may see own comments'), logged_in(student):
        test_client.req(
            'get',
            feedback_url,
            200,
            result={
                'general': '',
                'linter': {},
                'authors': [student],
                'user': [{
                    '__allow_extra__': True,
                    'replies': [{
                        'comment': 'A reply', '__allow_extra__': True
                    }],
                }],
            },
        )

    with describe('Teacher may see all comments'), logged_in(teacher):
        test_client.req(
            'get',
            feedback_url,
            200,
            result={
                'general': '',
                'linter': {},
                'authors': [student, teacher],
                'user': [{
                    '__allow_extra__': True,
                    'replies': [{
                        'comment': 'base comment', '__allow_extra__': True
                    }, {'comment': 'A reply', '__allow_extra__': True}],
                }],
            },
        )

    with describe('A teacher can reply and should get a warning'
                  ), logged_in(teacher):
        _, rv = add_reply('another comment', include_response=True)
        assert 'Warning' in rv.headers
        assert 'have sufficient permissions' in rv.headers['Warning']


def test_delete_feedback(
    logged_in, test_client, session, admin_user, mail_functions, describe,
    tomorrow, make_add_reply
):
    with describe('setup'), logged_in(admin_user):
        assignment = helpers.create_assignment(
            test_client, state='open', deadline=tomorrow
        )
        course = assignment['course']
        teacher = admin_user
        student = helpers.create_user_with_role(session, 'Student', course)
        ta = helpers.create_user_with_role(session, 'TA', course)

        work_id = helpers.get_id(
            helpers.create_submission(
                test_client, assignment, for_user=student
            )
        )

        add_reply = make_add_reply(work_id)
        feedback_url = f'/api/v1/submissions/{work_id}/feedbacks/?with_replies'

    with describe('Users can delete own replies'):
        for user in [teacher, student, ta]:
            with logged_in(user):
                reply = add_reply('a reply')
                test_client.req(
                    'delete', (
                        f'/api/v1/comments/{reply["comment_base_id"]}/'
                        f'replies/{reply["id"]}'
                    ), 204
                )
                with logged_in(teacher):
                    test_client.req(
                        'get',
                        feedback_url,
                        200,
                        result={
                            'general': '', 'linter': {}, 'authors': [],
                            'user': []
                        },
                    )

    with describe('Only teachers can delete replies of others'):
        with logged_in(student):
            reply, base = add_reply('a reply', include_base=True)
        with logged_in(ta):
            test_client.req(
                'delete', (
                    f'/api/v1/comments/{reply["comment_base_id"]}/'
                    f'replies/{reply["id"]}'
                ), 403
            )
        with logged_in(teacher):
            test_client.req(
                'get',
                feedback_url,
                200,
                result={
                    'general': '', 'linter': {}, 'authors': [student],
                    'user': [base]
                },
            )

        with logged_in(teacher):
            test_client.req(
                'delete', (
                    f'/api/v1/comments/{reply["comment_base_id"]}/'
                    f'replies/{reply["id"]}'
                ), 204
            )
            test_client.req(
                'get',
                feedback_url,
                200,
                result={
                    'general': '', 'linter': {}, 'authors': [], 'user': []
                },
            )

    with describe('Cannot delete a reply twice'), logged_in(student):
        reply = add_reply('To delete')
        test_client.req(
            'delete', (
                f'/api/v1/comments/{reply["comment_base_id"]}/'
                f'replies/{reply["id"]}'
            ), 204
        )
        test_client.req(
            'delete', (
                f'/api/v1/comments/{reply["comment_base_id"]}/'
                f'replies/{reply["id"]}'
            ), 404
        )
