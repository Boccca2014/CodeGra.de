"""
This module defines all API routes with the main directory "courses". The APIs
are used to create courses and return information about courses.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t

from flask import request
from mypy_extensions import TypedDict
from flask_limiter.util import get_remote_address

import psef
import psef.auth as auth
import cg_helpers
import psef.models as models
import psef.helpers as helpers
from psef import limiter, current_user
from psef.models import db
from psef.helpers import (
    JSONResponse, EmptyResponse, ExtendedJSONResponse, jsonify,
    ensure_keys_in_dict, make_empty_response, get_from_map_transaction,
    get_json_dict_from_request
)

from . import api
from .. import helpers, limiter, parsers, features
from ..lti.v1_1 import LTICourseRole
from ..exceptions import (
    APICodes, APIWarnings, APIException, PermissionException
)
from ..permissions import CoursePermMap
from ..permissions import CoursePermission as CPerm
from ..permissions import GlobalPermission as GPerm

_UserCourse = TypedDict(  # pylint: disable=invalid-name
    '_UserCourse', {
        'User': models.User,
        'CourseRole': models.CourseRole
    }
)


@api.route('/courses/<int:course_id>/roles/<int:role_id>', methods=['DELETE'])
def delete_role(course_id: int, role_id: int) -> EmptyResponse:
    """Remove a :class:`.models.CourseRole` from the given
    :class:`.models.Course`.

    .. :quickref: Course; Delete a course role from a course.

    :param int course_id: The id of the course
    :returns: An empty response with return code 204

    :raises APIException: If the role with the given ids does not exist.
        (OBJECT_NOT_FOUND)
    :raises APIException: If there are still users with this role.
        (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
        given id. (INCORRECT_PERMISSION)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_roles()

    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )
    role = helpers.filter_single_or_404(
        models.CourseRole,
        models.CourseRole.course_id == course_id,
        models.CourseRole.id == role_id,
        also_error=lambda r: r.hidden,
    )

    if course.lti_provider is not None:
        if LTICourseRole.codegrade_role_name_used(role.name):
            lms = course.lti_provider.lms_name
            raise APIException(
                f'You cannot delete default {lms} roles', (
                    'The course "{}" is an LTI course so it is impossible to '
                    'delete role {}'
                ).format(course.id, role.id), APICodes.INCORRECT_PERMISSION,
                403
            )

    users_with_role = db.session.query(
        models.user_course
    ).filter(models.user_course.c.course_id == role_id).exists()
    if db.session.query(users_with_role).scalar():
        raise APIException(
            'There are still users with this role',
            'There are still users with role {}'.format(role_id),
            APICodes.INVALID_PARAM, 400
        )
    links_with_role = db.session.query(
        models.CourseRegistrationLink
    ).filter_by(course_role_id=role_id).exists()
    if db.session.query(links_with_role).scalar():
        raise APIException(
            'There are still registration links with this role',
            f'The role "{role_id}" cannot be deleted as it is still in use',
            APICodes.INVALID_PARAM, 400
        )

    db.session.delete(role)
    db.session.commit()

    return make_empty_response()


