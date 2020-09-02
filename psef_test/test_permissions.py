# SPDX-License-Identifier: AGPL-3.0-only
import os
import sys
import json

import pytest

import psef.auth as a
import psef.models as m
from helpers import create_marker
from psef.errors import APICodes, APIException
from psef.permissions import CoursePermission, GlobalPermission

should_raise = create_marker(pytest.mark.should_raise)


@pytest.mark.parametrize(
    'perm,vals',
    [
        # name, (bs_course (is ta), pse_course (is student), prolog (nothing))
        (CoursePermission.can_submit_own_work, (False, True, False)),
        (CoursePermission.can_see_others_work, (True, False, False)),
        (CoursePermission.can_see_assignments, (True, True, False)),
        should_raise((GlobalPermission.can_add_users, (False, False, False)),
                     )  # This is not a real permission
    ]
)
def test_course_permissions(
    ta_user, bs_course, pse_course, prolog_course, perm, vals, logged_in,
    test_client, request, error_template
):
    should_r = request.node.get_closest_marker('should_raise')
    error = bool(should_r)

    with logged_in(ta_user):
        for course, val in zip([bs_course, pse_course, prolog_course], vals):
            if should_r:
                with pytest.raises(AssertionError):
                    res = ta_user.has_permission(perm, course_id=course.id)
            else:
                assert ta_user.has_permission(perm, course_id=course.id) == val
            res = test_client.req(
                'get',
                f'/api/v1/courses/{course.id}/permissions/',
                200,
                result=dict
            )
            if error:
                assert (
                    perm.name not in res
                ), 'Make sure the object keys are valid'
            else:
                assert res[perm.name
                           ] == val, 'The permission should be correct'

            if not error:
                if val:
                    a.ensure_permission(perm, course_id=course.id)
                else:
                    with pytest.raises(APIException) as err:
                        a.ensure_permission(perm, course_id=course.id)
                    assert err.value.api_code == APICodes.INCORRECT_PERMISSION

    if not error:
        for course, val in zip([bs_course, pse_course, prolog_course], vals):
            with logged_in('NOT_LOGGED_IN'):
                res = test_client.req(
                    'get', f'/api/v1/courses/{course.id}/permissions/', 401
                )
                with pytest.raises(APIException) as err:
                    a.ensure_permission(perm, course_id=course.id)
                assert err.value.api_code == APICodes.NOT_LOGGED_IN


@pytest.mark.parametrize('perm', ['wow_nope'])
def test_non_existing_permission(
    ta_user, bs_course, perm, logged_in, test_client, error_template
):
    with logged_in(ta_user):
        assert perm not in test_client.req(
            'get',
            f'/api/v1/courses/{bs_course.id}/permissions/',
            200,
        ), 'The requested object should not have this value'

        assert perm not in test_client.req(
            'get',
            f'/api/v1/permissions/',
            200,
            query={'type': 'global'},
        ), 'The requested object should not have this value'

        # This api point should raise an error as you actually query
        # permissions and not just all permissions.
        test_client.req(
            'get',
            f'/api/v1/permissions/',
            404,
            query={'permission': perm, 'type': 'course'},
            result=error_template
        )


@pytest.mark.parametrize(
    'perm',
    [CoursePermission.can_grade_work, CoursePermission.can_submit_own_work]
)
def test_non_existing_course(ta_user, bs_course, perm):
    assert not ta_user.has_permission(perm, course_id=bs_course.id * 10)


@pytest.mark.parametrize(
    'perm,vals',
    [(GlobalPermission.can_edit_own_info, (True, True)),
     (GlobalPermission.can_add_users, (False, True))],
)
def test_role_permissions(
    ta_user, admin_user, perm, vals, logged_in, test_client
):
    query = {'type': 'global'}

    for user, val in zip([ta_user, admin_user], vals):
        with logged_in(user):
            res = test_client.req(
                'get', '/api/v1/permissions/', 200, query=query
            )
            assert res[perm.name
                       ] == val, 'Make sure correct permission is returned'

            if val:
                a.ensure_permission(perm, course_id=None)
            else:
                with pytest.raises(APIException) as err:
                    a.ensure_permission(perm, course_id=None)
                assert err.value.api_code == APICodes.INCORRECT_PERMISSION

    with logged_in('NOT_LOGGED_IN'):
        test_client.req('get', '/api/v1/permissions/', 401, query=query)
        with pytest.raises(APIException) as err:
            a.ensure_permission(perm)
        assert err.value.api_code == APICodes.NOT_LOGGED_IN


def test_all_permissions(
    ta_user, bs_course, pse_course, prolog_course, admin_user, student_user,
    logged_in, test_client
):
    for user in [ta_user, admin_user, student_user]:
        with logged_in(user):
            for course in [bs_course, pse_course, prolog_course, None]:
                if course:
                    res = test_client.req(
                        'get', f'/api/v1/courses/{course.id}/permissions/', 200
                    )
                    cls = CoursePermission
                else:
                    res = test_client.req(
                        'get',
                        '/api/v1/permissions/',
                        200,
                        query={'type': 'global'},
                    )
                    cls = GlobalPermission
                for perm, val in res.items():
                    assert val == user.has_permission(
                        cls.get_by_name(perm), course
                    )

    test_client.req('get', '/api/v1/permissions/', 401)

    with logged_in(ta_user):
        test_client.req(
            'get',
            '/api/v1/permissions/',
            400,
            query={'type': 'INVALID_TYPE'},
        )


@pytest.mark.parametrize(
    'permissions',
    [['can_edit_assignment_info', 'can_see_assignments', 'can_grade_work'],
     should_raise(['hello', 5, 'bye'])]
)
@pytest.mark.parametrize(
    'named_user', ['Thomas Schaper', 'Student1', 'admin'],
    indirect=['named_user']
)
def test_get_all_permissions(
    named_user, logged_in, test_client, permissions, error_template, request
):
    err = bool(request.node.get_closest_marker('should_raise'))

    with logged_in(named_user):
        course_perms = test_client.req(
            'get',
            f'/api/v1/permissions/',
            404 if err else 200,
            query={'type': 'course', 'permission': permissions}
        )
        if err:
            return

        assert len(course_perms) == len(named_user.courses)
        for course_id, p_val in course_perms.items():
            for permission, has in p_val.items():
                assert has == named_user.has_permission(
                    CoursePermission.get_by_name(permission), int(course_id)
                )

        course_perms = test_client.req(
            'get',
            f'/api/v1/permissions/',
            200,
            query={'type': 'course'},
        )
        for course_id, p_val in course_perms.items():
            for p in CoursePermission:
                assert p_val[p.name] == named_user.has_permission(
                    CoursePermission.get_by_name(p.name), int(course_id)
                )
