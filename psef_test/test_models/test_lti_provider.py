import copy
import uuid

import furl
import pytest
import requests
import flask_sqlalchemy
import pylti1p3.names_roles
import pylti1p3.service_connector
import pylti1p3.assignments_grades

import helpers
import psef.models as m
import psef.signals as signals
import requests_stubs
import psef.lti.v1_3.claims as claims
from cg_dt_utils import DatetimeWithTimezone


def raise_pylti1p3_exc():
    raise pylti1p3.exception.LtiException('ERR')


def test_get_self_from_course(
    describe, admin_user, test_client, session, app, logged_in
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.to_db_object(
            helpers.create_course(test_client), m.Course
        )
        lti_course = helpers.to_db_object(
            helpers.create_lti_course(session, app, admin_user), m.Course
        )

    with describe('Getting without course should return none'):
        assert m.LTI1p1Provider._get_self_from_course(None) is None

    with describe('Getting for non LTI course should return none'):
        assert m.LTI1p1Provider._get_self_from_course(course) is None

    with describe('Getting with LTI course should return instance'):
        prov = m.LTI1p1Provider._get_self_from_course(lti_course)
        assert prov is not None
        assert lti_course.lti_provider.id == prov.id

    with describe('Getting for for other LTI class should return none'):
        assert m.LTI1p3Provider._get_self_from_course(lti_course) is None


def test_get_launch_url(describe, logged_in, admin_user, test_client):
    with describe('setup'), logged_in(admin_user):
        canvas_prov = helpers.to_db_object(
            helpers.create_lti1p3_provider(test_client, 'Canvas'),
            m.LTI1p3Provider
        )
        moodle_prov = helpers.to_db_object(
            helpers.create_lti1p3_provider(test_client, 'Moodle'),
            m.LTI1p3Provider
        )

    with describe('Should return a furl object'):
        # Furl is not typed yet so it makes sense to check this as mypy sees it
        # as an `Any`
        url = canvas_prov.get_launch_url(goto_latest_sub=False)
        assert isinstance(url, furl.furl)

    with describe('should not include an ID for canvas'):
        url = canvas_prov.get_launch_url(goto_latest_sub=False)
        assert canvas_prov.id not in str(url)

    with describe('should not include an ID for moodle'):
        url = moodle_prov.get_launch_url(goto_latest_sub=False)
        assert moodle_prov.id in str(url)

    with describe('should be possible to launch to the latest submission'):
        url = canvas_prov.get_launch_url(goto_latest_sub=True)
        assert '/launch_to_latest_submission' in str(url)


def test_retrieve_users_in_course(
    describe, lti1p3_provider, stub_function_class, monkeypatch, test_client,
    admin_user, logged_in, session, app, watch_signal
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.to_db_object(
            helpers.create_course(test_client), m.Course
        )
        membership_url = f'http://{uuid.uuid4()}'
        lti_course, _ = helpers.create_lti1p3_course(
            test_client,
            session,
            lti1p3_provider,
            membership_url,
        )
        return_value = []

        stub_get = stub_function_class(lambda: copy.deepcopy(return_value))
        monkeypatch.setattr(
            pylti1p3.names_roles.NamesRolesProvisioningService, 'get_members',
            stub_get
        )

        assig_created_signal = watch_signal(
            # Make sure we flush the db as we expect that the created
            # assignment can be found by doing queries.
            signals.ASSIGNMENT_CREATED,
            flush_db=True
        )
        user_added_signal = watch_signal(
            signals.USER_ADDED_TO_COURSE,
            clear_all_but=[m.LTI1p3Provider._retrieve_users_in_course]
        )

        new_user_id1 = str(uuid.uuid4())
        new_user_id2 = str(uuid.uuid4())

        do_poll_again = True
        stub_poll_again = stub_function_class(lambda: do_poll_again)
        monkeypatch.setattr(
            m.CourseLTIProvider, 'can_poll_names_again', stub_poll_again
        )

    with describe('make sure it is connected to the necessary signals'):
        assert signals.USER_ADDED_TO_COURSE.is_connected(
            m.LTI1p3Provider._retrieve_users_in_course
        )
        assert signals.ASSIGNMENT_CREATED.is_connected(
            m.LTI1p3Provider._retrieve_users_in_course
        )

    with describe('non lti courses should be ignored'):
        m.LTI1p3Provider._retrieve_users_in_course(course.id)
        assert not stub_get.called

    with describe('should work when no members are returned'):
        assig = helpers.create_lti1p3_assignment(session, lti_course)
        assert assig_created_signal.was_send_once
        assert stub_get.called
        assert user_added_signal.was_not_send
        assert stub_poll_again.called

    with describe('Should be possible to add members'):
        return_value = [
            {
                'status': 'Active',
                # Not correct at all, but the function should still not crash.
                'message': object(),
                'user_id': new_user_id1,
                'email': 'hello@codegrade.com',
                'name': 'USER1',
            },
            {
                'status': 'Active',
                'message': {
                    claims.CUSTOM: {'cg_username_0': 'username_user2'}
                },
                'user_id': new_user_id2,
                'email': 'hello2@codegrade.com',
                'name': 'USER2',
                'roles': ['Student'],
            },
        ]
        signals.ASSIGNMENT_CREATED.send(assig)
        assert stub_poll_again.called
        assert user_added_signal.was_send_once

        # USER1 should not be added and recursion should not happen
        assert user_added_signal.called_amount == 1
        assert m.User.query.filter_by(username='username_user2'
                                      ).one().is_enrolled(lti_course)
        assert m.User.query.filter_by(email='hello@codegrade.com'
                                      ).one_or_none() is None

    with describe('Can add known users to new courses, even without username'):
        # Remove the message claim
        return_value = [{**r, 'message': {}} for r in return_value]

        with logged_in(admin_user):
            lti_course2, _ = helpers.create_lti1p3_course(
                test_client, session, lti1p3_provider
            )

        helpers.create_lti1p3_assignment(session, lti_course2)

        assert user_added_signal.was_send_once
        assert m.User.query.filter_by(username='username_user2'
                                      ).one().is_enrolled(lti_course2)
        assert m.User.query.filter_by(email='hello@codegrade.com'
                                      ).one_or_none() is None

    with describe('if can poll return no poll should be done'):
        do_poll_again = False
        signals.ASSIGNMENT_CREATED.send(assig)
        assert not stub_get.called


def test_delete_submission_passback(
    lti1p3_provider, describe, logged_in, admin_user, watch_signal,
    stub_function, test_client, session, tomorrow
):
    with describe('setup'), logged_in(admin_user):
        watch_signal(signals.WORK_CREATED, clear_all_but=[])
        watch_signal(signals.GRADE_UPDATED, clear_all_but=[])
        watch_signal(signals.USER_ADDED_TO_COURSE, clear_all_but=[])
        stub_function(
            pylti1p3.service_connector.ServiceConnector,
            'get_access_token', lambda: ''
        )
        stub_passback = stub_function(
            pylti1p3.assignments_grades.AssignmentsGradesService, 'put_grade'
        )

        course, course_conn = helpers.create_lti1p3_course(
            test_client, session, lti1p3_provider
        )
        assig = helpers.create_lti1p3_assignment(
            session, course, state='done', deadline=tomorrow
        )
        user = helpers.create_lti1p3_user(session, lti1p3_provider)
        lti_user_id = m.UserLTIProvider.query.filter_by(
            user=m.User.resolve(user)
        ).one().lti_user_id
        course_conn.maybe_add_user_to_course(user, ['Learner'])

        sub_oldest, sub_older, sub_middle, sub_newest = [
            helpers.to_db_object(
                helpers.create_submission(test_client, assig, for_user=user),
                m.Work
            ) for _ in range(4)
        ]
        signal = watch_signal(
            signals.WORK_DELETED,
            clear_all_but=[m.LTI1p3Provider._delete_submission]
        )

        def do_delete(sub):
            with logged_in(admin_user):
                test_client.req(
                    'delete', f'/api/v1/submissions/{helpers.get_id(sub)}', 204
                )

    with describe('Delete non newest'):
        do_delete(sub_older)
        assert signal.was_send_once
        assert not stub_passback.called

    with describe('Calling method for non existing work simply does nothing'):
        m.LTI1p3Provider._delete_submission(1000000)
        assert not stub_passback.called

    with describe('Calling method for non deleted work does nothing'):
        m.LTI1p3Provider._delete_submission(helpers.get_id(sub_newest))
        assert not stub_passback.called

    with describe('Delete newest should passback grade of new newest'):
        sub_middle.set_grade(5.0, m.User.resolve(admin_user))
        session.commit()
        # We should have removed the grade_updated signal
        assert not stub_passback.called

        do_delete(sub_newest)
        assert signal.was_send_once
        assert stub_passback.called_amount == 1
        grade, = stub_passback.all_args[0].values()
        assert grade.get_score_given() == 5.0
        assert grade.get_user_id() == lti_user_id

    with describe('Deleting new newest should passback next non deleted'):
        sub_older.set_grade(6.0, m.User.resolve(admin_user))
        sub_oldest.set_grade(8.0, m.User.resolve(admin_user))
        session.commit()
        assert not m.GradeHistory.query.filter_by(work=sub_oldest
                                                  ).one().passed_back

        do_delete(sub_middle)
        assert signal.was_send_once
        assert stub_passback.called_amount == 1
        grade, = stub_passback.all_args[0].values()
        # Should passback oldest as we deleted older in an earlier block
        assert grade.get_score_given() == 8.0
        assert grade.get_user_id() == lti_user_id

        # Should update history
        assert m.GradeHistory.query.filter_by(work=sub_oldest
                                              ).one().passed_back

    with describe('Deleting without any existing submission should passback'):
        do_delete(sub_oldest)
        assert signal.was_send_once
        assert stub_passback.called_amount == 1
        grade, = stub_passback.all_args[0].values()
        assert grade.get_score_given() is None
        assert grade.get_grading_progress() == 'NotReady'
        assert grade.get_user_id() == lti_user_id

    with describe('Passing back deleted sub should do nothing'):
        lti1p3_provider._passback_grade(
            assignment=assig,
            sub=sub_newest,
            timestamp=DatetimeWithTimezone.utcnow()
        )
        assert not stub_passback.called


def test_passing_back_all_grades(
    lti1p3_provider, describe, logged_in, admin_user, watch_signal,
    stub_function, test_client, session, tomorrow, make_function_spy
):
    with describe('setup'), logged_in(admin_user):
        watch_signal(signals.WORK_CREATED, clear_all_but=[])
        watch_signal(signals.GRADE_UPDATED, clear_all_but=[])
        watch_signal(signals.USER_ADDED_TO_COURSE, clear_all_but=[])
        watch_signal(signals.WORK_DELETED, clear_all_but=[])
        signal = watch_signal(
            signals.ASSIGNMENT_STATE_CHANGED,
            clear_all_but=[m.LTI1p3Provider._passback_grades]
        )

        stub_get_acccess_token = stub_function(
            pylti1p3.service_connector.ServiceConnector,
            'get_access_token', lambda: ''
        )
        stub_passback = make_function_spy(
            pylti1p3.assignments_grades.AssignmentsGradesService,
            'put_grade',
            pass_self=True
        )

        # Make a session with a response that returns json when the `json`
        # method is called
        req_session = requests_stubs.session_maker()()
        req_session.Response.json = lambda _=None: {}
        stub_requests_post = stub_function(requests, 'post', req_session.post)

        course, course_conn = helpers.create_lti1p3_course(
            test_client, session, lti1p3_provider
        )
        assig = helpers.create_lti1p3_assignment(
            session, course, state='hidden', deadline=tomorrow
        )

        user1 = helpers.create_lti1p3_user(session, lti1p3_provider)
        user2 = helpers.create_lti1p3_user(session, lti1p3_provider)
        user3 = helpers.create_lti1p3_user(session, lti1p3_provider)
        all_students = [user1, user2, user3]

        for u in all_students:
            course_conn.maybe_add_user_to_course(u, ['Learner'])

        lti_user_ids = [
            m.UserLTIProvider.query.filter_by(user=u).one().lti_user_id
            for u in all_students
        ]

        gset = helpers.create_group_set(test_client, course, 1, 2, [assig])
        helpers.create_group(test_client, gset, [user1, user3])

        sub = helpers.to_db_object(
            helpers.create_submission(test_client, assig, for_user=user1),
            m.Work
        )
        sub.set_grade(2.5, admin_user)

        # Make sure user2 does not have a non deleted submission
        user2_sub = helpers.create_submission(
            test_client, assig, for_user=user2
        )
        test_client.req(
            'delete', f'/api/v1/submissions/{helpers.get_id(user2_sub)}', 204
        )

    with describe('changing assignment state to "open" does not passback'):
        assig.set_state_with_string('open')
        assert signal.was_send_once
        assert not stub_passback.called
        assert not stub_get_acccess_token.called

    with describe('changing to done does passback'):
        assig.set_state_with_string('done')
        assert signal.was_send_once
        assert stub_passback.called_amount == len(all_students)
        # Calls should be cached
        assert stub_get_acccess_token.called_amount == 1

        p1, p2, p3 = stub_passback.args

        assert p1[0] != p2[0] != p3[0]

        assert p1[0].get_score_given() == 2.5
        assert p2[0].get_score_given() == 2.5
        assert {p1[0].get_user_id(),
                p2[0].get_user_id()} == {lti_user_ids[0], lti_user_ids[2]}

        # Does not have a submission
        assert p3[0].get_score_given() is None
        assert p3[0].get_user_id() == lti_user_ids[1]

    with describe('toggling to open and done should do a new passback'):
        assig.set_state_with_string('open')
        assert signal.was_send_once
        assert not stub_passback.called
        assert not stub_get_acccess_token.called

        assig.set_state_with_string('done')
        assert signal.was_send_n_times(2)
        assert stub_passback.called
        # access token should still be cached
        assert not stub_get_acccess_token.called


def test_passback_for_new_student(
    lti1p3_provider, describe, logged_in, admin_user, watch_signal,
    stub_function, test_client, session, tomorrow
):
    with describe('setup'), logged_in(admin_user):
        signal = watch_signal(
            signals.USER_ADDED_TO_COURSE,
            flush_db=True,
            clear_all_but=[m.LTI1p3Provider._passback_new_user]
        )
        stub_function(
            pylti1p3.names_roles.NamesRolesProvisioningService,
            'get_members',
            lambda: [],
        )
        stub_function(
            pylti1p3.service_connector.ServiceConnector,
            'get_access_token', lambda: ''
        )
        stub_passback = stub_function(
            pylti1p3.assignments_grades.AssignmentsGradesService, 'put_grade'
        )

        course, course_conn = helpers.create_lti1p3_course(
            test_client, session, lti1p3_provider
        )
        assig1 = helpers.create_lti1p3_assignment(
            session, course, deadline=tomorrow
        )
        assig2 = helpers.create_lti1p3_assignment(
            session, course, deadline=tomorrow
        )
        user = helpers.create_lti1p3_user(session, lti1p3_provider)

    with describe('non enrolled student should not do anything'):
        assert not user.is_enrolled(course)
        m.LTI1p3Provider._passback_new_user((user.id, course.id, None))
        assert not stub_passback.called

    with describe('enrolling student should passback the grades'):
        course_conn.maybe_add_user_to_course(user, [])
        assert signal.was_send_once
        assert stub_passback.called_amount == 2


def test_failing_passback(
    lti1p3_provider, describe, logged_in, admin_user, watch_signal,
    stub_function, test_client, session, tomorrow
):
    with describe('setup'), logged_in(admin_user):
        watch_signal(signals.WORK_CREATED, clear_all_but=[])
        watch_signal(signals.GRADE_UPDATED, clear_all_but=[])
        watch_signal(signals.USER_ADDED_TO_COURSE, clear_all_but=[])
        stub_function(
            pylti1p3.service_connector.ServiceConnector,
            'get_access_token', lambda: ''
        )
        stub_passback = stub_function(
            pylti1p3.assignments_grades.AssignmentsGradesService, 'put_grade',
            raise_pylti1p3_exc
        )

        course, course_conn = helpers.create_lti1p3_course(
            test_client, session, lti1p3_provider
        )
        assig = helpers.create_lti1p3_assignment(
            session, course, state='done', deadline=tomorrow
        )

        user = helpers.create_lti1p3_user(session, lti1p3_provider)
        course_conn.maybe_add_user_to_course(user, [])

        sub = helpers.to_db_object(
            helpers.create_submission(test_client, assig, for_user=user),
            m.Work
        )
        sub.set_grade(10.0, m.User.resolve(admin_user))
        session.commit()
        hist = m.GradeHistory.query.filter_by(work=sub).one()
        assert hist
        assert not hist.passed_back

    with describe('failing passback should not update history'):

        m.LTI1p3Provider._passback_grades(assig.id)
        assert stub_passback.called
        hist = m.GradeHistory.query.filter_by(work=sub).one()
        assert hist
        assert not hist.passed_back


def test_passback_single_submission(
    lti1p3_provider, describe, logged_in, admin_user, watch_signal,
    stub_function, test_client, session, tomorrow
):
    with describe('setup'), logged_in(admin_user):
        watch_signal(signals.WORK_CREATED, clear_all_but=[])
        watch_signal(signals.USER_ADDED_TO_COURSE, clear_all_but=[])
        signal = watch_signal(
            signals.GRADE_UPDATED,
            clear_all_but=[m.LTI1p3Provider._passback_submission]
        )

        stub_function(
            pylti1p3.service_connector.ServiceConnector,
            'get_access_token', lambda: ''
        )
        stub_passback = stub_function(
            pylti1p3.assignments_grades.AssignmentsGradesService, 'put_grade',
            raise_pylti1p3_exc
        )

        course, course_conn = helpers.create_lti1p3_course(
            test_client, session, lti1p3_provider
        )
        assig = helpers.create_lti1p3_assignment(
            session, course, state='done', deadline=tomorrow
        )

        user = helpers.create_lti1p3_user(session, lti1p3_provider)
        course_conn.maybe_add_user_to_course(user, [])

        older_sub, newest_sub = [
            helpers.to_db_object(
                helpers.create_submission(test_client, assig, for_user=user),
                m.Work
            ) for _ in range(2)
        ]

    with describe('calling directly with non existing assignment is a noop'):
        m.LTI1p3Provider._passback_submission((newest_sub.id, 100000))
        assert not stub_passback.called

    with describe('changing grade of non newest sub does not passback'):
        older_sub.set_grade(5.0, admin_user)
        assert signal.was_send_once
        assert not stub_passback.called

    with describe('changing grade on newest sub passes the new grade back'):
        newest_sub.set_grade(9.5, m.User.resolve(admin_user))
        assert signal.was_send_once
        assert stub_passback.called_amount == 1
        assert stub_passback.args[0][0].get_score_given() == 9.5

    with describe('unsetting grade should passback something without grade'):
        newest_sub.set_grade(None, m.User.resolve(admin_user))

        assert signal.was_send_once
        assert stub_passback.called_amount == 1
        assert stub_passback.args[0][0].get_score_given() is None
        assert stub_passback.args[0][0].get_activity_progress() == 'Submitted'


def test_passback_with_bonus_points(
    lti1p3_provider, describe, logged_in, admin_user, watch_signal,
    stub_function, test_client, session, tomorrow
):
    with describe('setup'), logged_in(admin_user):
        watch_signal(signals.WORK_CREATED, clear_all_but=[])
        watch_signal(signals.USER_ADDED_TO_COURSE, clear_all_but=[])
        signal = watch_signal(
            signals.GRADE_UPDATED,
            clear_all_but=[m.LTI1p3Provider._passback_submission]
        )

        stub_function(
            pylti1p3.service_connector.ServiceConnector,
            'get_access_token', lambda: ''
        )
        stub_passback = stub_function(
            pylti1p3.assignments_grades.AssignmentsGradesService, 'put_grade',
            raise_pylti1p3_exc
        )

        course, course_conn = helpers.create_lti1p3_course(
            test_client, session, lti1p3_provider
        )
        assig = helpers.create_lti1p3_assignment(
            session, course, state='done', deadline=tomorrow
        )
        test_client.req(
            'patch',
            f'/api/v1/assignments/{helpers.get_id(assig)}',
            200,
            data={'max_grade': 15}
        )

        user = helpers.create_lti1p3_user(session, lti1p3_provider)
        course_conn.maybe_add_user_to_course(user, [])

        sub = helpers.to_db_object(
            helpers.create_submission(test_client, assig, for_user=user),
            m.Work
        )

    with describe('can passback bonus points'), logged_in(admin_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{helpers.get_id(sub)}',
            200,
            data={'grade': 14},
        )
        assert signal.was_send_once
        assert stub_passback.called_amount == 1

        assert stub_passback.args[0][0].get_score_given() == 14
        assert stub_passback.args[0][0].get_score_maximum() == 10


def test_delete_submission_of_group(
    lti1p3_provider, describe, logged_in, admin_user, watch_signal,
    stub_function, test_client, session, tomorrow
):
    with describe('setup'), logged_in(admin_user):
        watch_signal(signals.WORK_CREATED, clear_all_but=[])
        watch_signal(signals.GRADE_UPDATED, clear_all_but=[])
        watch_signal(signals.USER_ADDED_TO_COURSE, clear_all_but=[])
        stub_function(
            pylti1p3.service_connector.ServiceConnector,
            'get_access_token', lambda: ''
        )
        stub_passback = stub_function(
            pylti1p3.assignments_grades.AssignmentsGradesService, 'put_grade'
        )

        course, course_conn = helpers.create_lti1p3_course(
            test_client, session, lti1p3_provider
        )
        assig = helpers.create_lti1p3_assignment(
            session, course, state='done', deadline=tomorrow
        )

        # Create some users and let them have individual submissions
        g_user1 = helpers.create_lti1p3_user(session, lti1p3_provider)
        g_user2 = helpers.create_lti1p3_user(session, lti1p3_provider)
        for user in [g_user1, g_user2]:
            course_conn.maybe_add_user_to_course(user, ['Learner'])
            sub = helpers.create_submission(test_client, assig, for_user=user)
            helpers.to_db_object(sub, m.Work).set_grade(
                5.0, m.User.resolve(admin_user)
            )

        # Place the users in a group, with a submission with a different grade
        # than their individual submission.
        gset = helpers.create_group_set(test_client, course, 1, 2, [assig])
        helpers.create_group(test_client, gset, [g_user1, g_user2])
        gsub = helpers.create_submission(test_client, assig, for_user=g_user2)
        helpers.to_db_object(gsub, m.Work).set_grade(
            6.0, m.User.resolve(admin_user)
        )

        session.commit()

    with describe(
        'deleting group submission passes back individual submissions'
    ):
        with logged_in(admin_user):
            test_client.req(
                'delete', f'/api/v1/submissions/{helpers.get_id(gsub)}', 204
            )

        assert stub_passback.called_amount == 2

        # The grade passed back is that of their individual submission
        assert stub_passback.args[0][0].get_score_given() == 5.0
        assert stub_passback.args[1][0].get_score_given() == 5.0


def test_find_assignment_without_resource_id(
    lti1p3_provider, describe, make_function_spy, admin_user, logged_in,
    session, app
):
    with describe('setup'), logged_in(admin_user):
        lti_course = helpers.to_db_object(
            helpers.create_lti_course(session, app, admin_user), m.Course
        )
        spy = make_function_spy(
            flask_sqlalchemy.BaseQuery, 'filter', pass_self=True
        )

    with describe('find_assignment does not query without resource_id'):
        res = lti1p3_provider.find_assignment(lti_course, None, None)
        assert res is None
        assert not spy.called
