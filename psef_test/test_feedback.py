import re

import pytest
from freezegun import freeze_time

import psef
import helpers
import cg_dt_utils
import psef.models as m
from dotdict import dotdict
from helpers import get_id, dict_without, create_marker
from psef.permissions import CoursePermission as CPerm

perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)
late_error = create_marker(pytest.mark.late_error)
only_own = create_marker(pytest.mark.only_own)


@pytest.fixture
def make_add_reply(session, test_client, error_template, mail_functions):
    class Reply(dict):
        def get_url(self):
            return (
                f'/api/v1/comments/{self["comment_base_id"]}/'
                f'replies/{self["id"]}'
            )

        def delete(self):
            test_client.req('delete', self.get_url(), 204)

        def set_approval(self, approved: bool, *, err=False):
            result = error_template if err else {
                **self,
                'approved': approved,
            }
            res = test_client.req(
                'post' if approved else 'delete',
                f'{self.get_url()}/approval',
                err or 200,
                result=result
            )
            if err:
                return res
            return Reply(res)

        def update(self, new_text, now=None, *, approved=None, err=False):
            if now is None:
                now = cg_dt_utils.DatetimeWithTimezone.utcnow()
            if approved is None:
                approved = self['approved']

            with freeze_time(now):
                res = test_client.req(
                    'patch',
                    self.get_url(),
                    err or 200,
                    data={'comment': new_text},
                    result=error_template if err else {
                        **self,
                        'comment': new_text,
                        'last_edit': now.isoformat(),
                        'approved': approved,
                    },
                )
                if not err:
                    return Reply(res)
                return res

    def inner(work_id):
        code_id = session.query(m.File.id).filter(
            m.File.work_id == get_id(work_id),
            m.File.parent_id.isnot(None),
            m.File.name != '__init__',
        ).first()[0]

        def add_reply(
            txt,
            line=0,
            include_response=False,
            include_base=False,
            in_reply_to=None,
            expect_error=False,
            expect_peer_feedback=False,
            base_id=None
        ):
            in_reply_to_id = in_reply_to and get_id(in_reply_to)
            base = base_id or test_client.req(
                'put',
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

            res, rv = test_client.req(
                'post',
                f'/api/v1/comments/{get_id(base)}/replies/',
                expect_error or 200,
                data={
                    'comment': txt,
                    'reply_type': 'markdown',
                    'in_reply_to': in_reply_to_id,
                },
                result=error_template if expect_error else {
                    'id': int,
                    'reply_type': 'markdown',
                    'comment': txt,
                    'in_reply_to_id': in_reply_to_id,
                    'last_edit': None,
                    'comment_base_id': get_id(base),
                    'comment_type': (
                        'peer_feedback' if expect_peer_feedback else 'normal'
                    ),
                    '__allow_extra__': True,
                },
                include_response=True,
            )
            if expect_error:
                return (res, rv) if include_response else res
            reply = Reply(res)
            result = (reply, rv) if include_response else reply

            if include_base:
                base['replies'].append({**res})
                base['replies'][-1].pop('author')
                result = (result, base)

            return result

        return add_reply

    yield inner


@pytest.fixture(autouse=True)
def mail_functions(
    monkeypatch, monkeypatch_celery, make_function_spy, stubmailer
):

    direct = make_function_spy(psef.mail, 'send_direct_notification_email')
    digest = make_function_spy(psef.mail, 'send_digest_notification_email')

    def any_mails():
        if direct.called:
            print('Direct emails send', direct.all_args, stubmailer.args)
            return True
        elif digest.called:
            print('Digest emails send', digest.all_args, stubmailer.args)
            return True
        return False

    def assert_mailed(user, amount=1):
        if amount > 0:
            assert any_mails() and len(stubmailer.args
                                       ) > 0, ('Nobody was mailed')

        user_id = helpers.get_id(user)
        user = m.User.query.get(user_id)
        assert user is not None, f'Given user {user_id} was not found'
        msgs = []

        for arg, in stubmailer.args:
            message = arg._message()
            recipients = message['To'].split(', ')
            assert recipients, 'A mail was send to nobody'
            for recipient in recipients:
                print(recipient)
                if '<{}>'.format(user.email) in recipient:
                    msgs.append(
                        dotdict(
                            orig=message,
                            msg=arg.html,
                            subject=message['Subject'],
                            message_id=message['Message-ID'],
                            in_reply_to=message['In-Reply-To'],
                            references=(
                                message['References'] and
                                message['References'].split(' ')
                            ),
                        )
                    )
                    amount -= 1

        assert amount == 0, 'The given user was not mailed or mailed to much'
        return msgs

    yield dotdict(
        send_mail=stubmailer,
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
    assig.state = m.AssignmentStateEnum.done
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

    assignment.state = m.AssignmentStateEnum.open

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
    student_user = m.User.query.get(work['user']['id'])
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

    general_feedback = 'general feedback'

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work["id"]}',
            200,
            data={'feedback': general_feedback},
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
        rf'{general_feedback}\n'
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
    assig.state = m.AssignmentStateEnum.done
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

    perm_err_out = {
        'general': '',
        'user': {},
        'linter': {},
        'authors': {},
    }
    no_perm_err_out = {
        'user': {str(code_id): {
                     '0': 'for line 0',
                     '1': 'for line - 1',
                 }},
        'general': general_feedback,
        'linter': {
            str(code_id): {
                '1': [
                    [str, dict],
                    [str, dict],
                    [str, dict],
                    [str, dict],
                ]
            }
        },
        'authors': {str(code_id): {
                        '0': teacher_user,
                        '1': teacher_user,
                    }},
    }

    with logged_in(named_user):
        if perm_err:
            out = perm_err_out
        elif list_err:
            out = {**no_perm_err_out, 'authors': {}}
        else:
            out = no_perm_err_out

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work["id"]}/feedbacks/',
            code,
            result=out if code == 200 else error_template,
        )

    with logged_in(student_user):
        assig = session.query(m.Assignment).get(assig_id)
        assig.state = m.AssignmentStateEnum.open
        session.commit()
        assert not assig.is_done

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work["id"]}/feedbacks/',
            200,
            result=perm_err_out,
        )


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

    def match_res(res, only_own_subs=only_own_subs):
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
    assig.state = m.AssignmentStateEnum.done
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

    with logged_in(
        helpers.create_user_with_perms(
            session, [CPerm.can_see_others_work, CPerm.can_see_assignments],
            assig.course
        )
    ):
        res = test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/feedbacks/',
            200,
            result=dict,
        )

        if not perm_err:

            match_res(res, only_own_subs=False)


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
                    'general': '',
                    'linter': {},
                    'authors': [student],
                    'user': [base],
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


