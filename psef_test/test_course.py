# SPDX-License-Identifier: AGPL-3.0-only
import uuid

import pytest

import helpers
import psef.models as m
from helpers import (
    create_course, create_marker, create_assignment, create_submission,
    create_user_with_role, create_user_with_perms
)
from psef.permissions import CoursePermission as CPerm

perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)
missing_error = create_marker(pytest.mark.missing_error)


@pytest.mark.parametrize(
    'named_user,expected', [
        (
            'Thomas Schaper', [('Project Software Engineering', 'Student'),
                               ('Besturingssystemen', 'TA'),
                               ('Programmeertalen', 'TA')]
        ),
        (
            'Student1', [('Programmeertalen', 'Student'),
                         ('Inleiding Programmeren', 'Student')]
        ),
        ('admin', []),
        perm_error(error=401)(('NOT_LOGGED_IN', 'ERROR!')),
    ],
    indirect=['named_user']
)
def test_get_all_courses(
    named_user,
    test_client,
    logged_in,
    request,
    expected,
    error_template,
):
    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/courses/',
            error or 200,
            result=error_template if error else list
        )

        if not error:
            found = set()
            for item in res:
                exp = [ex for ex in expected if ex[0] == item['name']]
                assert len(exp) == 1
                exp = exp[0]
                assert exp[1] == item['role']
                found.add(exp)

            assert len(found) == len(res) == len(expected)


def test_get_all_extended_courses(ta_user, test_client, logged_in, session):
    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/courses/',
            200,
            query={'extended': 'true'},
            result=list,
        )
        assert len(res) == 3
        for item in res:
            assert 'assignments' in item
            assert isinstance(item['assignments'], list)
            assert 'group_sets' in item
            assert isinstance(item['group_sets'], list)

    u = create_user_with_perms(session, [], res)
    with logged_in(u):
        test_client.req(
            'get',
            '/api/v1/courses/',
            200,
            query={'extended': 'true'},
            result=[{
                **c,
                'assignments': [],
                'role': str,
            } for c in res]
        )


