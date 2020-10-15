# SPDX-License-Identifier: AGPL-3.0-only
import uuid

import pytest

import psef as p
import helpers
import psef.errors as e
import psef.models as m
from helpers import create_marker

perm_error = create_marker(pytest.mark.perm_error)
http_error = create_marker(pytest.mark.http_error)
data_error = create_marker(pytest.mark.data_error)


@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        'Student1',
        perm_error(error=401)('NOT_LOGGED_IN'),
        'admin',
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'q,users',
    [
        ('UdeNt', ['student{}'.format(i) for i in range(1, 5)]),
        ('s chap', ['thomas']),
        ('s%chap', []),
        http_error(error=400)(('ko', [])),  # Too short
        http_error(error=400)(('            ', [])),  # Too short
        http_error(error=400)(('ko ', [])),  # Too short
        http_error(error=400)(('\t\t   ', [])),  # Too short
    ]
)
def test_searching_users(
    named_user, error_template, logged_in, test_client, q, users, request
):
    perm_marker = request.node.get_closest_marker('perm_error')
    http_marker = request.node.get_closest_marker('http_error')

    code = 200 if http_marker is None else http_marker.kwargs['error']
    code = code if perm_marker is None else perm_marker.kwargs['error']

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/users/?q={q}',
            code,
            result=error_template if code >= 400 else list
        )
        if code < 400:
            assert [i['username'] for i in res] == sorted(users)


@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=403)('admin'),
    ], indirect=True
)
@pytest.mark.parametrize(
    'q,course_id,users', [
        ('UdeNt', True, []),
        ('UdeNt', 'Other', ['student{}'.format(i) for i in range(1, 5)]),
        ('admin', True, ['admin']),
        perm_error(error=400)(('admin', 'notanint', 'NOT IMPORTANT')),
    ]
)
def test_searching_user_excluding_course(
    named_user, error_template, logged_in, test_client, q, users, request,
    course_id, assignment, session, teacher_user
):
    perm_marker = request.node.get_closest_marker('perm_error')
    http_marker = request.node.get_closest_marker('http_error')
    teacher_user = teacher_user._get_current_object()

    code = 200 if http_marker is None else http_marker.kwargs['error']
    code = code if perm_marker is None else perm_marker.kwargs['error']

    if course_id is True:
        c_id = assignment.course_id
    elif course_id == 'Other':
        other_course = m.Course.create_and_add(name='Other course')
        session.flush()
        other_course_teacher_role = m.CourseRole.query.filter_by(
            course_id=other_course.id, name='Teacher'
        ).one()
        teacher_user.courses[other_course.id] = other_course_teacher_role
        session.commit()
        c_id = other_course.id
    else:
        c_id = course_id

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/users/?q={q}&exclude_course={c_id}',
            code,
            result=error_template if code >= 400 else list
        )
        if code < 400:
            assert [i['username'] for i in res] == sorted(users)


def test_searching_users_rate_limit(
    ta_user, error_template, logged_in, test_client, app
):
    # Multiple `app.app_context` calls are used to make sure the `g` object
    # from flask is reset. This is necessary as our rate limiter only checks
    # the limit once per request and does this using this `g` object.
    with logged_in(ta_user):
        with app.app_context():
            res = test_client.req(
                'get',
                f'/api/v1/users/?q=query',
                200,
                result=list,
            )
        with app.app_context():
            # We should be hitting the limit now.
            res = test_client.req(
                'get', f'/api/v1/users/?q=query', 429, result=error_template
            )
            assert res['code'] == e.APICodes.RATE_LIMIT_EXCEEDED.name


def test_searching_test_student(
    logged_in, session, error_template, test_client, request, admin_user,
    ta_user, tomorrow, assignment
):
    with logged_in(admin_user):
        course = helpers.create_course(test_client)
        teacher = helpers.create_user_with_role(session, 'Teacher', course)

        actual_student_name = f'TEST_STUDENT_{str(uuid.uuid4())}'
        student = helpers.create_user_with_role(
            session, 'Student', course, name=actual_student_name
        )

    with logged_in(teacher):
        assig_id = helpers.create_assignment(
            test_client, course, 'open', deadline=tomorrow
        )['id']

        res = helpers.create_submission(
            test_client,
            assignment_id=assig_id,
            is_test_submission=True,
        )
        test_user_id = res['user']['id']

        res = test_client.req(
            'get',
            '/api/v1/users/?q=TEST_STUDENT',
            200,
        )

        assert res
        for user in res:
            assert user['id'] != test_user_id
        assert student.id in set(user['id'] for user in res)


@pytest.mark.parametrize(
    'username, taken',
    [
        data_error(error=400)(('thomas', True)),
        # This exact username is not taken, but case insensitively it is
        data_error(error=400)(('RoBiN', True)),
        ('NOT TAKEN', False),
        ('NoT TaKeN!', False),
        data_error(error=400)(('', False)),
        data_error(error=400)((None, False)),
    ]
)
@pytest.mark.parametrize(
    'email', [
        data_error(error=400)('ERR'),
        data_error(error=400)(''),
        data_error(error=400)(None),
        'good@email',
    ]
)
@pytest.mark.parametrize(
    'name', [
        data_error(error=400)(''),
        data_error(error=400)(None),
        'good',
    ]
)
@pytest.mark.parametrize(
    'password', [
        data_error(error=400)(''),
        data_error(error=400)(None),
        data_error(error=400)('weak'),
        'STRONG@#$!#$qwi09aewfjsdf9023u923j4ljksda',
    ]
)
def test_register_user(
    username, test_client, error_template, name, password, email, request, app,
    session, monkeypatch, taken
):
    p.site_settings.Opt.REGISTER_ENABLED.set_and_commit_value(True)

    data_err = request.node.get_closest_marker('data_error')
    code = 200 if data_err is None else data_err.kwargs['error']

    data = {}
    if name is not None:
        data['name'] = name
    if username is not None:
        data['username'] = username
    if password is not None:
        data['password'] = password
    if email is not None:
        data['email'] = email

    res = test_client.req(
        'post',
        '/api/v1/user',
        code,
        data=data,
        result=None if code >= 400 else {'access_token': str}
    )

    if code >= 400:
        assert isinstance(res['code'], str)
        assert isinstance(res['description'], str)
        assert isinstance(res['message'], str)
    else:
        access_token = res['access_token']
        # Make sure we can log in with the newly given token
        test_client.req(
            'get',
            '/api/v1/login',
            200,
            headers={'Authorization': f'Bearer {access_token}'}
        )

        new_user = m.User.query.filter_by(username=username).one()
        assert new_user.name == name, 'The given name should be used'
        assert new_user.email == email, 'The given email should be used'

        # Make sure we can log in with the given password
        test_client.req(
            'post',
            '/api/v1/login',
            200,
            data={
                'username': username,
                'password': password,
            }
        )

    if code >= 400 and not taken:
        assert session.query(m.User).filter_by(
            username=username
        ).first() is None, ('The new user should not have been created')
    elif code >= 400:
        assert session.query(m.User).filter_by(
            username=username
        ).one().name != name, ('The old user should be preserved')
