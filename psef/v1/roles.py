"""
This module defines all API routes with the main directory "role". The APIs
are used to get roles and add permissions to certain roles. Please note that
all api's work on global roles, not course roles. See the ``course`` routes for
course roles.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from flask import request

import psef.auth as auth
import psef.models as models
import psef.helpers as helpers
from psef import current_user
from psef.errors import APICodes, APIException
from psef.models import db
from psef.helpers import (
    JSONResponse, EmptyResponse, jsonify, ensure_json_dict,
    ensure_keys_in_dict, make_empty_response
)

from . import api
from ..permissions import GlobalPermission as GPerm


@api.route('/roles/', methods=['GET'])
@auth.permission_required(GPerm.can_manage_site_users)
def get_all_roles() -> JSONResponse[t.Sequence[t.Mapping[str, t.Any]]]:
    """Get all global roles with their permissions

    .. :quickref: Role; Get all global roles with their permissions.

    :returns: A object as described in :py:meth:`.models.Role.__to_json__` with
        the following keys added:

    - ``perms``: All permissions of this role, as described in
      :py:meth:`.models.Role.get_all_permissions`.
    - ``own``: Is the given role the role of the current user.

    :raises PermissionException: If the current user does not have the
        ``can_manage_site_users`` permission. (INCORRECT_PERMISSION)
    """
    roles: t.Sequence[models.Role]
    roles = models.Role.query.order_by(models.Role.name).all()

    res = []
    for role in roles:
        res.append(
            {
                **role.__to_json__(),
                'perms': GPerm.create_map(role.get_all_permissions()),
                'own': current_user.role_id == role.id,
            }
        )

    return jsonify(res)


@api.route('/roles/<int:role_id>', methods=['PATCH'])
@auth.permission_required(GPerm.can_manage_site_users)
def set_role_permission(role_id: int) -> EmptyResponse:
    """Update the :class:`.models.Permission` of a given
    :class:`.models.Role`.

    .. :quickref: Role; Update a permission for a certain role.

    :param int role_id: The id of the (non course) role.
    :returns: An empty response with return code 204.

    :<json str permission: The name of the permission to change.
    :<json bool value: The value to set the permission to (``True`` means the
        specified role has the specified permission).

    :raises PermissionException: If the current user does not have the
        ``can_manage_site_users`` permission. (INCORRECT_PERMISSION)
    """
    content = ensure_json_dict(request.get_json())

    ensure_keys_in_dict(content, [('permission', str), ('value', bool)])

    perm = GPerm.get_by_name(t.cast(str, content['permission']))
    value = t.cast(bool, content['value'])

    if (
        current_user.role_id == role_id and perm == GPerm.can_manage_site_users
    ):
        raise APIException(
            'You cannot remove this permission from your own role', (
                'The current user is in role {} which'
                ' cannot remove "can_manage_site_users"'
            ).format(role_id), APICodes.INCORRECT_PERMISSION, 403
        )

    role = helpers.get_or_404(models.Role, role_id)
    role.set_permission(perm, value)

    db.session.commit()

    return make_empty_response()
