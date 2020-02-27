"""This module defines all routes needed to manipulate a single group.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

from flask import request

from . import api
from .. import auth, models, features, current_user
from ..helpers import (
    EmptyResponse, ExtendedJSONResponse, get_or_404, add_warning,
    readable_join, ensure_json_dict, extended_jsonify, ensure_keys_in_dict,
    make_empty_response, filter_single_or_404
)
from ..exceptions import (
    APICodes, APIWarnings, APIException, ValidationException
)
from ..permissions import CoursePermission as CPerm


@api.route('/groups/<int:group_id>', methods=['GET'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def get_group(group_id: int) -> ExtendedJSONResponse[models.Group]:
    """Get a group by id.

    .. :quickref: Group; Get a single group by id.

    :param group_id: The id of the group to get.
    :returns: The requested group.
    """
    group = get_or_404(models.Group, group_id)
    auth.ensure_can_view_group(group)
    return extended_jsonify(group, use_extended=models.Group)


@api.route('/groups/<int:group_id>', methods=['DELETE'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def delete_group(group_id: int) -> EmptyResponse:
    """Delete a group by id.

    .. :quickref: Group; Delete a group by id.

    .. warning:: This action is irreversible!

    :param group_id: The id of the group to delete.
    :returns: Nothing
    :raises APIException: If the group has submissions associated with
        it. (INVALID_PARAM)
    """
    group = get_or_404(models.Group, group_id)

    perms = [CPerm.can_edit_others_groups]
    if current_user in group.members or not group.members:
        perms.append(CPerm.can_edit_own_groups)
    auth.ensure_any_of_permissions(
        perms,
        group.group_set.course_id,
    )

    if group.has_a_submission:
        raise APIException(
            (
                'You cannot delete a group with submissions, delete the'
                ' submissions first.'
            ), f'The group {group.id} has submissions', APICodes.INVALID_PARAM,
            400
        )

    models.db.session.delete(group)
    models.db.session.commit()
    return make_empty_response()


@api.route('/groups/<int:group_id>/member', methods=['POST'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def add_member_to_group(group_id: int) -> ExtendedJSONResponse[models.Group]:
    """Add a user (member) to a group.

    .. :quickref: Group; Add a member to a group.

    :param group_id: The id of the group the user should be added to.
    :>json username: The name of the user that should be added to the group.
    :returns: The group with the newly added user.
    """
    group = get_or_404(models.Group, group_id)
    content = ensure_json_dict(request.get_json())
    ensure_keys_in_dict(content, [('username', str)])
    username = t.cast(str, content['username'])
    new_user = filter_single_or_404(
        models.User, models.User.username == username
    )

    auth.ensure_can_edit_members_of_group(group, [new_user])

    if len(group.members) >= group.group_set.maximum_size:
        raise APIException(
            'This group is full', (
                f'This group has a maximum capacity '
                f'of {group.group_set.maximum_size}'
            ), APICodes.ASSIGNMENT_GROUP_FULL, 400
        )

    if models.db.session.query(
        models.Group.contains_users(
            [new_user]
        ).filter_by(group_set=group.group_set).exists()
    ).scalar():
        raise APIException(
            'Member already in a group',
            'One of the members is already in a group for this group set',
            APICodes.INVALID_PARAM, 400
        )

    old_hooks = models.WebhookBase.query.filter(
        models.WebhookBase.user_id == new_user.id,
        t.cast(models.DbColumn[int], models.WebhookBase.assignment_id).in_(
            [a.id for a in group.group_set.assignments]
        ),
    ).all()
    if old_hooks:
        add_warning(
            (
                'The existing webhook{plural_s} for {assigs} will be disabled'
                ' after joining the group.'
            ).format(
                assigs=readable_join([h.assignment.name for h in old_hooks]),
                plural_s='s' if len(old_hooks) > 1 else '',
            ),
            APIWarnings.WEBHOOKS_DISABLED,
        )

    if group.group_set.course.lti_provider is not None:
        existing_hooks = models.WebhookBase.query.filter_by(
            user=group.virtual_user,
        )
        missing_sourcedids = [
            h.assignment for h in existing_hooks if (
                h.assignment_id not in new_user.assignment_results and
                h.assignment.is_lti
            )
        ]
        if missing_sourcedids:
            raise APIException(
                (
                    'You first have to open the assignments: {assigs} from'
                    ' {LMS} before you can join this group'
                ).format(
                    assigs=readable_join([a.name for a in missing_sourcedids]),
                    LMS=group.group_set.course.lti_provider.lms_name,
                ), (
                    "This group has webhooks for these assignments, but you"
                    " didn't open them yet"
                ), APICodes.INVALID_STATE, 400
            )

    group.add_member(new_user)
    models.db.session.commit()
    return extended_jsonify(group, use_extended=models.Group)


@api.route('/groups/<int:group_id>/members/<int:user_id>', methods=['DELETE'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def remove_member_from_group(group_id: int, user_id: int
                             ) -> ExtendedJSONResponse[models.Group]:
    """Remove a user (member) from a group.

    .. :quickref: Group; Remove a member from a group.

    :param group_id: The group the user should be removed from.
    :param user_id: The user that should be removed.
    :returns: The group without the removed user.

    :raises APIException: If the group has submissions associated with it and
        the given user was the last member. (INVALID_STATE)
    """
    group = get_or_404(models.Group, group_id)
    user = get_or_404(models.User, user_id)
    auth.ensure_can_edit_members_of_group(group, [user])

    if len(
        group.members
    ) == group.group_set.minimum_size and group.has_a_submission:
        raise APIException(
            (
                'You cannot shrink a group to smaller than the minimum size'
                ' when the group has a submission.'
            ), (
                f'The group {group.id} has a submission, so it cannot be '
                'smaller than the minimum size for this group set'
            ), APICodes.INVALID_STATE, 400
        )

    group.remove_member(user)

    models.db.session.commit()
    return extended_jsonify(group, use_extended=models.Group)


@api.route('/groups/<int:group_id>/name', methods=['POST'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def update_name_of_group(group_id: int) -> ExtendedJSONResponse[models.Group]:
    """Update the name of the group.

    .. :quickref: Group; Update the name of a group.

    :param group_id: The id of the group that should be updated.
    :>json name: The new name of the group.
    :returns: The group with the updated name.

    :raises ValidationException: If the name of the group has less than 3
        characters. (iNVALID_PARAM)
    """
    group = get_or_404(models.Group, group_id)

    perms = []
    if group.has_as_member(current_user):
        perms.append(CPerm.can_edit_own_groups)
    perms.append(CPerm.can_edit_others_groups)

    auth.ensure_any_of_permissions(
        perms,
        group.group_set.course_id,
    )

    content = ensure_json_dict(request.get_json())
    ensure_keys_in_dict(content, [('name', str)])
    new_name = t.cast(str, content['name'])
    if len(new_name) < 3:
        raise ValidationException(
            'A group name needs consists of at least 3 characters',
            f'The name "{new_name}" is not long enough',
        )
    group.name = new_name

    models.db.session.commit()
    return extended_jsonify(group, use_extended=models.Group)
