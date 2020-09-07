import re
import uuid
from datetime import timedelta

import flask
from freezegun import freeze_time

import psef
import helpers
import psef.models as m
from psef.permissions import CoursePermission as CPerm


def test_enabling_login_links(
    describe, test_client, logged_in, admin_user, yesterday, session,
    stub_function, app, monkeypatch, tomorrow, error_template
):
    with describe('setup'), logged_in(admin_user):
        send_mail_stub = stub_function(psef.mail, 'send_login_link_mail')
        assig = helpers.create_assignment(test_client)
        assig_id = helpers.get_id(assig)
        course = helpers.get_id(assig['course'])
        url = f'/api/v1/assignments/{assig_id}'
        teacher = helpers.create_user_with_perms(
            session, [
                CPerm.can_see_assignments,
                CPerm.can_see_hidden_assignments,
                CPerm.can_view_analytics,
                CPerm.can_edit_assignment_info,
            ], course
        )
        no_perm = helpers.create_user_with_perms(
            session, [
                CPerm.can_see_assignments,
                CPerm.can_see_hidden_assignments,
                CPerm.can_view_analytics,
            ], course
        )
        # Make sure there are users to email
        for _ in range(10):
            helpers.create_user_with_role(session, 'Student', course)

    with describe('cannot enable login links for wrong kind'
                  ), logged_in(teacher):
        test_client.req('patch', url, 409, data={'send_login_links': True})
        _, rv = test_client.req(
            'patch',
            url,
            200,
            data={
                'deadline': yesterday.isoformat(),
                'available_at': (yesterday - timedelta(minutes=1)).isoformat(),
                'kind': 'exam',
                'send_login_links': True,
            },
            result={
                '__allow_extra__': True,
                'send_login_links': True,
            },
            include_response=True,
        )
        warning = rv.headers['warning']
        assert re.match(r'.*deadline.*expired.*not send', warning)
        assert not send_mail_stub.called

    with describe('cannot enable login links for wrong kind'
                  ), logged_in(teacher):
        test_client.req('patch', url, 409, data={'kind': 'normal'})
        assert not send_mail_stub.called

    with describe('cannot change login links with incorrect perms'
                  ), logged_in(no_perm):
        test_client.req('patch', url, 403, data={'send_login_links': False})
        assert not send_mail_stub.called

    with describe('Setting again does nothing'), logged_in(teacher):
        old_token = m.Assignment.query.get(assig_id).send_login_links_token
        test_client.req(
            'patch',
            url,
            200,
            data={
                'send_login_links': True,
                'available_at': (yesterday - timedelta(minutes=1)).isoformat(),
            }
        )
        new_token = m.Assignment.query.get(assig_id).send_login_links_token
        assert new_token == old_token
        assert not send_mail_stub.called

    with describe('Changing available at reschedules links'
                  ), logged_in(teacher):
        old_token = m.Assignment.query.get(assig_id).send_login_links_token
        test_client.req(
            'patch',
            url,
            200,
            data={
                'send_login_links': True,
                'available_at': (yesterday - timedelta(minutes=2)).isoformat(),
            }
        )
        new_token = m.Assignment.query.get(assig_id).send_login_links_token
        assert new_token != old_token
        assert new_token is not None
        assert not send_mail_stub.called

    with describe('Disabling clears token'), logged_in(teacher):
        test_client.req('patch', url, 200, data={'send_login_links': False})
        new_token = m.Assignment.query.get(assig_id).send_login_links_token
        assert new_token is None
        assert not send_mail_stub.called

    with describe('Cannot enable login links with large availability window'
                  ), logged_in(teacher):
        monkeypatch.setitem(
            app.config, 'EXAM_LOGIN_MAX_LENGTH', timedelta(days=1)
        )
        test_client.req(
            'patch',
            url,
            409,
            data={
                'send_login_links': True,
                'deadline': tomorrow.isoformat(),
                'available_at': yesterday.isoformat(),
            },
            result={
                **error_template, 'message':
                    re.compile(
                        'Login links can only be enabled if the deadline is at'
                        ' most 24 hours after.*'
                    )
            }
        )