@api.route('/courses/<int:course_id>/roles/', methods=['POST'])
def add_role(course_id: int) -> EmptyResponse:
    """Add a new :class:`.models.CourseRole` to the given
    :class:`.models.Course`.

    .. :quickref: Course; Add a new course role to a course.

    :param int course_id: The id of the course
    :returns: An empty response with return code 204.

    :<json str name: The name of the new course role.

    :raises APIException: If the name parameter was not in the request.
                          (MISSING_REQUIRED_PARAM)
    :raises APIException: If the course with the given id was not found.
                          (OBJECT_NOT_FOUND)
    :raises APIException: If the course already has a role with the submitted
                          name. (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
                                 given id. (INCORRECT_PERMISSION)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_roles()

    content = get_json_dict_from_request()

    ensure_keys_in_dict(content, [('name', str)])
    name = t.cast(str, content['name'])

    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )

    if models.CourseRole.query.filter_by(
        name=name, course_id=course_id
    ).first() is not None:
        raise APIException(
            'This course already has a role with this name',
            'The course "{}" already has a role named "{}"'.format(
                course_id, name
            ), APICodes.INVALID_PARAM, 400
        )

    role = models.CourseRole(name=name, course=course, hidden=False)
    db.session.add(role)
    db.session.commit()

    return make_empty_response()


@api.route('/courses/<int:course_id>/roles/<int:role_id>', methods=['PATCH'])
def update_role(course_id: int, role_id: int) -> EmptyResponse:
    """Update the :class:`.models.Permission` of a given
    :class:`.models.CourseRole` in the given :class:`.models.Course`.

    .. :quickref: Course; Update a permission for a certain role.

    :param int course_id: The id of the course.
    :param int role_id: The id of the course role.
    :returns: An empty response with return code 204.

    :<json str permission: The name of the permission to change.
    :<json bool value: The value to set the permission to (``True`` means the
        specified role has the specified permission).

    :raises APIException: If the value or permission parameter are not in the
                          request. (MISSING_REQUIRED_PARAM)
    :raises APIException: If the role with the given id does not exist or the
                          permission with the given name does not exist.
                          (OBJECT_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
                                 given id. (INCORRECT_PERMISSION)
    """
    content = get_json_dict_from_request()

    auth.CoursePermissions(course_id=course_id).ensure_may_edit_roles()

    ensure_keys_in_dict(content, [('value', bool), ('permission', str)])
    value = t.cast(bool, content['value'])
    permission_name = t.cast(str, content['permission'])
    permission = CPerm.get_by_name(permission_name)

    role = helpers.filter_single_or_404(
        models.CourseRole,
        models.CourseRole.course_id == course_id,
        models.CourseRole.id == role_id,
        also_error=lambda r: r.hidden,
    )

    if (
        current_user.courses[course_id].id == role.id and
        permission == CPerm.can_edit_course_roles
    ):
        raise APIException(
            'You cannot remove this permission from your own role', (
                'The current user is in role {} which'
                ' cannot remove "can_edit_course_roles"'
            ).format(role.id), APICodes.INCORRECT_PERMISSION, 403
        )

    role.set_permission(permission, value)

    db.session.commit()

    return make_empty_response()


@api.route('/courses/<int:course_id>/roles/', methods=['GET'])
def get_all_course_roles(
    course_id: int
) -> JSONResponse[t.Union[t.Sequence[models.CourseRole], t.Sequence[
    t.MutableMapping[str, t.Union[t.Mapping[str, bool], bool]]]]]:
    """Get a list of all :class:`.models.CourseRole` objects of a given
    :class:`.models.Course`.

    .. :quickref: Course; Get all course roles for a single course.

    :param int course_id: The id of the course to get the roles for.
    :returns: An array of all course roles for the given course.

    :>jsonarr perms: All permissions this role has as returned
        by :py:meth:`.models.CourseRole.get_all_permissions`.
    :>jsonarrtype perms: :py:class:`t.Mapping[str, bool]`
    :>jsonarr bool own: True if the current course role is the current users
        course role.
    :>jsonarr ``**rest``: The course role as returned by
        :py:meth:`.models.CourseRole.__to_json__`

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
                                 given id. (INCORRECT_PERMISSION)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_see_roles()

    course_roles: t.Sequence[models.CourseRole]
    course_roles = models.CourseRole.query.filter_by(
        course_id=course_id, hidden=False
    ).order_by(models.CourseRole.name).all()

    if request.args.get('with_roles') == 'true':
        res = []
        for course_role in course_roles:
            json_course = course_role.__to_json__()
            json_course['perms'] = CPerm.create_map(
                course_role.get_all_permissions()
            )
            json_course['own'] = current_user.courses[course_role.course_id
                                                      ] == course_role
            res.append(json_course)
        return jsonify(res)
    return jsonify(course_roles)


@api.route('/courses/<int:course_id>/users/', methods=['PUT'])
def set_course_permission_user(
    course_id: int
) -> t.Union[EmptyResponse, JSONResponse[_UserCourse]]:
    """Set the :class:`.models.CourseRole` of a :class:`.models.User` in the
    given :class:`.models.Course`.

    .. :quickref: Course; Change the course role for a user.

    :param int course_id: The id of the course
    :returns: If the user_id parameter is set in the request the response will
              be empty with return code 204. Otherwise the response will
              contain the JSON serialized user and course role with return code
              201

    :raises APIException: If the parameter role_id or not at least one of
                          user_id and user_email are in the request.
                          (MISSING_REQUIRED_PARAM)
    :raises APIException: If no role with the given role_id or no user
                          with the supplied parameters exists.
                          (OBJECT_ID_NOT_FOUND)
    :raises APIException: If the user was selected by email and the user is
                          already in the course. (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
                                 given id. (INCORRECT_PERMISSION)

    .. todo::
        This function should probability be splitted.
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_users()

    content = get_json_dict_from_request()
    ensure_keys_in_dict(content, [('role_id', int)])
    role_id = t.cast(int, content['role_id'])

    role = helpers.filter_single_or_404(
        models.CourseRole, models.CourseRole.id == role_id,
        models.CourseRole.course_id == course_id
    )

    res: t.Union[EmptyResponse, JSONResponse[_UserCourse]]

    if 'user_id' in content:
        with get_from_map_transaction(content) as [get, _]:
            user_id = get('user_id', int)

        user = helpers.get_or_404(models.User, user_id)

        if user.id == current_user.id:
            raise APIException(
                'You cannot change your own role',
                'The user requested and the current user are the same',
                APICodes.INCORRECT_PERMISSION, 403
            )

        res = make_empty_response()
    elif 'username' in content:
        with get_from_map_transaction(content) as [get, _]:
            username = get('username', str)

        user = helpers.filter_single_or_404(
            models.User, models.User.username == username
        )

        if course_id in user.courses:
            raise APIException(
                'The specified user is already in this course',
                'The user {} is in course {}'.format(user.id, course_id),
                APICodes.INVALID_PARAM, 400
            )

        res = jsonify({
            'User': user,
            'CourseRole': role,
        }, status_code=201)
    else:
        raise APIException(
            'None of the keys "user_id" or "role_id" were found', (
                'The given content ({})'
                ' does  not contain "user_id" or "user_email"'
            ).format(content), APICodes.MISSING_REQUIRED_PARAM, 400
        )

    if user.is_test_student:
        raise APIException(
            'You cannot change the role of a test student',
            f'The user {user.id} is a test student', APICodes.INVALID_PARAM,
            400
        )

    user.courses[role.course_id] = role
    db.session.commit()
    return res


@api.route('/courses/<int:course_id>/users/', methods=['GET'])
@auth.login_required
def get_all_course_users(
    course_id: int
) -> JSONResponse[t.Union[t.List[_UserCourse], t.List[models.User]]]:
    """Return a list of all :class:`.models.User` objects and their
    :class:`.models.CourseRole` in the given :class:`.models.Course`.

    .. :quickref: Course; Get all users for a single course.

    :param int course_id: The id of the course

    :query string q: Search for users matching this query string. This will
        change the output to a list of users.

    :returns: A response containing the JSON serialized users and course roles

    :>jsonarr User:  A member of the given course.
    :>jsonarrtype User: :py:class:`~.models.User`
    :>jsonarr CourseRole: The role that this user has.
    :>jsonarrtype CourseRole: :py:class:`~.models.CourseRole`
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_see_users()
    course = helpers.get_or_404(models.Course, course_id)

    if 'q' in request.args:

        @limiter.limit('1 per second', key_func=lambda: str(current_user.id))
        def get_users_in_course() -> t.List[models.User]:
            query: str = request.args.get('q', '')
            base = course.get_all_users_in_course(include_test_students=False
                                                  ).from_self(models.User)
            return helpers.filter_users_by_name(query, base).all()

        return jsonify(get_users_in_course())

    users = course.get_all_users_in_course(include_test_students=False)

    user_course: t.List[_UserCourse]
    user_course = [
        {
            'User': user,
            'CourseRole': crole
        } for user, crole in users
    ]
    return jsonify(sorted(user_course, key=lambda item: item['User'].name))


@api.route('/courses/<int:course_id>/assignments/', methods=['GET'])
def get_all_course_assignments(
    course_id: int
) -> JSONResponse[t.Sequence[models.Assignment]]:
    """Get all :class:`.models.Assignment` objects of the given
    :class:`.models.Course`.

    .. :quickref: Course; Get all assignments for single course.

    The returned assignments are sorted by deadline.

    :param int course_id: The id of the course
    :returns: A response containing the JSON serialized assignments sorted by
        deadline of the assignment. See
        :py:func:`.models.Assignment.__to_json__` for the way assignments are
        given.

    :raises APIException: If there is no course with the given id.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not see assignments in the
                                 given course. (INCORRECT_PERMISSION)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_see()

    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )

    return jsonify(course.get_all_visible_assignments())


@api.route('/courses/<int:course_id>/assignments/', methods=['POST'])
def create_new_assignment(course_id: int) -> JSONResponse[models.Assignment]:
    """Create a new course for the given assignment.

    .. :quickref: Course; Create a new assignment in a course.

    :param int course_id: The course to create an assignment in.

    :<json str name: The name of the new assignment.

    :returns: The newly created assignment.
    """
    with get_from_map_transaction(get_json_dict_from_request()) as [get, _]:
        name = get('name', str)

    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )

    assig = models.Assignment(
        name=name,
        course=course,
        is_lti=False,
    )
    auth.AssignmentPermissions(assig).ensure_may_add()
    db.session.add(assig)
    db.session.commit()

    return jsonify(assig)


@api.route('/courses/', methods=['POST'])
@auth.permission_required(GPerm.can_create_courses)
def add_course() -> ExtendedJSONResponse[models.Course]:
    """Add a new :class:`.models.Course`.

    .. :quickref: Course; Add a new course.

    :returns: A response containing the JSON serialization of the new course

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not create courses.
                                 (INCORRECT_PERMISSION)
    :raises APIException: If the parameter "name" is not in the request.
        (MISSING_REQUIRED_PARAM)
    """
    with helpers.get_from_request_transaction() as [get, _]:
        name = get('name', str)

    new_course = models.Course.create_and_add(name)
    db.session.flush()

    role = models.CourseRole.get_initial_course_role(new_course)
    current_user.courses[new_course.id] = role
    db.session.commit()

    return ExtendedJSONResponse.make(new_course, use_extended=models.Course)


@api.route('/courses/', methods=['GET'])
@auth.login_required
def get_courses() -> t.Union[JSONResponse[t.List[models.Course]],
                             ExtendedJSONResponse[t.List[models.Course]]]:
    """Return all :class:`.models.Course` objects the current user is a member
    of.

    .. :quickref: Course; Get all courses the current user is enrolled in.

    :returns: A response containing the JSON serialized courses

    :param str extended: If set to ``true``, ``1`` or the empty string all the
        assignments and group sets for each course are also included under the
        key ``assignments`` and ``group_sets`` respectively.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    courses_query = models.Course.update_query_for_extended_jsonify(
        models.Course.query.filter(
            auth.CoursePermissions.ensure_may_see_filter()
        )
    ).order_by(models.Course.created_at.desc(), models.Course.name)

    psef.current_user.load_all_permissions()

    courses = helpers.maybe_apply_sql_slice(courses_query).all()
    assignments = cg_helpers.flatten(c.assignments for c in courses)
    assignment_ids = [a.id for a in assignments]
    with_linter = set(
        assignment_id for assignment_id, in
        models.AssignmentLinter.get_whitespace_linter_query().filter(
            models.AssignmentLinter.assignment_id.in_(assignment_ids)
        ).with_entities(models.AssignmentLinter.assignment_id)
    )
    for assignment in assignments:
        assignment.whitespace_linter_exists = assignment.id in with_linter

    if not helpers.request_arg_true('no_role_name'):
        helpers.add_deprecate_warning(
            'Getting the role of the current user in the requested course is'
            ' deprecated and will be removed in the next major version of'
            ' CodeGrade'
        )
        helpers.jsonify_options.get_options().add_role_to_course = True

    if helpers.extended_requested():
        return ExtendedJSONResponse.make(courses, use_extended=models.Course)
    else:
        return JSONResponse.make(courses)


@api.route('/courses/<int:course_id>', methods=['GET'])
@auth.login_required
def get_course_by_id(
    course_id: int
) -> t.Union[JSONResponse[models.Course], ExtendedJSONResponse[models.Course]]:
    """Return course data for a given :class:`.models.Course`.

    .. :quickref: Course; Get data for a given course.

    :param int course_id: The id of the course

    :returns: A response containing the JSON serialized course

    :>json str role: The name of the role the current user has in this
        course.
    :>json ``**rest``: JSON serialization of :py:class:`psef.models.Course`.

    :raises APIException: If there is no course with the given id.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    course = helpers.get_or_404(models.Course, course_id)
    auth.CoursePermissions(course).ensure_may_see()

    if not helpers.request_arg_true('no_role_name'):
        helpers.add_deprecate_warning(
            'Getting the role of the current user in the requested course is'
            ' deprecated and will be removed in the next major version of'
            ' CodeGrade'
        )
        helpers.jsonify_options.get_options().add_role_to_course = True

    if helpers.extended_requested():
        return ExtendedJSONResponse.make(course, use_extended=models.Course)
    else:
        return JSONResponse.make(course)


@api.route('/courses/<int:course_id>/permissions/', methods=['GET'])
@auth.login_required
def get_permissions_for_course(
    course_id: int,
) -> JSONResponse[CoursePermMap]:
    """Get all the course :class:`.models.Permission` of the currently logged
    in :class:`.models.User`

    .. :quickref: Course; Get all the course permissions for the current user.

    :param int course_id: The id of the course of which the permissions should
        be retrieved.
    :returns: A mapping between the permission name and a boolean indicating if
        the currently logged in user has this permission.
    """
    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )
    return jsonify(CPerm.create_map(current_user.get_all_permissions(course)))


@api.route('/courses/<int:course_id>/group_sets/', methods=['GET'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def get_group_sets(course_id: int
                   ) -> JSONResponse[t.Sequence[models.GroupSet]]:
    """Get the all the :class:`.models.GroupSet` objects in the given course.

    .. :quickref: Course; Get all group sets in the course.

    :param int course_id: The id of the course of which the group sets should
        be retrieved.
    :returns: A list of group sets.
    """
    course = helpers.get_or_404(models.Course, course_id)
    auth.CoursePermissions(course).ensure_may_see()
    return jsonify(course.group_sets)


@api.route('/courses/<int:course_id>/group_sets/', methods=['PUT'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def create_group_set(course_id: int) -> JSONResponse[models.GroupSet]:
    """Create or update a :class:`.models.GroupSet` in the given course id.

    .. :quickref: Course; Create a new group set in the course.

    :>json int minimum_size: The minimum size attribute that the group set
        should have.
    :>json int maximum_size: The maximum size attribute that the group set
        should have.
    :>json int id: The id of the group to update.
    :param course_id: The id of the course in which the group set should be
        created or updated. The course id of a group set cannot change.
    :returns: The created or updated group.
    """
    course = helpers.get_or_404(models.Course, course_id)

    with helpers.get_from_request_transaction() as [get, opt_get]:
        min_size = get('minimum_size', int)
        max_size = get('maximum_size', int)
        old_id = opt_get('id', int)

    if min_size <= 0:
        raise APIException(
            'Minimum size should be larger than 0',
            f'Minimum size "{min_size}" is <= than 0', APICodes.INVALID_PARAM,
            400
        )
    elif max_size < min_size:
        raise APIException(
            'Maximum size is smaller than minimum size', (
                f'Maximum size "{max_size}" is smaller '
                f'than minimum size "{min_size}"'
            ), APICodes.INVALID_PARAM, 400
        )

    if old_id is helpers.MISSING:
        group_set = models.GroupSet(course_id=course.id)
        models.db.session.add(group_set)
        auth.GroupSetPermissions(group_set).ensure_may_add()
    else:
        group_set = helpers.get_or_404(models.GroupSet, old_id)
        auth.GroupSetPermissions(group_set).ensure_may_edit()

        if group_set.course_id != course.id:
            raise APIException(
                'You cannot change the course id of a group set', (
                    f'The group set {group_set.id} is '
                    f'not connected to course {course.id}'
                ), APICodes.INVALID_PARAM, 400
            )

    if group_set.largest_group_size > max_size:
        raise APIException(
            'There are groups larger than the new maximum size',
            f'Some groups have more than {max_size} members',
            APICodes.INVALID_PARAM, 400
        )
    elif group_set.smallest_group_size < min_size:
        raise APIException(
            'There are groups smaller than the new minimum size',
            f'Some groups have less than {min_size} members',
            APICodes.INVALID_PARAM, 400
        )
    group_set.minimum_size = min_size
    group_set.maximum_size = max_size

    models.db.session.commit()

    return jsonify(group_set)


@api.route('/courses/<int:course_id>/snippets/', methods=['GET'])
@auth.permission_required(GPerm.can_use_snippets)
@auth.login_required
def get_course_snippets(course_id: int
                        ) -> JSONResponse[t.Sequence[models.CourseSnippet]]:
    """Get all snippets (:class:`.models.CourseSnippet`) of the given
    :class:`.models.Course`.

    .. :quickref: CourseSnippet; Get all snippets for the given course.

    :returns: An array containing all snippets for the given course.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use snippets.
        (INCORRECT_PERMISSION)
    :raises PermissionException: If the user can not manage snippets for this
        course. (INCORRECT_PERMISSION)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_see_snippets()

    course = helpers.get_or_404(models.Course, course_id)
    return jsonify(course.snippets)


@api.route('/courses/<int:course_id>/snippet', methods=['PUT'])
@auth.permission_required(GPerm.can_use_snippets)
@auth.login_required
def create_course_snippet(course_id: int
                          ) -> JSONResponse[models.CourseSnippet]:
    """Add or modify a :class:`.models.CourseSnippet` by key.

    .. :quickref: CourseSnippet; Add or modify a course snippet.

    :returns: A response containing the JSON serialized snippet and return
              code 201.
    :<json str value: The new value of the snippet.
    :<json str key: The key of the new or existing snippet.

    :raises APIException: If the parameters "key", "value", and/or "course_id"
        were not in the request. (MISSING_REQUIRED_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use snippets
        (INCORRECT_PERMISSION)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_snippets()

    content = get_json_dict_from_request()
    ensure_keys_in_dict(content, [('value', str), ('key', str)])
    key = t.cast(str, content['key'])
    value = t.cast(str, content['value'])

    course = helpers.get_or_404(
        models.Course,
        course_id,
        with_for_update=True,
        with_for_update_of=models.Course,
    )
    snippet = models.CourseSnippet.query.filter_by(
        course=course,
        key=key,
    ).one_or_none()

    if snippet is None:
        snippet = models.CourseSnippet(
            course=course,
            key=key,
            value=value,
        )
        db.session.add(snippet)
    else:
        snippet.value = value

    db.session.commit()

    return jsonify(snippet, status_code=201)


@api.route(
    '/courses/<int:course_id>/snippets/<int:snippet_id>', methods=['PATCH']
)
@auth.permission_required(GPerm.can_use_snippets)
@auth.login_required
def patch_course_snippet(course_id: int, snippet_id: int) -> EmptyResponse:
    """Modify the :class:`.models.CourseSnippet` with the given id.

    .. :quickref: CourseSnippet; Change a snippets key and value.

    :param int snippet_id: The id of the snippet to change.
    :returns: An empty response with return code 204.

    :<json str key: The new key of the snippet.
    :<json str value: The new value of the snippet.

    :raises APIException: If the parameters "key" and/or "value" were not in
        the request. (MISSING_REQUIRED_PARAM)
    :raises APIException: If the snippet does not belong to the current user.
        (INCORRECT_PERMISSION)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use snippets.
        (INCORRECT_PERMISSION)
    :raises APIException: If another snippet with the same key already exists.
        (OBJECT_ALREADY_EXISTS)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_snippets()

    content = get_json_dict_from_request()
    ensure_keys_in_dict(content, [('key', str), ('value', str)])
    key = t.cast(str, content['key'])
    value = t.cast(str, content['value'])

    course = helpers.get_or_404(
        models.Course,
        course_id,
        with_for_update=True,
        with_for_update_of=models.Course
    )
    snip = helpers.get_or_404(
        models.CourseSnippet,
        snippet_id,
        also_error=lambda snip: snip.course_id != course.id
    )

    other = models.CourseSnippet.query.filter_by(
        course=course,
        key=key,
    ).one_or_none()
    if other is not None and other.id != snippet_id:
        raise APIException(
            'A snippet with the same key already exists.',
            'A snippet with key "{}" already exists for course "{}"'.format(
                key, course_id
            ),
            APICodes.OBJECT_ALREADY_EXISTS,
            400,
        )

    snip.key = key
    snip.value = value
    db.session.commit()

    return make_empty_response()


@api.route(
    '/courses/<int:course_id>/snippets/<int:snippet_id>', methods=['DELETE']
)
@auth.permission_required(GPerm.can_use_snippets)
@auth.login_required
def delete_course_snippets(course_id: int, snippet_id: int) -> EmptyResponse:
    """Delete the :class:`.models.CourseSnippet` with the given id.

    .. :quickref: CourseSnippet; Delete a course snippet.

    :param int snippet_id: The id of the snippet
    :returns: An empty response with return code 204

    :raises APIException: If the snippet with the given id does not exist.
        (OBJECT_ID_NOT_FOUND)
    :raises APIException: If the snippet does not belong the current user.
        (INCORRECT_PERMISSION)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use snippets.
        (INCORRECT_PERMISSION)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_snippets()

    course = helpers.get_or_404(
        models.Course,
        course_id,
        with_for_update=True,
        with_for_update_of=models.Course
    )
    snip = helpers.get_or_404(
        models.CourseSnippet,
        snippet_id,
        also_error=lambda snip: snip.course_id != course.id
    )

    db.session.delete(snip)
    db.session.commit()
    return make_empty_response()


@api.route('/courses/<int:course_id>/registration_links/', methods=['GET'])
def get_registration_links(
    course_id: int
) -> JSONResponse[t.Sequence[models.CourseRegistrationLink]]:
    """Get the registration links for the given course.

    .. :quickref: Course; Get the registration links for this course.

    :param course_id: The course id for which to get the registration links.
    :returns: An array of registration links.
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_users()
    course = helpers.get_or_404(
        models.Course, course_id, also_error=lambda c: c.virtual
    )
    return jsonify(course.registration_links)


@api.route(
    '/courses/<int:course_id>/registration_links/<uuid:link_id>',
    methods=['DELETE']
)
def delete_registration_link(
    course_id: int, link_id: uuid.UUID
) -> EmptyResponse:
    """Delete the given registration link.

    .. :quickref: Course; The delete a registration link of the given course.

    :param course_id: The id of the course to which the registration link is
        connected.
    :param link_id: The id of the registration link.
    :returns: Nothing.
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_users()
    course = helpers.get_or_404(
        models.Course, course_id, also_error=lambda c: c.virtual
    )
    link = helpers.get_or_404(
        models.CourseRegistrationLink,
        link_id,
        also_error=lambda l: l.course_id != course.id
    )
    db.session.delete(link)
    db.session.commit()
    return make_empty_response()


@api.route('/courses/<int:course_id>/registration_links/', methods=['PUT'])
def create_or_edit_registration_link(
    course_id: int
) -> JSONResponse[models.CourseRegistrationLink]:
    """Create or edit a registration link.

    .. :quickref: Course; Create or edit a registration link for a course.

    :param course_id: The id of the course in which this link should enroll
        users.
    :>json id: The id of the link to edit, omit to create a new link.
    :>json role_id: The id of the role that users should get when registering
        with this link.
    :>json expiration_date: The date this link should stop working, this date
        should be in ISO8061 format without any timezone information, as it
        will be interpret as a UTC date.
    :returns: The created or edited link.
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_edit_users()
    course = helpers.get_or_404(
        models.Course, course_id, also_error=lambda c: c.virtual
    )
    if course.is_lti:
        raise APIException(
            'You cannot create course enroll links in LTI courses',
            f'The course {course.id} is an LTI course', APICodes.INVALID_PARAM,
            400
        )

    with get_from_map_transaction(get_json_dict_from_request()) as [
        get, opt_get
    ]:
        expiration_date = get('expiration_date', str)
        role_id = get('role_id', int)
        link_id = opt_get('id', str, default=None)
        allow_register = opt_get('allow_register', bool, default=None)

    if link_id is None:
        link = models.CourseRegistrationLink(course=course)
        db.session.add(link)
    else:
        link = helpers.filter_single_or_404(
            models.CourseRegistrationLink,
            models.CourseRegistrationLink.id == uuid.UUID(link_id),
            also_error=lambda l: l.course_id != course.id
        )

    link.course_role = helpers.get_or_404(
        models.CourseRole,
        role_id,
        also_error=lambda r: r.course_id != course.id
    )
    if allow_register is not None:
        link.allow_register = allow_register
    link.expiration_date = parsers.parse_datetime(expiration_date)
    if link.expiration_date < helpers.get_request_start_time():
        helpers.add_warning(
            'The link has already expired.', APIWarnings.ALREADY_EXPIRED
        )

    if link.course_role.has_permission(CPerm.can_edit_course_roles):
        helpers.add_warning(
            (
                'Users that register with this link will have the permission'
                ' to give themselves more permissions.'
            ), APIWarnings.DANGEROUS_ROLE
        )

    db.session.commit()
    return jsonify(link)


def _get_non_expired_link(
    course_id: int, link_id: uuid.UUID
) -> models.CourseRegistrationLink:
    link = helpers.get_or_404(
        models.CourseRegistrationLink,
        link_id,
        also_error=lambda l: l.course_id != course_id or l.course.is_lti,
    )

    if link.expiration_date < helpers.get_request_start_time():
        raise APIException(
            'This registration link has expired.',
            f'The registration link {link.id} has expired',
            APICodes.OBJECT_EXPIRED, 409
        )

    return link


@api.route(
    '/courses/<int:course_id>/registration_links/<uuid:link_id>/join',
    methods=['POST']
)
@auth.login_required
def register_current_user_in_course(
    course_id: int, link_id: uuid.UUID
) -> EmptyResponse:
    """Join a course as the currently logged in user using a registration link.

    .. :quickref: Course; Enroll in this course.

    :param course_id: The id of the course in which you want to enroll.
    :param link_id: The id of the link you want to use to enroll.

    :returns: Nothing.
    """

    link = _get_non_expired_link(course_id, link_id)
    if current_user.is_enrolled(link.course):
        current_role = current_user.courses[link.course_id]
        if current_role.id == link.course_role_id:
            return EmptyResponse.make()

        raise APIException(
            'You are already enrolled in this course with a different role', (
                f'The user {current_user.id} is already enrolled in'
                f' {link.course_id}'
            ), APICodes.INVALID_STATE, 409
        )
    current_user.courses[link.course_id] = link.course_role
    db.session.commit()
    return EmptyResponse.make()


@api.route(
    '/courses/<int:course_id>/registration_links/<uuid:link_id>',
    methods=['GET']
)
def get_register_link(course_id: int, link_id: uuid.UUID
                      ) -> ExtendedJSONResponse[models.CourseRegistrationLink]:
    """Get a registration link.

    .. :quickref: Course; Get the data in a registration link.

    :param course_id: The id of the course to which the registration link is
        connected.
    :param link_id: The id of the registration link.

    :returns: The specified registration link.

    .. note::

        This route can be used without logging in, i.e. you don't have to be
        enrolled in the course to use this route. This route will not work for
        expired registration links.
    """
    link = _get_non_expired_link(course_id, link_id)

    return ExtendedJSONResponse.make(
        link, use_extended=models.CourseRegistrationLink
    )


@api.route(
    '/courses/<int:course_id>/registration_links/<uuid:link_id>/user',
    methods=['POST']
)
@features.feature_required(features.Feature.COURSE_REGISTER)
@limiter.limit('1 per second', key_func=get_remote_address)
def register_user_in_course(course_id: int, link_id: uuid.UUID
                            ) -> JSONResponse[t.Mapping[str, str]]:
    """Register as a new user, and directly enroll in a course.

    .. :quickref: Course; Register as a new user, and enroll in a course.

    :param course_id: The id of the course to which the registration link is
        connected.
    :param link_id: The id of the registration link.
    :>json access_token: The access token that the created user can use to
        login.
    """
    link = _get_non_expired_link(course_id, link_id)

    if not link.allow_register:
        raise PermissionException(
            'You are not allowed to register using this link',
            'This link does not support registration',
            APICodes.INCORRECT_PERMISSION, 403
        )

    with get_from_map_transaction(get_json_dict_from_request()) as [get, _]:
        username = get('username', str)
        password = get('password', str)
        email = get('email', str)
        name = get('name', str)

    user = models.User.register_new_user(
        username=username, password=password, email=email, name=name
    )
    user.courses[link.course_id] = link.course_role
    db.session.commit()

    return jsonify({'access_token': user.make_access_token()})


@api.route('/courses/<int:course_id>/email', methods=['POST'])
@limiter.limit('10 per 10 minutes', key_func=lambda: current_user.id)
@auth.login_required
@features.feature_required(features.Feature.EMAIL_STUDENTS)
def send_students_an_email(course_id: int) -> JSONResponse[models.TaskResult]:
    """Sent the authors in this course an email.

    .. :quickref: Course; Send users in this course an email.

    :>json subject: The subject of the email to send, should not be empty.
    :>json body: The body of the email to send, should not be empty.
    :>json email_all_users: If true all users are emailed, except for those in
        ``usernames``. If ``false`` no users are emailed except for those in
        ``usernames``.
    :>jsonarr usernames: The usernames of the users to which you want to send
        an email (or not if ``email_all_users`` is ``true``).
    :returns: A task result that will send these emails.
    """
    course = helpers.filter_single_or_404(
        models.Course,
        models.Course.id == course_id,
        also_error=lambda c: c.virtual,
    )
    auth.CoursePermissions(course).ensure_may_see()
    auth.ensure_permission(CPerm.can_email_students, course.id)

    with helpers.get_from_request_transaction() as [get, _]:
        subject = get('subject', str)
        body = get('body', str)
        email_all_users = get('email_all_users', bool)
        usernames: t.List[str] = get('usernames', list)

    if helpers.contains_duplicate(usernames):
        raise APIException(
            'The given exceptions list contains duplicates',
            'Each exception can only be mentioned once',
            APICodes.INVALID_PARAM, 400
        )

    exceptions = helpers.get_in_or_error(
        models.User,
        models.User.username,
        usernames,
        same_order_as_given=True,
    )

    if any(course_id not in u.courses for u in exceptions):
        raise APIException(
            'Not all given users are enrolled in this course',
            f'Some given users are not enrolled in course {course_id}',
            APICodes.INVALID_PARAM, 400
        )

    if not (subject and body):
        raise APIException(
            'Both a subject and body should be given', (
                f'One or both of the given subject ({subject}) or body'
                f' ({body}) is empty'
            ), APICodes.INVALID_PARAM, 400
        )

    if email_all_users:
        recipients = course.get_all_users_in_course(
            include_test_students=False
        ).filter(models.User.id.notin_([e.id for e in exceptions])
                 ).with_entities(models.User).all()
    else:
        recipients = exceptions
        # The test student cannot be a member of a group, so we do not need to
        # run this on the expanded group members, and we also do not want to
        # run it when `email_all_users` is true because in that case we let the
        # DB handle it for us.
        if any(r.is_test_student for r in recipients):
            raise APIException(
                'Cannot send an email to the test student',
                'Test student was selected', APICodes.INVALID_PARAM, 400
            )

    recipients = helpers.flatten(r.get_contained_users() for r in recipients)

    if not recipients:
        raise APIException(
            'At least one recipient should be given as recipient',
            'No recipients were selected', APICodes.INVALID_PARAM, 400
        )

    task_result = models.TaskResult(current_user)
    db.session.add(task_result)
    db.session.commit()

    psef.tasks.send_email_as_user(
        receiver_ids=[u.id for u in recipients],
        subject=subject,
        body=body,
        task_result_hex_id=task_result.id.hex,
        sender_id=current_user.id,
    )

    return JSONResponse.make(task_result)


@api.route(
    '/courses/<int:course_id>/users/<int:user_id>/submissions/',
    methods=['GET']
)
@auth.login_required
def get_user_submissions(
    course_id: int, user_id: int
) -> ExtendedJSONResponse[t.Mapping[int, t.Sequence[models.Work]]]:
    """Get all :class:`.models.Work`s by the given :class:`.models.User` in the
    given :class:`.models.Course`.

    .. :quickref: Course; Get submissions by user in a course.

    :qparam boolean latest_only: Only get the latest submission of a
        user. Please use this option if at all possible, as students have a
        tendency to submit many attempts and that can make this route quite
        slow.

    :param int course_id: The id of the course
    :param int user_id: The id of the user
    :returns: A response containing the JSON serialized submissions.

    :raises NotFoundException: If the course does not exist.
        (OBJECT_ID_NOT_FOUND)
    :raises NotFoundException: If the user does not exist.
        (OBJECT_ID_NOT_FOUND)
    :raises APIException: If the given user is not member of the course.
        (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the given user is not the logged in user
        and the logged in user does not have the permission to see others work.
        (INCORRECT_PERMISSION)
    """
    auth.CoursePermissions(course_id=course_id).ensure_may_see()
    course = helpers.get_or_404(models.Course, course_id)
    assignments = course.get_all_visible_assignments()

    user = helpers.get_or_404(models.User, user_id)
    if any(not u.is_enrolled(course_id) for u in user.get_contained_users()):
        raise APIException(
            'User is not enrolled in this course',
            f'User {user_id} not enrolled in course {course_id}',
            APICodes.INVALID_PARAM, 400
        )
    elif not user.contains_user(current_user):
        auth.ensure_permission(CPerm.can_see_others_work, course.id)

    latest_only = helpers.request_arg_true('latest_only')

    def get_subs(query: models.MyQuery[models.Work]) -> t.List[models.Work]:
        return models.Work.update_query_for_extended_jsonify(
            query.filter(
                models.Work.user_submissions_filter(user),
            )
        ).all()

    if latest_only:
        subs = {}
        for assignment in assignments:
            subs[assignment.id] = get_subs(
                assignment.get_all_latest_submissions(),
            )
    else:
        query = models.Work.query.filter(
            models.Work.assignment_id.in_([a.id for a in assignments]),
            # Use _deleted because we already know the assignment exists.
            ~models.Work._deleted,  # pylint: disable=protected-access
        ).order_by(models.Work.created_at.asc())
        subs = {assig.id: [] for assig in assignments}
        for sub in get_subs(query):
            subs[sub.assignment_id].append(sub)

    return ExtendedJSONResponse.make(
        subs,
        use_extended=models.Work,
    )
