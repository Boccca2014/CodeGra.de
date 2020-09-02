from datetime import timedelta

import pytest
import freezegun

import helpers
import psef.models as m
from cg_dt_utils import DatetimeWithTimezone
from test_feedback import mail_functions, make_add_reply
from psef.permissions import CoursePermission as CPerm


def get_all_connections(assignment, amount):
    assig_id = helpers.get_id(assignment)
    assignment = m.Assignment.query.get(assig_id)
    assert assignment is not None, 'Could not find assignment'
    pf_settings = assignment.peer_feedback_settings
    if amount == 0:
        assert pf_settings is None
        return
    assert pf_settings is not None, 'Not a PF assig'
    connections = sorted((conn.peer_user_id, conn.user_id)
                         for conn in pf_settings.connections)
    seen_amount = {}
    res = {}
    for a, b in connections:
        assert a != b
        if a not in res:
            res[a] = []
        if b not in seen_amount:
            seen_amount[b] = 0
        seen_amount[b] += 1
        assert b not in res[a]
        res[a].append(b)

    for a, conns in res.items():
        assert len(conns) == amount
        assert seen_amount[a] == amount

    return res


def test_enabling_peer_feedback(
    test_client, session, describe, admin_user, logged_in
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, state='open'
        )
        user_with_perm = helpers.create_user_with_perms(
            session,
            [CPerm.can_edit_peer_feedback_settings, CPerm.can_see_assignments],
            course
        )
        user_without_perm = helpers.create_user_with_perms(
            session, [CPerm.can_see_assignments], course
        )

    with describe('User without perm cannot enable'
                  ), logged_in(user_without_perm):
        helpers.enable_peer_feedback(test_client, assignment, err=403)

    with describe('User with perm can enable'), logged_in(user_with_perm):
        helpers.enable_peer_feedback(test_client, assignment)

    with describe('Amount should be >= 1'), logged_in(user_with_perm):
        helpers.enable_peer_feedback(
            test_client, assignment, amount=-1, err=400
        )
        helpers.enable_peer_feedback(
            test_client, assignment, amount=0, err=400
        )
        helpers.enable_peer_feedback(test_client, assignment, amount=110)

    with describe('Time should be > 0'), logged_in(user_with_perm):
        helpers.enable_peer_feedback(test_client, assignment, days=-1, err=400)
        helpers.enable_peer_feedback(test_client, assignment, days=0, err=400)
        helpers.enable_peer_feedback(test_client, assignment, days=0.005)


@pytest.mark.parametrize('iteration', range(5))
def test_division(
    test_client, admin_user, session, describe, logged_in, yesterday, iteration
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, deadline=yesterday
        )
        helpers.enable_peer_feedback(test_client, assignment)
        user1, user2, user3, user4 = [
            helpers.get_id(
                helpers.create_user_with_role(session, 'Student', course)
            ) for _ in range(4)
        ]

    with describe('Single submission no connections'), logged_in(admin_user):
        assert get_all_connections(assignment, 1) == {}
        helpers.create_submission(test_client, assignment, for_user=user1)
        assert get_all_connections(assignment, 1) == {}

    with describe('Second submission does initial division'
                  ), logged_in(admin_user):
        helpers.create_submission(test_client, assignment, for_user=user2)
        assert get_all_connections(assignment,
                                   1) == {user1: [user2], user2: [user1]}

    with describe('Third submission also gets divided'), logged_in(admin_user):
        helpers.create_submission(test_client, assignment, for_user=user3)
        connections = get_all_connections(assignment, 1)
        assert len(connections) == 3
        if connections[user3] == [user1]:
            assert connections[user2] == [user3]
            assert connections[user1] == [user2]
        else:
            assert connections[user3] == [user2]
            assert connections[user1] == [user3]
            assert connections[user2] == [user1]

    with describe('Submitting again does not change division'
                  ), logged_in(admin_user):
        old_connections = get_all_connections(assignment, 1)
        for _ in range(10):
            last_sub3 = helpers.create_submission(
                test_client, assignment, for_user=user3
            )
            assert get_all_connections(assignment, 1) == old_connections

    with describe('Deleting not last submission does not change division'
                  ), logged_in(admin_user):
        old_connections = get_all_connections(assignment, 1)
        _, rv = test_client.req(
            'delete',
            f'/api/v1/submissions/{helpers.get_id(last_sub3)}',
            204,
            include_response=True,
        )
        assert 'warning' not in rv.headers
        assert get_all_connections(assignment, 1) == old_connections

    with describe('Test submission does not change anything'
                  ), logged_in(admin_user):
        old_connections = get_all_connections(assignment, 1)
        for _ in range(10):
            helpers.create_submission(
                test_client, assignment, is_test_submission=True
            )
            assert get_all_connections(assignment, 1) == old_connections

    with describe('user gets assigned to different user every time'
                  ), logged_in(admin_user):
        conns = set()
        for _ in range(40):
            sub = helpers.create_submission(
                test_client, assignment, for_user=user4
            )
            new_conns = get_all_connections(assignment, 1)[user4]
            conns.add(new_conns[0])
            _, rv = test_client.req(
                'delete',
                f'/api/v1/submissions/{helpers.get_id(sub)}',
                204,
                include_response=True,
            )
            assert 'warning' not in rv.headers
        assert len(conns) == 3