def test_edit_feedback(
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
        with logged_in(student):
            reply = add_reply('a reply')
        reply_url = (
            f'/api/v1/comments/{reply["comment_base_id"]}/'
            f'replies/{reply["id"]}'
        )

    with describe('Editing with the same content does not create an edit'
                  ), logged_in(teacher):
        test_client.req('patch', reply_url, 200, data={'comment': 'a reply'})
        test_client.req(
            'get',
            feedback_url,
            200,
            result={
                '__allow_extra__': True, 'user': [{
                    '__allow_extra__': True,
                    'replies': [{
                        'id': reply['id'],
                        'comment': 'a reply',
                        'last_edit': None,
                        '__allow_extra__': True,
                    }],
                }]
            },
        )
    with describe('teachers and own user can edit reply'):
        with logged_in(student):
            test_client.req(
                'patch', reply_url, 200, data={'comment': 'updated1'}
            )
        with logged_in(teacher):
            test_client.req(
                'patch', reply_url, 200, data={'comment': 'updated2'}
            )
        with logged_in(ta):
            test_client.req(
                'patch', reply_url, 403, data={'comment': 'updated3'}
            )

        with logged_in(teacher):
            test_client.req(
                'get',
                feedback_url,
                200,
                result={
                    'general': '', 'linter': {}, 'authors': [student],
                    'user': [{
                        '__allow_extra__': True,
                        'replies': [{
                            'id': reply['id'],
                            'comment': 'updated2',
                            'last_edit': str,
                            '__allow_extra__': True,
                        }],
                    }]
                },
            )

    with describe('Students can only see own edits'):
        with logged_in(teacher):
            other_reply = add_reply('A reply jooo')
            other_reply_url = (
                f'/api/v1/comments/{other_reply["comment_base_id"]}/'
                f'replies/{other_reply["id"]}'
            )

        with logged_in(student):
            edits = test_client.req(
                'get',
                reply_url + '/edits/',
                200,
                result=[
                    {
                        'id': int,
                        'old_text': 'updated1',
                        'created_at': str,
                        'new_text': 'updated2',
                        'editor': teacher,
                    },
                    {
                        'id': int,
                        'old_text': 'a reply',
                        'created_at': str,
                        'new_text': 'updated1',
                        'editor': student,
                    },
                ]
            )

            test_client.req('get', other_reply_url + '/edits/', 403)

    with describe('teachers can see others edits'), logged_in(teacher):
        test_client.req('get', reply_url + '/edits/', 200, result=edits)
        test_client.req('get', other_reply_url + '/edits/', 200, result=[])

    with describe('last_edit should really be the last edit'
                  ), logged_in(student):
        last_edit = test_client.req('get', feedback_url,
                                    200)['user'][0]['replies'][0]['last_edit']

        now = cg_dt_utils.DatetimeWithTimezone.utcnow()
        with freeze_time(now):
            test_client.req(
                'patch', reply_url, 200, data={'comment': 'updated4'}
            )

        new_last_edit = test_client.req('get', feedback_url, 200
                                        )['user'][0]['replies'][0]['last_edit']
        assert new_last_edit > last_edit
        assert new_last_edit == now.isoformat()


def test_reply_to_a_comment(
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
        with logged_in(student):
            reply = add_reply('a reply')

    with describe('You set the in_reply_to of a comment'), logged_in(teacher):
        add_reply('a reply to', in_reply_to=reply)

    with describe('You cannot reply on a comment from a different line'
                  ), logged_in(teacher):
        add_reply('a reply to', line=10, in_reply_to=reply, expect_error=404)


def test_get_all_comments_of_user(
    logged_in, test_client, session, admin_user, describe, tomorrow,
    make_add_reply
):
    with describe('setup'), logged_in(admin_user):
        assignment = helpers.create_assignment(
            test_client, state='open', deadline=tomorrow
        )
        course = assignment['course']
        teacher1 = admin_user
        teacher2 = helpers.create_user_with_role(session, 'Teacher', course)
        student1 = helpers.create_user_with_role(session, 'Student', course)
        student2 = helpers.create_user_with_role(session, 'Student', course)

        sub1 = helpers.create_submission(
            test_client, assignment, for_user=student1
        )

        sub2 = helpers.create_submission(
            test_client, assignment, for_user=student2
        )

        add_reply1 = make_add_reply(sub1)
        add_reply2 = make_add_reply(sub2)

        with logged_in(teacher1):
            rep1_1 = add_reply1('Hello a reply', line=1)
            rep1_2 = add_reply1('Hello a reply', line=1)
            rep2 = add_reply1('Hello a reply', line=10)
            rep3 = add_reply2('Hello a reply', line=5)

        def get_url(user):
            return (
                f'/api/v1/assignments/{get_id(assignment)}/users'
                f'/{get_id(user)}/comments/'
            )

    with describe('Can get all comments by a user'), logged_in(teacher1):
        result = [
            {
                '__allow_extra__': True,
                'replies': [
                    dict_without(rep1_1, 'author'),
                    dict_without(rep1_2, 'author')
                ],
                'line': 1,
            },
            {
                '__allow_extra__': True,
                'replies': [dict_without(rep2, 'author')],
                'line': 10,
            },
            {
                '__allow_extra__': True,
                'replies': [dict_without(rep3, 'author')],
                'line': 5,
            },
        ]
        test_client.req('get', get_url(teacher1), 200, result)

    with describe('Does not get threads without own reply'):
        with logged_in(teacher2):
            # rep1_3 is allowed to exist in the reply, however this is not the
            # case with the current implementation. rep5 should never be in the
            # reply.
            rep1_3 = add_reply1('A reply by somebody else', line=1)
            rep5 = add_reply1('A reply by somebody else', line=100)
            test_client.req(
                'get',
                get_url(teacher2),
                200,
                [
                    {
                        '__allow_extra__': True,
                        'replies': [
                            # rep1_1 and rep1_2 are allowed to be present
                            dict_without(rep1_3, 'author')
                        ],
                        'line': 1,
                    },
                    {
                        '__allow_extra__': True,
                        'replies': [dict_without(rep5, 'author')],
                        'line': 100,
                    },
                ],
            )

        with logged_in(teacher1):
            test_client.req('get', get_url(teacher1), 200, result)
