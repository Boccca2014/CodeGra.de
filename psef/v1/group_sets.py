"""This module defines all routes needed to get or manipulate group sets. A
group set contains all groups. Multiple assignments (from the same course) can
be connected to a single group set. This makes it possible to have multiple
assignments share groups.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

from . import api
from .. import auth, models, helpers, features, current_user
from ..helpers import (
    JSONResponse, EmptyResponse, ExtendedJSONResponse, jsonify, get_or_404,
    get_in_or_error, extended_jsonify, make_empty_response
)
from ..exceptions import APICodes, APIException
from ..permissions import CoursePermission as CPerm


@api.route('/group_sets/<int:group_set_id>/group', methods=['POST'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def create_group(group_set_id: int) -> ExtendedJSONResponse[models.Group]:
    """Create a group for the given group set.

    .. :quickref: GroupSet; Create a group in a given group set.

    :param group_set_id: The id of the group set where the new group should be
        placed in.
    :>json member_ids: A list of user ids of users that should be the initial
        members of the group. This may be an empty list.
    :>json name: The name of the group. This key is optional and a random
        'funny' name will be generated when not given.
    :returns: The newly created group.
    """
    group_set = get_or_404(models.GroupSet, group_set_id)
    # The permissions in this function are not really easy to fit into the
    # permission checker class model. So simply check if the user can see the
    # course here.
    auth.CoursePermissions(group_set.course).ensure_may_see()
    auth.ensure_permission(CPerm.can_create_groups, group_set.course_id)

    with helpers.get_from_request_transaction() as [get, opt_get]:
        member_ids = get('member_ids', list)
        group_name = opt_get('name', str, default=None)

    if any(not isinstance(m, int) for m in member_ids):
        raise APIException(
            'All member ids should be integers', 'Some ids were not integers',
            APICodes.INVALID_PARAM, 400
        )

    if any(m_id != current_user.id for m_id in member_ids):
        auth.ensure_permission(
            CPerm.can_edit_others_groups, group_set.course_id
        )

    members = get_in_or_error(
        models.User, t.cast(models.DbColumn[int], models.User.id),
        t.cast(t.List[int], member_ids)
    )

    group = models.Group.create_group(group_set, members, name=group_name)
    auth.ensure_can_edit_members_of_group(group, members)

    models.db.session.add(group)
    models.db.session.commit()

    return extended_jsonify(group, use_extended=models.Group)


@api.route('/group_sets/<int:group_set_id>/groups/', methods=['GET'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def get_groups(group_set_id: int
               ) -> ExtendedJSONResponse[t.Sequence[models.Group]]:
    """Get all groups for a given group set.

    .. :quickref: GroupSet; Get the groups of this assignment.

    :param group_set_id: The group set for which the groups should be returned.
    :returns: All the groups for the given group set.
    """
    group_set = get_or_404(models.GroupSet, group_set_id)
    auth.GroupSetPermissions(group_set).ensure_may_see()

    groups: t.Sequence[models.Group]
    try:
        auth.ensure_permission(
            CPerm.can_view_others_groups,
            group_set.course_id,
        )
    except auth.PermissionException:
        groups = models.Group.contains_users(
            [current_user],
            include_empty=True,
        ).filter_by(group_set_id=group_set.id).order_by(
            models.Group.created_at,
        ).all()
    else:
        groups = group_set.groups

    return extended_jsonify(groups, use_extended=models.Group)


@api.route('/group_sets/<int:group_set_id>', methods=['GET'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def get_group_set(group_set_id: int) -> JSONResponse[models.GroupSet]:
    """Return the given :class:`.models.GroupSet`.

    .. :quickref: GroupSet; Get a single group set by id.

    :param int group_set_id: The id of the group set
    :returns: A response containing the JSON serialized group set.
    """
    group_set = get_or_404(models.GroupSet, group_set_id)
    auth.GroupSetPermissions(group_set).ensure_may_see()
    return jsonify(group_set)


@api.route('/group_sets/<int:group_set_id>', methods=['DELETE'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def delete_group_set(group_set_id: int) -> EmptyResponse:
    """Delete the given :class:`.models.GroupSet`.

    .. :quickref: GroupSet; Delete a single group set by id.

    You can only delete a group set if there are no groups in the set and no
    assignment is connected to the group set.

    :param int group_set_id: The id of the group set
    """
    group_set = get_or_404(models.GroupSet, group_set_id)
    auth.GroupSetPermissions(group_set).ensure_may_delete()

    if group_set.assignments:
        raise APIException(
            'Some assignments are still connected to this group set',
            'The assignments {} are still connected to group_set {}'.format(
                ', '.join(str(a.id) for a in group_set.assignments),
                group_set.id
            ), APICodes.INVALID_STATE, 400
        )

    if group_set.groups:
        raise APIException(
            'The group set still contains groups, remove these first',
            f'The group set {group_set.id} still contains groups',
            APICodes.INVALID_STATE, 400
        )

    models.db.session.delete(group_set)
    models.db.session.commit()

    return make_empty_response()