@pytest.mark.parametrize('students', [5, 6, 7, 10, 25, 30, 100, 300])
def test_division_larger_assignment(
    test_client, admin_user, session, describe, logged_in, yesterday, students
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, deadline=yesterday
        )
        all_users = [
            helpers.get_id(
                helpers.create_user_with_role(session, 'Student', course)
            ) for _ in range(students)
        ]
        user1, *rest_users = all_users
        rest_subs = [(
            user,
            helpers.create_submission(test_client, assignment, for_user=user)
        ) for user in rest_users]

    with describe('Enabling peer feedback should do divide'
                  ), logged_in(admin_user):
        helpers.enable_peer_feedback(test_client, assignment, amount=3)
        conns = get_all_connections(assignment, 3)
        assert len(conns) == len(rest_users)

    with describe('Submitting should still be possible'
                  ), logged_in(admin_user):
        helpers.create_submission(test_client, assignment, for_user=user1)
        conns = get_all_connections(assignment, 3)
        assert len(conns) == len(all_users)
        assert len(conns[user1]) == 3

    with describe('Can delete all rest users'), logged_in(admin_user):
        warning_amount = 0
        for idx, (user_id, sub) in enumerate(rest_subs):
            _, rv = test_client.req(
                'delete',
                f'/api/v1/submissions/{helpers.get_id(sub)}',
                204,
                include_response=True,
            )
            had_warning = 'warning' in rv.headers
            if had_warning:
                warning_amount += 1
            print('Deleting submission of', user_id, 'warning:', had_warning)
            conns = get_all_connections(assignment, 3)
            left = len(all_users) - (idx + 1)
            if left > 3:
                assert len(conns) == left, f'Got wrong amount of conns {conns}'
            else:
                assert len(conns) == 0, f'Got wrong amount of conns {conns}'

        assert warning_amount < len(all_users)