def test_sending_login_links(
    app, monkeypatch, describe, test_client, logged_in, admin_user, tomorrow,
    session, stub_function, error_template
):
    with describe('setup'), logged_in(admin_user):
        external_url = f'https://{uuid.uuid4()}.com'
        monkeypatch.setitem(app.config, 'EXTERNAL_URL', external_url)
        monkeypatch.setitem(
            app.config, 'LOGIN_TOKEN_BEFORE_TIME',
            [timedelta(hours=1), timedelta(minutes=5)]
        )
        orig_send_links = psef.tasks.send_login_links_to_users
        stub_send_links = stub_function(
            psef.tasks, 'send_login_links_to_users'
        )
        stub_function(psef.tasks, 'maybe_open_assignment_at')

        other_course = helpers.create_course(test_client)

        course = helpers.create_course(test_client)
        assig = helpers.create_assignment(test_client, course)
        url = f'/api/v1/assignments/{helpers.get_id(assig)}'

        test_client.req(
            'patch',
            url,
            200,
            data={
                'deadline': (tomorrow + timedelta(hours=1)).isoformat(),
                'available_at': tomorrow.isoformat(),
                'kind': 'exam',
            },
        )

        teacher = admin_user
        students = [
            helpers.create_user_with_role(
                session, 'Student', [course, other_course]
            ) for _ in range(10)
        ]

        with logged_in(students[0]):
            test_client.req(
                'get', '/api/v1/courses/', 200,
                [{'__allow_extra__': True, 'id': helpers.get_id(course)},
                 {'__allow_extra__': True, 'id': helpers.get_id(other_course)}]
            )

    with describe('can send link and each user receives a unique link'
                  ), logged_in(teacher):
        test_client.req('patch', url, 200, data={'send_login_links': True})
        assert stub_send_links.called_amount == 2
        # We safe the arguments here as the stub function will be reset at the
        # end of the describe block.
        do_send_links = [
            lambda args=args, kwargs=kwargs: orig_send_links(*args, **kwargs)
            for args, kwargs in
            zip(stub_send_links.args, stub_send_links.kwargs)
        ]

        with psef.mail.mail.record_messages() as outbox:
            with freeze_time(tomorrow - timedelta(hours=1)):
                del flask.g.request_start_time
                do_send_links[0]()

            assert len(outbox) == len(students)
            for mail in outbox:
                assert len(mail.recipients) == 1
            outbox_by_email = {mail.recipients[0]: mail for mail in outbox}
            users_by_link = {}
            link_ids = []

            for student in students:
                student = student._get_current_object()
                mail = outbox_by_email.pop((student.name, student.email))
                match = re.search(
                    rf'a href="({external_url}/[^"]+)"', str(mail)
                )
                link, = match.groups(1)
                assert link.startswith(external_url)
                assert link not in users_by_link
                users_by_link[link] = student
                link_id = link.split('/')[-1]
                link_ids.append((link_id, student))

            assert not outbox_by_email, 'No extra mails should be sent'

    with describe('second email send the same link'), logged_in(teacher):
        with psef.mail.mail.record_messages() as outbox:
            with freeze_time(tomorrow - timedelta(minutes=1)):
                del flask.g.request_start_time
                do_send_links[1]()

            assert len(outbox) == len(students)
            for mail in outbox:
                assert len(mail.recipients) == 1
            outbox_by_email = {mail.recipients[0]: mail for mail in outbox}

            for student in students:
                mail = outbox_by_email.pop((student.name, student.email))
                match = re.search(
                    rf'a href="({external_url}/[^"]+)"', str(mail)
                )
                link, = match.groups(1)
                assert link.startswith(external_url)
                assert users_by_link[link] == student

            assert not outbox_by_email, 'No extra mails should be send'

    with describe('can see link before available_at, but no login'
                  ), freeze_time(tomorrow - timedelta(hours=1)):
        for link_id, student in link_ids:
            test_client.req(
                'get',
                f'/api/v1/login_links/{link_id}',
                200,
                {
                    'id': link_id,
                    'user': student,
                    # Assignment is already visible
                    'assignment': {
                        '__allow_extra__': True,
                        'id': helpers.get_id(assig),
                        'state': 'hidden',
                    }
                }
            )

            test_client.req(
                'post', f'/api/v1/login_links/{link_id}/login', 409, {
                    **error_template,
                    'message': re.compile('.*wait for an hour'),
                }
            )

    with describe(
        'can login when assignment has started, token is scoped to the course'
    ), freeze_time(tomorrow + timedelta(seconds=15)):
        for idx, (link_id, student) in enumerate(link_ids):
            test_client.req(
                'get',
                f'/api/v1/login_links/{link_id}',
                200,
                {
                    'id': link_id,
                    'user': student,
                    # Assignment is already visible
                    'assignment': {
                        '__allow_extra__': True,
                        'id': helpers.get_id(assig),
                        'state': 'hidden' if idx == 0 else 'submitting',
                    }
                }
            )

            token = test_client.req(
                'post', f'/api/v1/login_links/{link_id}/login', 200, {
                    'user': {
                        '__allow_extra__': True,
                        'id': student.id,
                    },
                    'access_token': str,
                }
            )['access_token']

            # Make sure we are logged in for the correct user.
            headers = {'Authorization': f'Bearer {token}'}
            test_client.req(
                'get',
                '/api/v1/login',
                200,
                headers=headers,
                result={'id': student.id, '__allow_extra__': True},
            )
            test_client.req(
                'get',
                '/api/v1/courses/',
                200,
                headers=headers,
                result=[{
                    'id': helpers.get_id(course), '__allow_extra__': True
                }],
            )
            test_client.req(
                'get',
                f'/api/v1/courses/{helpers.get_id(other_course)}',
                403,
                headers=headers,
            )

    with describe('cannot login if deadline has expired'
                  ), freeze_time(tomorrow + timedelta(hours=2)):
        for idx, (link_id, student) in enumerate(link_ids):
            token = test_client.req(
                'post',
                f'/api/v1/login_links/{link_id}/login',
                400,
                {
                    **error_template,
                    'message':
                        re.compile(
                            'The deadline for this assignment has already'
                            ' expired'
                        ),
                    'code': 'OBJECT_EXPIRED',
                },
            )