@pytest.mark.parametrize('add_lti', [True, False])
@pytest.mark.parametrize(
    'named_user,course_name,role', [
        ('Thomas Schaper', 'Programmeertalen', 'TA'),
        ('Thomas Schaper', 'Project Software Engineering', 'Student'),
        ('Student1', 'Programmeertalen', 'Student'),
        perm_error(error=403)((
            'Student1',
            'Project Software Engineering',
            'Student',
        )),
        perm_error(error=403)((
            'admin',
            'Project Software Engineering',
            'Student',
        )),
        perm_error(error=401)((
            'NOT_LOGGED_IN',
            'Project Software Engineering',
            'Student',
        )),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize('via_assignment', [True, False])
@pytest.mark.parametrize('extended', [True, False])
@pytest.mark.parametrize('no_role', [True, False])
def test_get_course_data(
    error_template, request, logged_in, test_client, named_user, course_name,
    role, session, add_lti, canvas_lti1p1_provider, extended, via_assignment,
    no_role
):
    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        course = session.query(m.Course).filter_by(name=course_name).one()
        course_id = course.id
        if not error and add_lti:
            m.CourseLTIProvider.create_and_add(
                course=course,
                lti_provider=canvas_lti1p1_provider,
                lti_context_id='5',
                deployment_id='5',
            )
            session.commit()

        result = {
            'role': role,
            'id': course_id,
            'name': course_name,
            'created_at': str,
            'is_lti': add_lti,
            'virtual': False,
            'lti_provider': canvas_lti1p1_provider if add_lti else None,
            'state': 'visible',
        }

        if extended:
            result.update({
                'assignments': list,
                'group_sets': [],
                'snippets': [],
            })

        if via_assignment:
            # Doesn't support this legacy
            no_role = True
            url = (
                f'/api/v1/assignments/{course.assignments[0].id}/course'
                f'?no_course_in_assignment=true&extended={extended}'
            )
        else:
            url = (
                f'/api/v1/courses/{course.id}?extended={extended}'
                f'&no_course_in_assignment=true&no_role_name={no_role}'
            )

        if no_role:
            del result['role']

        test_client.req(
            'get',
            url,
            error or 200,
            result=error_template if error else result
        )


@pytest.mark.parametrize(
    'named_user', [
        perm_error(error=403)('Student1'),
        'admin',
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize('name', [data_error(None), data_error(5), 'str'])
def test_add_course(
    request, named_user, test_client, logged_in, name, error_template
):
    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif data_err:
        error = 400
    else:
        error = False

    with logged_in(named_user):
        data = {}
        if name is not None:
            data['name'] = name

        course = test_client.req(
            'post',
            f'/api/v1/courses/',
            error or 200,
            data=data,
            result=error_template if error else {
                'id': int,
                'name': name,
                'created_at': str,
                'virtual': False,
                'is_lti': False,
                'lti_provider': None,
                'assignments': [],
                'snippets': [],
                'group_sets': [],
                'state': 'visible',
            }
        )

        if not error:
            test_client.req(
                'get',
                f'/api/v1/courses/{course["id"]}',
                200,
                result={
                    'role': 'Teacher',
                    'id': course['id'],
                    'name': name,
                    'created_at': str,
                    'is_lti': False,
                    'virtual': False,
                    'lti_provider': None,
                    'state': 'visible',
                }
            )


@pytest.mark.parametrize(
    'named_user,expected', [
        ('Student1', ['Haskell', 'Shell', 'Python', 'Go']),
        ('Thomas Schaper', ['Haskell', 'Shell', 'Python', 'Go', 'Erlang']),
        perm_error(error=403)(('admin', [])),
        perm_error(error=401)(('NOT_LOGGED_IN', [])),
    ],
    indirect=['named_user']
)
def test_get_course_assignments(
    prog_course, named_user, test_client, error_template, session, request,
    logged_in, expected
):
    course = session.query(m.Course).filter_by(name='Programmeertalen').one()

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/courses/{course.id}/assignments/',
            error or 200,
            result=error_template if error else list
        )
        if not error:
            found = set()
            for got in res:
                item = [item for item in expected if item == got['name']]
                assert len(item) == 1
                found.add(item[0])

            assert len(expected) == len(res) == len(found)


def test_get_latest_submissions_of_user(
    describe, logged_in, session, test_client, error_template, admin_user,
    student_user
):
    with describe('setup'), logged_in(admin_user):
        course_id = helpers.get_id(helpers.create_course(test_client))

        teacher = helpers.create_user_with_role(session, 'Teacher', course_id)
        student = helpers.create_user_with_role(session, 'Student', course_id)
        other_student = helpers.create_user_with_role(
            session,
            'Student',
            course_id,
        )

        assigs = {}
        for state in ['hidden', 'open', 'done']:
            assig = helpers.create_assignment(
                test_client,
                course_id=course_id,
                state=state,
                deadline='tomorrow',
            )
            assigs[assig['id']] = assig

        all_subs = {
            str(assig_id): [
                helpers.create_submission(
                    test_client,
                    assignment_id=assig_id,
                    for_user=student,
                ) for _ in range(2)
            ]
            for assig_id in assigs
        }

        latest_subs = {
            assig_id: assig_subs[-1:]
            for assig_id, assig_subs in all_subs.items()
        }

        def get_visible(subs):
            return {
                str(assig_id): subs[str(assig_id)]
                for assig_id, assig in assigs.items()
                if assig['state'] != 'hidden'
            }

        all_visible_subs = get_visible(all_subs)

        latest_visible_subs = get_visible(latest_subs)

        no_subs = {str(assig_id): [] for assig_id in assigs}

        deleted_assig_id = helpers.get_id(
            helpers.create_assignment(
                test_client,
                course_id=course_id,
                state='done',
                deadline='tomorrow',
            )
        )
        helpers.create_submission(
            test_client,
            assignment_id=deleted_assig_id,
            for_user=student,
        )
        test_client.req(
            'delete',
            f'/api/v1/assignments/{deleted_assig_id}',
            204,
        )
        base_url = f'/api/v1/courses/{course_id}'

    with describe('nonexisting course'), logged_in(teacher):
        test_client.req(
            'get',
            f'/api/v1/courses/-1/users/{student.id}/submissions/',
            404,
            result=error_template,
        )

    with describe('nonexisting user'), logged_in(teacher):
        test_client.req(
            'get',
            f'/api/v1/courses/{course_id}/users/-1/submissions/',
            404,
            result=error_template,
        )

    with describe('user not in course'), logged_in(teacher):
        test_client.req(
            'get',
            f'{base_url}/users/{student_user.id}/submissions/',
            400,
            result=error_template,
        )

    with describe('teacher should get all submissions'), logged_in(teacher):
        test_client.req(
            'get',
            f'{base_url}/users/{student.id}/submissions/',
            200,
            result=all_subs,
        )
        test_client.req(
            'get',
            f'{base_url}/users/{other_student.id}/submissions/',
            200,
            result=no_subs,
        )

    with describe('student should not get submissions of other student'
                  ), logged_in(student):
        test_client.req(
            'get',
            f'{base_url}/users/{other_student.id}/submissions/',
            403,
            result=error_template,
        )

    with describe('student should get submissions to visible assignments'
                  ), logged_in(student):
        test_client.req(
            'get',
            f'{base_url}/users/{student.id}/submissions/',
            200,
            result=all_visible_subs,
        )

    with describe('student should not get other student submissions'
                  ), logged_in(student):
        test_client.req(
            'get',
            f'{base_url}/users/{other_student.id}/submissions/',
            403,
            result=error_template,
        )

    with describe('should not include deleted assignment'):
        with logged_in(teacher):
            test_client.req(
                'get',
                f'{base_url}/users/{student.id}/submissions/',
                200,
                result=all_subs,
            )

        with logged_in(student):
            test_client.req(
                'get',
                f'{base_url}/users/{student.id}/submissions/',
                200,
                result=all_visible_subs,
            )

    with describe('should respect the latest_only query parameter'):
        with logged_in(teacher):
            test_client.req(
                'get',
                f'{base_url}/users/{student.id}/submissions/?latest_only',
                200,
                result=latest_subs,
            )
            test_client.req(
                'get', (
                    f'{base_url}/users/{other_student.id}/submissions'
                    '/?latest_only'
                ),
                200,
                result=no_subs
            )

        with logged_in(student):
            test_client.req(
                'get',
                f'{base_url}/users/{student.id}/submissions/?latest_only',
                200,
                result=latest_visible_subs,
            )

    with describe('should work for groups'):
        with logged_in(teacher):
            group_assig_id = helpers.get_id(
                helpers.create_assignment(
                    test_client,
                    course_id=course_id,
                    state='done',
                    deadline='tomorrow',
                )
            )
            group_set = helpers.create_group_set(
                test_client,
                course_id,
                min_size=1,
                max_size=3,
                assig_ids=[group_assig_id],
            )
            group = helpers.create_group(
                test_client,
                group_set['id'],
                [student.id, other_student.id],
            )
            group_sub = helpers.create_submission(
                test_client,
                assignment_id=group_assig_id,
                for_user=student,
            )

            test_client.req(
                'get',
                f'{base_url}/users/{student.id}/submissions/?latest_only',
                200,
                result={
                    '__allow_extra__': True,
                    str(group_assig_id): [group_sub],
                },
            )
            test_client.req(
                'get',
                f'{base_url}/users/{group["virtual_user"]["id"]}/submissions/?latest_only',
                200,
                result={
                    '__allow_extra__': True,
                    str(group_assig_id): [group_sub],
                },
            )


@pytest.mark.parametrize(
    'course_n,users',
    [(
        'Programmeertalen', [
            'Thomas Schaper', 'Devin Hillenius', 'Student1', 'Student2',
            'Student3', 'Student4', 'b', 'Robin', 'Œlµo'
        ]
    )],
)
@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=403)('admin'),
        perm_error(error=401)('NOT_LOGGED_IN'),
        'Student1',
    ],
    indirect=['named_user']
)
def test_get_course_users(
    named_user, logged_in, test_client, request, error_template, session,
    course_n, users
):
    course = session.query(m.Course).filter_by(name=course_n).one()
    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/courses/{course.id}/users/',
            error or 200,
            result=error_template if error else list
        )
        if not error:
            assert len(users) == len(res)
            for got, expected in zip(res, sorted(users)):
                assert 'CourseRole' in got
                assert got['User']['name'] == expected