def test_delete_sub_with_cycle(
    test_client, admin_user, session, describe, logged_in, yesterday
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, deadline=yesterday
        )
        users = [
            helpers.get_id(
                helpers.create_user_with_role(session, 'Student', course)
            ) for _ in range(5)
        ]
        user1, user2, user3, user4, user5 = users
        subs = {
            user: helpers.create_submission(
                test_client,
                assignment,
                for_user=user,
            )
            for user in users
        }
        helpers.enable_peer_feedback(test_client, assignment, amount=1)

    with describe('setup cycle'):
        assig_id = helpers.get_id(assignment)
        assignment = m.Assignment.query.get(assig_id)
        assert assignment is not None, 'Could not find assignment'
        pf_settings = assignment.peer_feedback_settings
        pf_settings.connections = []

        for reviewer, subject in [
            (user1, user2),
            (user2, user1),
            (user3, user4),
            (user4, user5),
            (user5, user3),
        ]:
            reviewer = m.User.query.get(reviewer)
            subject = m.User.query.get(subject)
            conn = m.AssignmentPeerFeedbackConnection(
                pf_settings, user=subject, peer_user=reviewer
            )
            assert str(reviewer.id) in repr(conn)
            assert str(subject.id) in repr(conn)

        session.commit()

        # Make sure the just setup connections are valid
        get_all_connections(assignment, 1)

    with describe('delete sub of user in small cycle'), logged_in(admin_user):
        _, rv = test_client.req(
            'delete',
            f'/api/v1/submissions/{helpers.get_id(subs[user2])}',
            204,
            include_response=True,
        )
        assert (
            'All connections for peer feedback were redivided because of this'
            ' deletion.'
        ) in rv.headers['warning']

        conns = get_all_connections(assignment, 1)
        assert set(conns[user1]) & {user3, user4, user5}


def test_getting_peer_feedback_connections(
    test_client, admin_user, session, describe, logged_in, yesterday, tomorrow
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, deadline=yesterday, state='open'
        )
        teacher = helpers.create_user_with_role(session, 'Teacher', course)
        users = [
            helpers.get_id(
                helpers.create_user_with_role(session, 'Student', course)
            ) for _ in range(5)
        ]
        user1, user2, *_ = users
        for user in users:
            helpers.create_submission(test_client, assignment, for_user=user)

        helpers.enable_peer_feedback(test_client, assignment, amount=1)
        url = (
            f'/api/v1/assignments/{helpers.get_id(assignment)}/users'
            f'/{helpers.get_id(user1)}/peer_feedback_subjects/'
        )
        conns = get_all_connections(assignment, 1)[user1]

    with describe('Can get connections for own user'):
        with logged_in(user1):
            api_conns = test_client.req(
                'get',
                url,
                200,
                result=[{
                    'peer': helpers.to_db_object(user1, m.User),
                    'subject': helpers.to_db_object(conns[0], m.User),
                }]
            )

    with describe('Cannot get connections for other user as student'):
        with logged_in(user2):
            test_client.req('get', url, 403)

    with describe('Can get connections for other user as teacher'):
        with logged_in(teacher):
            test_client.req('get', url, 200, result=api_conns)

    with describe(
        'No connections if assignments deadline has not expired just yet'
    ):
        with logged_in(teacher):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{helpers.get_id(assignment)}',
                200,
                data={'deadline': tomorrow.isoformat()}
            )

        with logged_in(user1):
            test_client.req('get', url, 200, result=[])

        # Not even as teacher
        with logged_in(teacher):
            test_client.req('get', url, 200, result=[])


