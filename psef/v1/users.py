"""
This module defines all API routes with the main directory "users". Thus the
APIs in this module are mostly used to manipulate :class:`.models.User` objects
and their relations. However to manipulate the current logged in user the main
directory "login" should be used.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from flask import request
from sqlalchemy import case, func
from flask_limiter.util import get_remote_address

from . import api
from .. import auth, models, helpers, limiter, features, current_user
from ..models import db
from ..helpers import (
    JSONResponse, jsonify, ensure_json_dict, ensure_keys_in_dict,
    get_from_map_transaction
)
from ..exceptions import APICodes, APIException
from ..permissions import CoursePermission as CPerm
from ..permissions import GlobalPermission as GPerm


@api.route('/users/', methods=['GET'])
@auth.permission_required(GPerm.can_search_users)
@limiter.limit('1 per second', key_func=lambda: str(current_user.id))
def search_users() -> JSONResponse[t.Sequence[models.User]]:
    """Search for a user by name and username.

    .. :quickref: User; Fuzzy search for a user by name and username.

    :query str q: The string to search for, all SQL wildcard are escaped and
        spaces are replaced by wildcards.
    :query int exclude_course: Exclude all users that are in the given course
        from the search results. You need the permission
        `can_list_course_users` on this course to use this parameter.

    :returns: A list of :py:class:`.models.User` objects that match the given
        query string.

    :raises APIException: If the query string less than 3 characters
        long. (INVALID_PARAM)
    :raises PermissionException: If the currently logged in user does not have
        the permission ``can_search_users``. (INCORRECT_PERMISSION)
    :raises RateLimitExceeded: If you hit this end point more than once per
        second. (RATE_LIMIT_EXCEEDED)
    """
    ensure_keys_in_dict(request.args, [('q', str)])
    query = t.cast(str, request.args.get('q'))

    if 'exclude_course' in request.args:
        try:
            exclude_course = int(request.args['exclude_course'])
        except ValueError as exc:
            raise APIException(
                'The "exclude_course" parameter should be an integer', (
                    f'The given parameter "{request.args["exclude_course"]}"'
                    ' could not parsed as an int'
                ), APICodes.INVALID_PARAM, 400
            ) from exc
        auth.ensure_permission(CPerm.can_list_course_users, exclude_course)

        base = db.session.query(models.User).join(
            models.user_course,
            models.user_course.c.user_id == models.User.id,
            isouter=True,
        ).join(
            models.CourseRole,
            models.CourseRole.id == models.user_course.c.course_id,
            isouter=True,
        ).group_by(models.User).having(
            func.sum(
                case(
                    [(models.CourseRole.course_id == exclude_course, 1)],
                    else_=0
                )
            ) == 0
        )
    else:
        base = models.User.query

    base = base.filter(~models.User.virtual, ~models.User.is_test_student)

    return jsonify(helpers.filter_users_by_name(query, base).all())


@api.route('/user', methods=['POST'])
@features.feature_required(features.Feature.REGISTER)
@limiter.limit('5 per minute', key_func=get_remote_address)
def register_user() -> JSONResponse[t.Mapping[str, str]]:
    """Create a new :class:`.models.User`.

    .. :quickref: User; Create a new user by registering it.

    :<json str username: The username of the new user.
    :<json str password: The password of the new user.
    :<json str email: The email of the new user.
    :<json str name: The full name of the new user.

    :>json str access_token: The JWT token that can be used to log in the newly
        created user.

    :raises APIException: If the not all given strings are at least 1
        char. (INVALID_PARAM)
    :raises APIException: If there is already a user with the given
        username. (OBJECT_ALREADY_EXISTS)
    :raises APIException: If the given email is not a valid
        email. (INVALID_PARAM)
    """
    content = ensure_json_dict(request.get_json())
    with get_from_map_transaction(content) as [get, _]:
        username = get('username', str)
        password = get('password', str)
        email = get('email', str)
        name = get('name', str)

    user = models.User.register_new_user(
        username=username, password=password, email=email, name=name
    )
    db.session.commit()

    return jsonify({'access_token': user.make_access_token()})