@pytest.mark.parametrize('course_n', ['Programmeertalen'])
@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=403)('Thomas Schaper'),
        perm_error(error=403)('Student1'),
        perm_error(error=403)('admin'),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize(
    'to_add', [
        data_error(error=400)('thomas'),
        data_error(error=400)('student1'),
        data_error(error=404)('non_existing'),
        data_error(error=404)('non_existing@example.com'),
        data_error(error=400)(1),
        ('admin'),
    ]
)
@pytest.mark.parametrize('role_n', ['Student', 'Teacher'])
@pytest.mark.parametrize('include_role', [True, missing_error(False)])
@pytest.mark.parametrize('include_username', [True, missing_error(False)])
def test_add_user_to_course(
    named_user, test_client, logged_in, request, session, course_n, role_n,
    include_role, include_username, to_add, error_template
):
    course = session.query(m.Course).filter_by(name=course_n).one()
    role = session.query(m.CourseRole).filter_by(
        name=role_n, course=course
    ).one()

    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    missing_err = request.node.get_closest_marker('missing_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif missing_err:
        error = 400
    elif data_err:
        error = data_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        data = {}
        if include_username:
            data['username'] = to_add
        if include_role:
            data['role_id'] = role.id

        res = test_client.req(
            'put',
            f'/api/v1/courses/{course.id}/users/',
            error or 201,
            data=data,
            result=error_template if error else {
                'User': dict,
                'CourseRole': dict,
            }
        )
        if error == 404:
            assert res['message'] == 'The requested user was not found'

        if not error:
            res = test_client.req(
                'get',
                f'/api/v1/courses/{course.id}/users/',
                200,
            )
            res = [r for r in res if r['User']['username'] == to_add]
            assert len(res) == 1
            assert res[0]['CourseRole']['name'] == role_n


@pytest.mark.parametrize('course_n', ['Programmeertalen'])
@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=403)('Thomas Schaper'),
        perm_error(error=403)('Student1'),
        perm_error(error=403)('admin'),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize(
    'to_update',
    [
        data_error(error=403)('OWN_EMAIL'),  # You cannot change your own role
        ('student1@example.com'),
        ('admin@example.com'),
        data_error(error=404)(-1),
        data_error(error=400)(True),
        data_error(error=400)(None),
    ]
)
@pytest.mark.parametrize('role_n', ['Student', 'Teacher'])
@pytest.mark.parametrize('include_role', [True, missing_error(False)])
@pytest.mark.parametrize('include_user_id', [True, missing_error(False)])
def test_update_user_in_course(
    logged_in, named_user, test_client, request, session, course_n, role_n,
    include_user_id, include_role, error_template, to_update
):
    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    missing_err = request.node.get_closest_marker('missing_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif missing_err:
        error = 400
    elif data_err:
        error = data_err.kwargs['error']
    else:
        error = False

    course = session.query(m.Course).filter_by(name=course_n).one()
    role = session.query(m.CourseRole).filter_by(
        name=role_n, course=course
    ).one()

    if to_update == 'OWN_EMAIL':
        user_id = 0 if isinstance(named_user, str) else named_user.id
    elif isinstance(to_update, str):
        user_id = session.query(m.User).filter_by(email=to_update).one().id
    else:
        user_id = to_update

    with logged_in(named_user):
        data = {}
        if include_user_id:
            data['user_id'] = user_id
        if include_role:
            data['role_id'] = role.id

        test_client.req(
            'put',
            f'/api/v1/courses/{course.id}/users/',
            error or 204,
            result=error_template if error else None,
            data=data,
        )


@pytest.mark.parametrize('course_n', ['Programmeertalen'])
@pytest.mark.parametrize(
    'named_user,role', [
        ('Robin', 'Teacher'),
        perm_error(error=403)(('Thomas Schaper', 'TA')),
        perm_error(error=403)(('Student1', 'Student')),
        perm_error(error=403)(('admin', None)),
        perm_error(error=401)(('NOT_LOGGED_IN', None)),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize('extended', [True, False])
def test_get_courseroles(
    logged_in, named_user, test_client, request, session, error_template,
    course_n, extended, role
):
    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    course = session.query(m.Course).filter_by(name=course_n).one()
    course_roles = sorted(
        m.CourseRole.query.filter_by(course_id=course.id).all(),
        key=lambda item: item.name
    )

    with logged_in(named_user):
        result = []
        for crole in course_roles:
            item = {
                'name': crole.name,
                'id': int,
                'hidden': False,
                'course': {
                    'name': course_n,
                    'id': int,
                    'created_at': str,
                    'is_lti': False,
                    'virtual': False,
                    'lti_provider': None,
                    'state': 'visible',
                },
            }
            if extended:
                item['perms'] = dict
                item['own'] = crole.name == role
            result.append(item)

        test_client.req(
            'get',
            f'/api/v1/courses/{course.id}/roles/',
            error or 200,
            query={'with_roles': 'true'} if extended else {},
            result=error_template if error else result
        )


@pytest.mark.parametrize('course_n', ['Programmeertalen'])
@pytest.mark.parametrize(
    'named_user', [
        ('Robin'),
        perm_error(error=403)(('Thomas Schaper')),
        perm_error(error=403)(('Student1')),
        perm_error(error=403)(('admin')),
        perm_error(error=401)(('NOT_LOGGED_IN')),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize(
    'role_name', [
        'NEW_ROLE',
        data_error('Student'),
        data_error(None),
        data_error(5),
        data_error(True),
    ]
)
def test_add_courseroles(
    logged_in,
    named_user,
    test_client,
    request,
    session,
    error_template,
    course_n,
    role_name,
):
    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif data_err:
        error = 400
    else:
        error = False

    course = session.query(m.Course).filter_by(name=course_n).one()

    with logged_in(named_user):
        data = {}
        if role_name is not None:
            data['name'] = role_name
        test_client.req(
            'post',
            f'/api/v1/courses/{course.id}/roles/',
            error or 204,
            data=data,
            result=error_template if error else None
        )

        if not error:
            roles = test_client.req(
                'get',
                f'/api/v1/courses/{course.id}/roles/',
                200,
                query={'with_roles': 'true'}
            )

            found_amount = 0
            for role in roles:
                if role['name'] == role_name:
                    found_amount += 1
                    assert (
                        len(role['perms']) == len(
                            session.query(
                                m.Permission
                            ).filter_by(course_permission=True).all()
                        )
                    )
                    for perm_n, value in role['perms'].items():
                        perm = session.query(m.Permission).filter_by(
                            value=CPerm.get_by_name(perm_n),
                        ).one()
                        assert perm.default_value == value
                        assert perm.course_permission

            assert found_amount == 1


@pytest.mark.parametrize('course_n', ['Programmeertalen'])
@pytest.mark.parametrize(
    'named_user,user_role', [
        ('Robin', 'Teacher'),
        perm_error(error=403)(('Student1', 'Student')),
        perm_error(error=403)(('admin', None)),
        perm_error(error=401)(('NOT_LOGGED_IN', None)),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize(
    'role_name', [
        'Teacher',
        'Student',
        data_error(error=404)(1000),
    ]
)
@pytest.mark.parametrize(
    'perm_value', [True, False, missing_error(error=400)(None)]
)
@pytest.mark.parametrize(
    'perm_name', [
        missing_error(error=400)(5),
        'can_edit_course_roles',
        missing_error(error=400)(None),
        'can_grade_work',
        data_error(error=400)('non_existing'),
    ]
)
def test_update_courseroles(
    logged_in, named_user, test_client, request, session, error_template,
    course_n, role_name, user_role, perm_value, perm_name
):
    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    missing_err = request.node.get_closest_marker('missing_error')

    if perm_err:
        error = perm_err.kwargs['error']
    elif missing_err:
        error = missing_err.kwargs['error']
    elif data_err:
        error = data_err.kwargs['error']
    elif user_role == role_name and perm_name == 'can_edit_course_roles':
        error = 403
    else:
        error = False

    course = session.query(m.Course).filter_by(name=course_n).one()
    if isinstance(role_name, str):
        role_id = session.query(m.CourseRole).filter_by(
            name=role_name, course=course
        ).one().id
    else:
        role_id = role_name

    with logged_in(named_user):
        data = {}
        if perm_value is not None:
            data['value'] = perm_value
        if perm_name is not None:
            data['permission'] = perm_name

        test_client.req(
            'patch',
            f'/api/v1/courses/{course.id}/roles/{role_id}',
            error or 204,
            data=data,
            result=error_template if error else None
        )


def test_update_test_student_role(
    teacher_user,
    logged_in,
    test_client,
    describe,
    tomorrow,
    assignment,
    error_template,
):
    c_id = assignment.course.id

    with logged_in(teacher_user):
        test_sub = create_submission(
            test_client,
            assignment.id,
            is_test_submission=True,
        )
        test_user = test_sub['user']

        roles = test_client.req(
            'get',
            f'/api/v1/courses/{c_id}/roles/',
            200,
        )

        role = next(r for r in roles if not r['hidden'])

        test_client.req(
            'put',
            f'/api/v1/courses/{assignment.course.id}/users/',
            400,
            result=error_template,
            data={
                'user_id': test_user['id'],
                'role_id': role['id'],
            },
        )


@pytest.mark.parametrize('course_n', ['Programmeertalen'])
@pytest.mark.parametrize(
    'named_user', [
        ('Robin'),
        perm_error(error=403)(('Student1')),
        perm_error(error=403)(('admin')),
        perm_error(error=401)(('NOT_LOGGED_IN')),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize(
    'role_name', [
        'Observer',
        data_error(error=400)('TA'),
        data_error(error=400)('Student'),
        data_error(error=404, skip_check=True)(1000),
    ]
)
def test_delete_courseroles(
    logged_in, named_user, test_client, request, session, error_template,
    course_n, role_name, teacher_user
):
    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    missing_err = request.node.get_closest_marker('missing_error')

    if perm_err:
        error = perm_err.kwargs['error']
    elif missing_err:
        error = missing_err.kwargs['error']
    elif data_err:
        error = data_err.kwargs['error']
    else:
        error = False

    course = session.query(m.Course).filter_by(name=course_n).one()
    if isinstance(role_name, str):
        role_id = session.query(m.CourseRole).filter_by(
            name=role_name, course=course
        ).one().id
    else:
        role_id = role_name

    with logged_in(teacher_user):
        orig_roles = test_client.req(
            'get',
            f'/api/v1/courses/{course.id}/roles/',
            200,
        )

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/courses/{course.id}/roles/{role_id}',
            error or 204,
            result=error_template if error else None,
        )

    with logged_in(teacher_user):
        new_roles = test_client.req(
            'get',
            f'/api/v1/courses/{course.id}/roles/',
            200,
        )

        assert (new_roles == orig_roles) == bool(error)
        if not error:
            assert not any(role_name == r['name'] for r in new_roles)


@pytest.mark.parametrize(
    'role_name', [
        data_error(error=403)('Student'),
        'Observer',
        'NEW_ROLE',
    ]
)
def test_delete_lti_courseroles(
    role_name, admin_user, session, test_client, logged_in, request,
    error_template, app
):
    data_err = request.node.get_closest_marker('data_error')

    if data_err:
        error = data_err.kwargs['error']
    else:
        error = False

    course = helpers.create_lti_course(session, app, admin_user)

    with logged_in(admin_user):
        test_client.req(
            'post',
            f'/api/v1/courses/{course.id}/roles/',
            204,
            data={'name': 'NEW_ROLE'},
        )

        role_id = session.query(m.CourseRole).filter_by(
            name=role_name, course=course
        ).one().id

        orig_roles = test_client.req(
            'get',
            f'/api/v1/courses/{course.id}/roles/',
            200,
        )

        test_client.req(
            'delete',
            f'/api/v1/courses/{course.id}/roles/{role_id}',
            error or 204,
            result=error_template if error else None,
        )

        new_roles = test_client.req(
            'get',
            f'/api/v1/courses/{course.id}/roles/',
            200,
        )

        assert (new_roles == orig_roles) == bool(error)
        if not error:
            assert not any(role_name == r['name'] for r in new_roles)


@pytest.mark.parametrize(
    'named_user', [
        ('Robin'),
        perm_error(error=403)('Thomas Schaper'),
        perm_error(error=403)('Student1'),
        perm_error(error=403)('admin'),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize('name', [data_error(None), data_error(5), 'str'])
def test_add_assignment(
    request, named_user, test_client, logged_in, name, error_template,
    prog_course, session
):
    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    course = session.query(m.Course).filter_by(name='Programmeertalen').one()
    if data_err:
        error = 400
    elif perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        data = {}
        if name is not None:
            data['name'] = name

        test_client.req(
            'post',
            f'/api/v1/courses/{course.id}/assignments/',
            error or 200,
            data=data,
            result=error_template if error else {
                'id': int,
                'name': name,
                'created_at': str,
                'is_lti': False,
                'lms_name': None,
                'course': dict,
                'course_id': course.id,
                'state': 'hidden',
                'deadline': None,
                'description': str,
                'whitespace_linter': False,
                'cgignore': None,
                'cgignore_version': None,
                'done_type': None,
                'done_email': None,
                'reminder_time': None,
                'fixed_max_rubric_points': None,
                'max_grade': None,
                'group_set': None,
                'division_parent_id': None,
                'auto_test_id': None,
                'files_upload_enabled': True,
                'webhook_upload_enabled': False,
                'cool_off_period': 0.0,
                'amount_in_cool_off_period': 1,
                'max_submissions': None,
                'analytics_workspace_ids': [int],
                'peer_feedback_settings': None,
                'kind': 'normal',
                'send_login_links': False,
                'available_at': None,
            }
        )

        if not error:
            res = test_client.req(
                'get',
                f'/api/v1/courses/{course.id}/assignments/',
                200,
            )

            assert len([r for r in res if r['name'] == name]) == 1


@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=403)('admin'),
    ], indirect=True
)
@pytest.mark.parametrize(
    'q,course_id,users',
    [
        ('UdeNt', True, ['student{}'.format(i) for i in range(1, 5)]),
        ('UdeNt', 'Other', []),  # Other course
        ('admin', True, []),
    ]
)
def test_searching_user_in_course(
    named_user, error_template, logged_in, test_client, q, users, request,
    course_id, assignment, session, teacher_user, tomorrow
):
    perm_marker = request.node.get_closest_marker('perm_error')
    http_marker = request.node.get_closest_marker('http_error')
    teacher_user = teacher_user._get_current_object()

    code = 200 if http_marker is None else http_marker.kwargs['error']
    code = code if perm_marker is None else perm_marker.kwargs['error']

    if course_id is True:
        c_id = assignment.course_id
    else:
        other_course = m.Course.create_and_add(name='Other course')
        session.flush()
        other_course_teacher_role = m.CourseRole.get_by_name(
            course=other_course, name='Teacher'
        ).one()
        teacher_user.courses[other_course.id] = other_course_teacher_role
        session.commit()
        c_id = other_course.id

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/courses/{c_id}/users/?q={q}&course_id={c_id}',
            code,
            result=error_template if code >= 400 else list
        )
        if code < 400:
            assert [i['username'] for i in res] == sorted(users)


def test_searching_test_student_in_course(
    logged_in, test_client, assignment, session, teacher_user, tomorrow
):
    c_id = assignment.course_id

    with logged_in(teacher_user):
        actual_student_name = f'TEST_STUDENT_{str(uuid.uuid4())}'
        student = create_user_with_role(
            session,
            'Student',
            c_id,
            name=actual_student_name,
        )

        assig_id = create_assignment(
            test_client, c_id, 'open', deadline=tomorrow
        )['id']

        res = create_submission(
            test_client,
            assig_id,
            is_test_submission=True,
        )
        test_user_id = res['user']['id']

        res = test_client.req(
            'get',
            f'/api/v1/courses/{c_id}/users/?q=TEST_STUDENT',
            200,
        )

        assert res
        for user in res:
            assert user['id'] != test_user_id
        assert student.id in set(user['id'] for user in res)


def test_course_snippets(
    error_template, logged_in, test_client, session, prog_course, prolog_course
):
    url_base = f'/api/v1/courses/{prog_course.id}'
    teacher_user = create_user_with_perms(
        session, [
            CPerm.can_manage_course_snippets,
            CPerm.can_view_course_snippets,
        ], [prog_course, prolog_course]
    )
    ta_user = create_user_with_perms(
        session, [
            CPerm.can_view_course_snippets,
        ], [prog_course, prolog_course]
    )
    student_user = create_user_with_perms(
        session, [], [prog_course, prolog_course]
    )

    snips = []
    with logged_in(teacher_user):
        # Create snippets
        for i in range(2):
            snips.append({
                'key': f'snippet_key{i}',
                'value': f'snippet_value{i}',
            })
            test_client.req(
                'put',
                f'{url_base}/snippet',
                201,
                data=snips[-1],
                result={'id': int, **snips[-1]},
            )
        snips = test_client.req(
            'get',
            f'{url_base}/snippets/',
            200,
            result=[{'id': int, **snip} for snip in snips],
        )

        # Change value by putting snippet with existing key
        snips[0]['value'] = 'newvalue'
        test_client.req(
            'put',
            f'{url_base}/snippet',
            201,
            data={'key': snips[0]['key'], 'value': snips[0]['value']},
            result=snips[0],
        )
        test_client.req(
            'get',
            f'{url_base}/snippets/',
            200,
            result=snips,
        )

        # Change key, patch by id
        snips[0]['key'] = 'newkey'
        test_client.req(
            'patch',
            f'{url_base}/snippets/{snips[0]["id"]}',
            204,
            data={'key': snips[0]['key'], 'value': snips[0]['value']},
        )
        test_client.req(
            'get',
            f'{url_base}/snippets/',
            200,
            result=snips,
        )

        # Check that duplicate keys raise an error
        test_client.req(
            'patch',
            f'{url_base}/snippets/{snips[0]["id"]}',
            400,
            data={'key': snips[1]['key'], 'value': snips[0]['value']},
            result=error_template,
        )

        # Delete existing snippet
        test_client.req(
            'delete',
            f'{url_base}/snippets/{snips[0]["id"]}',
            204,
        )
        snips = test_client.req(
            'get',
            f'{url_base}/snippets/',
            200,
            result=snips[1:],
        )

        # Shouldn't be able to change other course's snippets
        # This should return a 404 to minimize leaking information
        res = test_client.req(
            'patch',
            f'/api/v1/courses/{prolog_course.id}/snippets/{snips[0]["id"]}',
            404,
            data=snips[0],
            result=error_template,
        )

        res = test_client.req(
            'delete',
            f'/api/v1/courses/{prolog_course.id}/snippets/{snips[0]["id"]}',
            404,
            result=error_template,
        )

    with logged_in(ta_user):
        # TA user should only be able to view snippets
        test_client.req(
            'get',
            f'{url_base}/snippets/',
            200,
            result=snips,
        )

        # But they may not edit them.
        test_client.req(
            'put',
            f'{url_base}/snippet',
            403,
            result=error_template,
            data={'key': snips[0]['key'], 'value': 'new value'},
        )
        test_client.req(
            'patch',
            f'{url_base}/snippets/{snips[0]["id"]}',
            403,
            data={'key': snips[0]['key'], 'value': 'new value'},
            result=error_template,
        )
        test_client.req(
            'delete',
            f'{url_base}/snippets/{snips[0]["id"]}',
            403,
            result=error_template,
        )

    with logged_in(student_user):
        # Student users may not use course snippets
        test_client.req(
            'get',
            f'{url_base}/snippets/',
            403,
            result=error_template,
        )

        # They can also not edit them
        test_client.req(
            'put',
            f'{url_base}/snippet',
            403,
            result=error_template,
            data={'key': snips[0]['key'], 'value': 'new value'},
        )
        test_client.req(
            'patch',
            f'{url_base}/snippets/{snips[0]["id"]}',
            403,
            data={'key': snips[0]['key'], 'value': 'new value'},
            result=error_template,
        )
        test_client.req(
            'delete',
            f'{url_base}/snippets/{snips[0]["id"]}',
            403,
            result=error_template,
        )


def test_create_course(app, monkeypatch, describe, session):
    with describe('setup'):
        new_user = create_user_with_role(session, 'Admin', [])
        monkeypatch.setitem(app.config, 'ADMIN_USER', new_user.username)

        def get_users_in_course(course):
            links = session.query(m.user_course).filter(
                m.user_course.c.course_id.in_(
                    session.query(m.CourseRole.id
                                  ).filter_by(course_id=course.id)
                )
            ).all()
            return [m.User.query.get(link.user_id) for link in links]

    with describe('create new course'):
        course = m.Course.create_and_add(str(uuid.uuid4()))
        session.commit()

        assert new_user.courses[course.id].name == 'Teacher'
        assert len(get_users_in_course(course)) == 1

    with describe('create new course with non existing admin user'):
        monkeypatch.setitem(app.config, 'ADMIN_USER', new_user.username + '2')
        course = m.Course.create_and_add(str(uuid.uuid4()))
        session.commit()
        assert len(get_users_in_course(course)) == 0

    with describe('create new course with non existing course role'):
        monkeypatch.setitem(app.config, 'ADMIN_USER', new_user.username)
        monkeypatch.setitem(app.config, '_DEFAULT_COURSE_ROLES', {})
        course = m.Course.create_and_add(str(uuid.uuid4()))
        session.commit()
        assert len(get_users_in_course(course)) == 0


def test_register_using_registration_link(
    describe, logged_in, teacher_user, admin_user, test_client, session,
    tomorrow, yesterday
):
    with describe('setup'), logged_in(admin_user):
        c1 = create_course(test_client)['id']
        c2 = create_course(test_client)['id']

        role1 = m.CourseRole(
            name=str(uuid.uuid4()),
            course=m.Course.query.get(c1),
            hidden=False
        )
        session.add(role1)
        role2 = m.CourseRole(
            name=str(uuid.uuid4()),
            course=m.Course.query.get(c1),
            hidden=False,
        )
        role2.set_permission(CPerm.can_edit_course_roles, True)
        session.add(role2)

        session.commit()
        r1 = role1.id
        r2 = role2.id

        new_user = helpers.create_user_with_role(session, 'NON_EXISTENT', [])

        register_data = {
            'username': 'NEW_NAME_' + uuid.uuid4().hex,
            'password': uuid.uuid4().hex,
            'email': 'cg@example.com',
            'name': 'NAME123',
        }

    with describe('can create registration link'), logged_in(admin_user):
        link, rv = test_client.req(
            'put',
            f'/api/v1/courses/{c1}/registration_links/',
            200,
            data={'role_id': r1, 'expiration_date': yesterday.isoformat()},
            result={
                'id': str,
                'role': dict,
                'expiration_date': yesterday.isoformat(),
                'allow_register': True,
            },
            include_response=True,
        )
        assert 'already expired' in rv.headers['Warning']
        link_id = link['id']
        base_url = f'/api/v1/courses/{c1}/registration_links/{link_id}'

    with describe('cannot register with expired link'):
        res = test_client.req(
            'post',
            f'{base_url}/user',
            409,
            data=register_data,
        )
        assert 'has expired' in res['message']

    with describe('cannot retrieve single expired link without logging in'):
        test_client.req('get', base_url, 409)

    with describe('can edit registration link'), logged_in(admin_user):
        link, rv = test_client.req(
            'put',
            f'/api/v1/courses/{c1}/registration_links/',
            200,
            data={
                'role_id': r2,
                'expiration_date': tomorrow.isoformat(),
                'id': link_id,
            },
            result={
                'id': link_id,
                'role': dict,
                'allow_register': True,
                'expiration_date': tomorrow.isoformat(),
            },
            include_response=True,
        )
        assert 'will have the permission' in rv.headers['Warning']

    with describe('can retrieve single link without logging in'):
        test_client.req(
            'get',
            base_url,
            200,
            result={
                'id': link_id,
                'expiration_date': tomorrow.isoformat(),
                'role': role2,
                'allow_register': True,
                'course': {
                    'id': c1,
                    '__allow_extra__': True,
                },
            }
        )
        test_client.req(
            'get', f'/api/v1/courses/{c1}/registration_links/', 401
        )

    with describe('can get all registration links'), logged_in(admin_user):
        test_client.req(
            'get',
            f'/api/v1/courses/{c1}/registration_links/',
            200,
            result=[link],
        )

    with describe('cannot register in another course'):
        test_client.req(
            'post',
            f'/api/v1/courses/{c2}/registration_links/{link_id}/user',
            404,
            data=register_data,
        )

    with describe('can register in the correct course'):
        atoken = test_client.req(
            'post',
            f'/api/v1/courses/{c1}/registration_links/{link_id}/user',
            200,
            data=register_data,
        )['access_token']
        test_client.req(
            'get',
            '/api/v1/login',
            200,
            headers={'Authorization': f'Bearer {atoken}'},
            result={
                '__allow_extra__': True,
                'username': register_data['username'],
            }
        )

        # Make sure the new user is enrolled in the course with the correct
        # role.
        test_client.req(
            'get',
            '/api/v1/courses/?extended',
            200,
            headers={'Authorization': f'Bearer {atoken}'},
            result=[{
                '__allow_extra__': True,
                'id': c1,
                'role': role2.name,
            }]
        )

    with describe('Can disable registration'):
        with logged_in(admin_user):
            test_client.req(
                'put',
                f'/api/v1/courses/{c1}/registration_links/',
                200,
                data={
                    'role_id': r2,
                    'expiration_date': tomorrow.isoformat(),
                    'id': link_id,
                    'allow_register': False,
                },
                result={**link, 'allow_register': False},
                include_response=True,
            )

        test_client.req('post', f'{base_url}/user', 403, data=register_data)

        with logged_in(new_user):
            test_client.req('post', f'{base_url}/join', 204)
            test_client.req(
                'get',
                '/api/v1/courses/?extended',
                200,
                result=[{
                    '__allow_extra__': True,
                    'id': c1,
                    'role': role2.name,
                }],
            )
            # Enrolling again changes nothing
            test_client.req('post', f'{base_url}/join', 204)

        # Cannot enroll as a user in the course but with a different role
        with logged_in(admin_user):
            test_client.req('post', f'{base_url}/join', 409)

    with describe('cannot register after link deletion'):
        with logged_in(admin_user):
            test_client.req(
                'delete',
                f'/api/v1/courses/{c1}/registration_links/{link_id}',
                204,
            )
            test_client.req(
                'get',
                f'/api/v1/courses/{c1}/registration_links/',
                200,
                result=[],
            )

        test_client.req(
            'post',
            f'/api/v1/courses/{c1}/registration_links/{link_id}/user',
            404,
        )


def test_delete_role_with_register_link(
    describe, logged_in, teacher_user, admin_user, test_client, session,
    tomorrow
):
    with describe('setup'), logged_in(admin_user):
        c = create_course(test_client)['id']

        role = m.CourseRole(
            name=str(uuid.uuid4()), course=m.Course.query.get(c), hidden=False
        )
        session.add(role)
        session.commit()

        r = role.id

        test_client.req(
            'put',
            f'/api/v1/courses/{c}/registration_links/',
            200,
            data={'role_id': r, 'expiration_date': tomorrow.isoformat()},
            result={
                'id': str,
                'role': dict,
                'expiration_date': tomorrow.isoformat(),
                'allow_register': True,
            },
            include_response=True,
        )

    with describe('cannot delete role connected to register link'
                  ), logged_in(admin_user):
        res = test_client.req(
            'delete',
            f'/api/v1/courses/{c}/roles/{r}',
            400,
        )
        assert 'are still registration links' in res['message']


def test_fail_conditions_email_course_members(
    describe, logged_in, session, test_client, admin_user, stubmailer,
    monkeypatch_celery, monkeypatch
):
    with describe('setup'), logged_in(admin_user):
        course_id = helpers.get_id(create_course(test_client))
        other_course_id = helpers.get_id(create_course(test_client))
        assig_id = helpers.get_id(create_assignment(test_client, course_id))

        mail_user = helpers.create_user_with_perms(
            session, [CPerm.can_email_students], course_id
        )
        user1 = helpers.create_user_with_role(session, 'Student', course_id)
        user2 = helpers.create_user_with_perms(session, [], course_id)
        u_wrong_course = helpers.create_user_with_perms(
            session, [], other_course_id
        )
        test_user = create_submission(
            test_client,
            assig_id,
            is_test_submission=True,
        )['user']

        url = f'/api/v1/courses/{course_id}/email'

    with describe('normal users are not allowed to send emails'):
        with logged_in(user1):
            test_client.req(
                'post',
                url,
                403,
                data={
                    'body': 'hello',
                    'email_all_users': False,
                    'subject': 'no subject',
                    'usernames': [user1.username],
                }
            )

        with logged_in(user2):
            test_client.req('post', url, 403)

        assert not stubmailer.was_called

    with describe('subject and body should be non empty strings'
                  ), logged_in(mail_user):
        for body, subject in [
            ('full', ''),
            ('', ''),
            ('', 'full'),
            (5, 'full'),
            ('full', None),
            ('MISSING', 'full'),
        ]:
            data = {
                'body': body,
                'email_all_users': False,
                'subject': subject,
                'usernames': [user1.username],
            }
            if data['body'] == 'MISSING':
                del data['body']
            test_client.req('post', url, 400, data=data)

        assert not stubmailer.was_called

    with describe('at least one username should be given'
                  ), logged_in(mail_user):
        err = test_client.req(
            'post',
            url,
            400,
            data={
                'email_all_users': False,
                'body': 'MY BODY',
                'subject': 'MY SUBJECT',
                'usernames': [],
            }
        )
        assert 'At least one recipient should be given' in err['message']
        assert not stubmailer.was_called

        # Filtering everybody out should also result in an error.
        err = test_client.req(
            'post',
            url,
            400,
            data={
                'email_all_users': True,
                'body': 'MY BODY',
                'subject': 'MY SUBJECT',
                'usernames': [
                    admin_user.username, user1.username, user2.username,
                    mail_user.username
                ],
            }
        )
        assert 'At least one recipient should be given' in err['message']
        assert not stubmailer.was_called

    with describe('given users should all be enrolled in the course'
                  ), logged_in(mail_user):
        err = test_client.req(
            'post',
            url,
            400,
            data={
                'email_all_users': False,
                'body': 'MY BODY',
                'subject': 'MY SUBJECT',
                'usernames': [user1.username, u_wrong_course.username],
            }
        )

        assert 'Not all given users are enrolled' in err['message']
        assert not stubmailer.was_called

    with describe('Duplicate users are not allowed'), logged_in(mail_user):
        err = test_client.req(
            'post',
            url,
            400,
            data={
                'email_all_users': False,
                'body': 'MY BODY',
                'subject': 'MY SUBJECT',
                'usernames': [user1.username, user1.username],
            }
        )

        assert 'contains duplicates' in err['message']
        assert not stubmailer.was_called

    with describe(
        'Users without a valid email should crash when sending email'
    ), logged_in(mail_user):
        # Raise an exception for empty emails
        monkeypatch.setattr(
            stubmailer, 'send', lambda msg: msg.recipients[0][1][1]
        )
        user1.email = ''

        session.commit()
        tr_id = str(
            helpers.get_id(
                test_client.req(
                    'post',
                    url,
                    200,
                    data={
                        'body': 'bo',
                        'email_all_users': False,
                        'subject': 'body',
                        'usernames': [user1.username, user2.username],
                    }
                )
            )
        )
        test_client.req(
            'get',
            f'/api/v1/task_results/{tr_id}',
            200,
            result={
                'state': 'failed',
                'id': tr_id,
                'result': {
                    'all_users': [user1, user2],
                    'failed_users': [user1],
                    'code': 'MAILING_FAILED',
                    'description': 'Failed to mail some users',
                    'message': 'Failed to email every user',
                },
            }
        )

    with describe('others cannot retrieve task result'):
        with logged_in(user1):
            test_client.req('get', f'/api/v1/task_results/{tr_id}', 403)

        # Original user can keep retrieving
        with logged_in(mail_user):
            test_client.req('get', f'/api/v1/task_results/{tr_id}', 200)

    with describe('cannot send email to the test student'
                  ), logged_in(mail_user):
        test_client.req(
            'post',
            url,
            400,
            data={
                'body': 'bo',
                'email_all_users': False,
                'subject': 'body',
                'usernames': [test_user['username']],
            },
        )


def test_successful_email_course_members(
    describe, logged_in, session, test_client, admin_user, stubmailer,
    monkeypatch_celery
):
    with describe('setup'), logged_in(admin_user):
        course_id = helpers.get_id(create_course(test_client))
        assig_id = helpers.get_id(create_assignment(test_client, course_id))

        mail_user = helpers.create_user_with_perms(
            session, [CPerm.can_email_students], course_id
        )
        user1 = helpers.create_user_with_role(session, 'Student', course_id)
        user2 = helpers.create_user_with_role(session, 'Student', course_id)

        # Create a test student. We don't need the user data as it should never
        # be included in the task results.
        create_submission(
            test_client,
            assig_id,
            is_test_submission=True,
        )

        url = f'/api/v1/courses/{course_id}/email'
        subject = f'SUBJECT: {uuid.uuid4()}'
        body = f'BODY: {uuid.uuid4()}'

    with describe('can email students'), logged_in(mail_user):
        tr_id = str(
            helpers.get_id(
                test_client.req(
                    'post',
                    url,
                    200,
                    data={
                        'body': body,
                        'email_all_users': False,
                        'subject': subject,
                        'usernames': [user1.username, user2.username],
                    }
                )
            )
        )
        test_client.req(
            'get',
            f'/api/v1/task_results/{tr_id}',
            200,
            result={
                'state': 'finished',
                'id': tr_id,
                'result': None,
            }
        )

        assert stubmailer.was_called
        assert stubmailer.times_called == 2
        assert stubmailer.times_connect_called == 1

        for (msg, ), user in zip(stubmailer.args, [user1, user2]):
            recipient, = msg.recipients
            assert recipient == (user.name, user.email)
            assert msg.subject == subject
            assert msg.body == body
            assert msg.reply_to == (mail_user.name, mail_user.email)
            # It should not send an html email
            assert msg.html is None

    with describe('can email all students except'), logged_in(mail_user):
        tr_id = str(
            helpers.get_id(
                test_client.req(
                    'post',
                    url,
                    200,
                    data={
                        'body': body,
                        'email_all_users': True,
                        'subject': subject,
                        'usernames': [user1.username],
                    }
                )
            )
        )
        test_client.req(
            'get',
            f'/api/v1/task_results/{tr_id}',
            200,
            result={
                'state': 'finished',
                'id': tr_id,
                'result': None,
            }
        )

        assert stubmailer.was_called
        # For myself and for user2, and admin user
        assert stubmailer.times_called == 3
        assert stubmailer.times_connect_called == 1

        assert set(arg.recipients[0][1] for arg, in stubmailer.args) == set([
            user2.email, mail_user.email, admin_user.email
        ])

    with describe('can email all students'), logged_in(mail_user):
        tr_id = str(
            helpers.get_id(
                test_client.req(
                    'post',
                    url,
                    200,
                    data={
                        'body': body,
                        'email_all_users': True,
                        'subject': subject,
                        'usernames': [],
                    }
                )
            )
        )
        test_client.req(
            'get',
            f'/api/v1/task_results/{tr_id}',
            200,
            result={
                'state': 'finished',
                'id': tr_id,
                'result': None,
            }
        )
        assert stubmailer.times_called == 4


def test_cannot_add_registration_link_to_lti_course(
    describe, logged_in, admin_user, session, app, tomorrow, test_client
):
    with describe('setup'):
        c = helpers.create_lti_course(session, app, user=admin_user)
        role = m.CourseRole(
            name=str(uuid.uuid4()),
            course=helpers.to_db_object(c, m.Course),
            hidden=False,
        )
        session.add(role)
        session.commit()

    with describe('Cannot add registration link'), logged_in(admin_user):
        err = test_client.req(
            'put',
            f'/api/v1/courses/{helpers.get_id(c)}/registration_links/',
            400,
            data={
                'role_id': helpers.get_id(role),
                'expiration_date': tomorrow.isoformat(),
                'allow_register': False,
            },
        )

        assert ('cannot create course enroll links in LTI courses'
                ) in err['message']


def test_update_name_of_course(
    describe, logged_in, admin_user, test_client, session, app, error_template
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        url = f'/api/v1/courses/{helpers.get_id(course)}'
        lti_course = helpers.create_lti_course(session, app)
        lti_url = f'/api/v1/courses/{helpers.get_id(lti_course)}'

        courses = [course, lti_course]
        student = helpers.create_user_with_role(session, 'Student', courses)
        teacher = helpers.create_user_with_role(session, 'Teacher', courses)
        ta = helpers.create_user_with_role(session, 'TA', courses)

    with describe('Teacher can change name'), logged_in(teacher):
        test_client.req('patch', url, 200, data={'name': 'Teacher name'})
        test_client.req(
            'get',
            url,
            200,
            result={
                '__allow_extra__': True,
                'id': helpers.get_id(course),
                'name': 'Teacher name',
            }
        )

    with describe("TA's and students cannot change name"):
        with logged_in(student):
            test_client.req('patch', url, 403, data={'name': 'Student name'})
        with logged_in(ta):
            test_client.req('patch', url, 403, data={'name': 'TA name'})

        with logged_in(teacher):
            test_client.req(
                'get',
                url,
                200,
                result={
                    '__allow_extra__': True,
                    'id': helpers.get_id(course),
                    'name': 'Teacher name',
                }
            )

    with describe('Cannot change name of LTI course'), logged_in(teacher):
        test_client.req(
            'patch',
            lti_url,
            400,
            data={'name': 'Teacher name'},
            result={
                **error_template,
                'message': 'You cannot rename LTI courses',
            }
        )


def test_archiving_of_course(
    describe, logged_in, admin_user, test_client, session, error_template
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        url = f'/api/v1/courses/{helpers.get_id(course)}'
        student = helpers.create_user_with_role(session, 'Student', course)
        teacher = helpers.create_user_with_role(session, 'Teacher', course)
        ta = helpers.create_user_with_role(session, 'TA', course)

        def ensure_can_see():
            test_client.req('get', url, 200)
            assert helpers.get_id(course) in map(
                helpers.get_id,
                test_client.req('get', '/api/v1/courses/', 200)
            )

    with describe('Coures is visible at first'):
        for user in [student, ta, teacher]:
            with logged_in(user):
                ensure_can_see()

    with describe("TA's and students cannot archive course"):
        with logged_in(student):
            test_client.req('patch', url, 403, data={'state': 'archived'})
        with logged_in(ta):
            test_client.req('patch', url, 403, data={'state': 'archived'})

        with logged_in(teacher):
            test_client.req(
                'get',
                url,
                200,
                result={
                    '__allow_extra__': True, 'id': helpers.get_id(course),
                    'state': 'visible'
                }
            )

    with describe('Teacher can archive course'), logged_in(teacher):
        test_client.req('patch', url, 200, data={'state': 'archived'})
        test_client.req(
            'get',
            url,
            200,
            result={
                '__allow_extra__': True,
                'id': helpers.get_id(course),
                'state': 'archived',
            }
        )

    with describe("Only TA's and teachers can see the course"):
        for user in [ta, teacher]:
            with logged_in(user):
                ensure_can_see()

        with logged_in(student):
            test_client.req('get', url, 403)
            assert helpers.get_id(course) not in map(
                helpers.get_id,
                test_client.req('get', '/api/v1/courses/', 200)
            )

    with describe('Teacher can unarchive course'):
        with logged_in(teacher):
            test_client.req('patch', url, 200, data={'state': 'visible'})

        for user in [ta, student, teacher]:
            with logged_in(user):
                ensure_can_see()

    with describe('Deleting is not (yet) possible'), logged_in(teacher):
        test_client.req(
            'patch',
            url,
            400,
            data={'state': 'deleted'},
            result={
                **error_template,
                'message': 'It is not yet possible to delete a course',
            },
        )