@pytest.mark.parametrize('auto_approved', [True, False])
def test_giving_peer_feedback_comments(
    test_client, admin_user, session, describe, logged_in, yesterday, tomorrow,
    auto_approved, make_add_reply
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, deadline=tomorrow, state='open'
        )
        teacher = helpers.create_user_with_role(session, 'Teacher', course)
        users = [
            helpers.get_id(
                helpers.create_user_with_role(session, 'Student', course)
            ) for _ in range(5)
        ]
        user1, *other_users = users
        subs_by_user = {}
        for user in users:
            helpers.create_submission(test_client, assignment, for_user=user)
            # Every user has two submissions
            subs_by_user[user] = helpers.create_submission(
                test_client, assignment, for_user=user
            )

        helpers.enable_peer_feedback(
            test_client, assignment, amount=1, auto_approved=auto_approved
        )
        conns = get_all_connections(assignment, 1)[user1]
        other_user = next(u for u in other_users if u not in conns)
        base_url = f'/api/v1/assignments/{helpers.get_id(assignment)}'
        pf_sub = subs_by_user[conns[0]]
        own_sub = subs_by_user[user1]
        add_reply = make_add_reply(pf_sub)

        with logged_in(teacher):
            teacher_rep = add_reply('Hello')
            base_comment_id = teacher_rep['comment_base_id']
            teacher_rep.delete()

    with describe(
        'Before deadline we have no connections (and cannot place feedback)'
    ), logged_in(user1):
        test_client.req(
            'get',
            f'{base_url}/submissions/?latest_only',
            200,
            result=[{
                'id': int,
                'user': {
                    'id': user1,
                    '__allow_extra__': True,
                },
                '__allow_extra__': True,
            }]
        )
        add_reply(
            'Too early for a reply', expect_error=403, base_id=base_comment_id
        )

    with logged_in(teacher):
        test_client.req(
            'patch', base_url, 200, data={'deadline': yesterday.isoformat()}
        )

    with describe(
        'Will receive peer feedback submissions when getting all submissions'
    ), logged_in(user1):
        test_client.req(
            'get',
            f'{base_url}/submissions/?latest_only&extended',
            200,
            result=[pf_sub, own_sub],
        )
        # Can also get older subs of a assigned user
        test_client.req(
            'get',
            f'{base_url}/users/{conns[0]}/submissions/?extended',
            200,
            result=[
                pf_sub,
                {
                    '__allow_extra__': True,
                    'user': {'id': conns[0], '__allow_extra__': True},
                }
            ],
        )

    with describe('Can comment on other submission'), logged_in(user1):
        reply = add_reply('A peer feedback comment', expect_peer_feedback=True)
        assert reply['approved'] == auto_approved

    with describe('Cannot change approval status yourself'), logged_in(user1):
        reply.set_approval(not auto_approved, err=403)

    with describe('Teacher can change approval status'), logged_in(teacher):
        reply = reply.set_approval(not auto_approved)

    with describe('Editing feedback resets approval status'):
        with logged_in(user1):
            # We don't reset it back to ``True`` if ``auto_approved`` is
            # ``True`` but we do set it back to ``False``.
            reply = reply.update('New content', approved=False)

        if auto_approved:
            # If reply is approved an ``auto_approved`` is ``True`` the
            # approval state should not change.
            with logged_in(teacher):
                reply.set_approval(True)
            with logged_in(user1):
                reply = reply.update('New content2', approved=True)

    with describe(
        'Cannot place or edit peer feedback after pf deadline has expired'
    ):
        with logged_in(teacher):
            helpers.enable_peer_feedback(
                test_client,
                assignment,
                amount=1,
                auto_approved=auto_approved,
                days=0.5
            )
            assert get_all_connections(assignment, 1)[user1] == conns
        with logged_in(user1):
            add_reply('Another peer feedback comment', expect_error=403)

            reply.update('Cannot update!', err=403)

    with describe('Can always place peer feedback if pf time is None'):
        with logged_in(teacher):
            helpers.enable_peer_feedback(
                test_client,
                assignment,
                amount=1,
                auto_approved=auto_approved,
                days=None,
            )

        with freezegun.freeze_time(
            DatetimeWithTimezone.utcnow() + timedelta(days=365 * 20)
        ), logged_in(user1):
            reply = reply.update('Can update way after the deadline!')

    with describe('Cannot add peer feedback to a non assigned sub'
                  ), logged_in(other_user):
        add_reply(
            'Not possible to add this',
            expect_error=403,
            base_id=reply['comment_base_id']
        )

    with describe('Student can see approved peer feedback after done'):
        with logged_in(teacher):
            reply = reply.set_approval(not auto_approved)
            test_client.req(
                'get',
                f'/api/v1/submissions/{helpers.get_id(pf_sub)}/feedbacks/',
                200,
                query={'with_replies': '1'},
                result={
                    'general': '',
                    'linter': {},
                    'user': [{
                        'id': int,
                        '__allow_extra__': True,
                        'replies': [helpers.dict_without(reply, 'author'), ],
                    }],
                    'authors': [helpers.to_db_object(user1, m.User)],
                },
            )
            test_client.req('patch', base_url, 200, data={'state': 'done'})

        with logged_in(conns[0]):
            test_client.req(
                'get',
                f'/api/v1/submissions/{helpers.get_id(pf_sub)}/feedbacks/',
                200,
                query={'with_replies': '1'},
                result={
                    'general': '',
                    'linter': {},
                    'authors': ([helpers.to_db_object(user1, m.User)]
                                if reply['approved'] else []),
                    'user': ([{
                        'id': int,
                        '__allow_extra__': True,
                        'replies': [helpers.dict_without(reply, 'author')],
                    }] if reply['approved'] else []),
                },
            )


def test_disabling_peer_feedback(
    test_client, admin_user, session, describe, logged_in, yesterday,
    make_add_reply
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, deadline=yesterday, state='open'
        )
        teacher = helpers.create_user_with_role(session, 'Teacher', course)
        users = [
            helpers.get_id(
                helpers.create_user_with_role(session, 'Student', course)
            ) for _ in range(5)
        ]
        user1, *other_users = users
        for user in users:
            helpers.create_submission(test_client, assignment, for_user=user)

        helpers.enable_peer_feedback(test_client, assignment)
        conns = get_all_connections(assignment, 1)[user1]
        base_url = f'/api/v1/assignments/{helpers.get_id(assignment)}'

        pf_sub = m.Work.query.filter_by(
            assignment_id=helpers.get_id(assignment),
            user_id=helpers.get_id(conns[0]),
        ).one()
        pf_url = f'{base_url}/peer_feedback_settings'

        add_reply = make_add_reply(pf_sub)
        with logged_in(user1):
            reply = add_reply(
                'A peer feedback comment', expect_peer_feedback=True
            )

    with describe('Students cannot disable peer feedback'), logged_in(user1):
        test_client.req('delete', pf_url, 403)

    with describe('Teachers can disable peer feedback'), logged_in(teacher):
        test_client.req('delete', pf_url, 204)
        get_all_connections(assignment, 0)

    with describe('Old feedback still exists after disabling'
                  ), logged_in(teacher):
        test_client.req(
            'get',
            f'/api/v1/submissions/{helpers.get_id(pf_sub)}/feedbacks/',
            200,
            query={'with_replies': '1'},
            result={
                'general': '',
                'linter': {},
                'authors': [helpers.to_db_object(user1, m.User)],
                'user': [{
                    'id': int,
                    '__allow_extra__': True,
                    'replies': [helpers.dict_without(reply, 'author')],
                }],
            }
        )

        # Students can no longer see their peer feedback subs
    with describe('Student can no longer place new comments'
                  ), logged_in(user1):
        add_reply(
            'No peer feedback',
            expect_error=403,
            base_id=reply['comment_base_id'],
        )

    with describe('deleting again does nothing'), logged_in(teacher):
        test_client.req('delete', pf_url, 204)
        get_all_connections(assignment, 0)


def test_peer_feedback_and_group_assignments(
    test_client, logged_in, describe, admin_user
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        gset = helpers.create_group_set(test_client, course, 1, 2)

        def enable_group(assig, *, err=False, gset_id=helpers.get_id(gset)):
            return test_client.req(
                'patch',
                f'/api/v1/assignments/{helpers.get_id(assig)}',
                err or 200,
                data={'group_set_id': gset_id}
            )

    with describe('Cannot enable peer feedback on group assignment'
                  ), logged_in(admin_user):
        assig = helpers.create_assignment(test_client, course)
        enable_group(assig)
        err = helpers.enable_peer_feedback(test_client, assig, err=400)
        assert 'This is a group assignment' in err['message']
        enable_group(assig, gset_id=None)
        helpers.enable_peer_feedback(test_client, assig)

    with describe('Cannot make group assignment if peer feedback is enabled'
                  ), logged_in(admin_user):
        assig = helpers.create_assignment(test_client, course)
        helpers.enable_peer_feedback(test_client, assig)
        err = enable_group(assig, err=400)
        assert 'This assignment has peer feedback enabled' in err['message']
        url = (
            f'/api/v1/assignments/{helpers.get_id(assig)}'
            '/peer_feedback_settings'
        )
        test_client.req('delete', url, 204)
        enable_group(assig)
