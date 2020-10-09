"""
This module defines all API routes with the main directory "linters" and
"linter_comments". These APIs are used to directly communicate about the  state
of linters and their output.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from sqlalchemy.orm import joinedload

from . import api
from .. import auth, models, helpers, site_settings
from ..models import db
from ..helpers import (
    JSONResponse, EmptyResponse, ExtendedJSONResponse, jsonify,
    make_empty_response
)


@api.route('/linters/<linter_id>', methods=['DELETE'])
@site_settings.Opt.LINTERS_ENABLED.required
def delete_linter_output(linter_id: str) -> EmptyResponse:
    """Delete the all the output created by the
    :class:`.models.AssignmentLinter` with the given id.

    .. :quickref: Linter; Delete all linter input for a given linter.

    :param int linter_id: The id of the linter
    :returns: An empty response with return code 204

    :raises APIException: If the linter with the given id does not exist.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use the linters in the
                                 course attached to the linter with the given
                                 id. (INCORRECT_PERMISSION)
    """
    linter = helpers.get_or_404(
        models.AssignmentLinter,
        linter_id,
        also_error=lambda l: not l.assignment.is_visible
    )

    auth.LinterPermissions(linter).ensure_may_delete()

    db.session.delete(linter)
    db.session.commit()

    return make_empty_response()


@api.route('/linters/<linter_id>', methods=['GET'])
@site_settings.Opt.LINTERS_ENABLED.required
def get_linter_state(linter_id: str) -> t.Union[ExtendedJSONResponse[
    models.AssignmentLinter], JSONResponse[models.AssignmentLinter]]:
    """Get the state of the :class:`.models.AssignmentLinter` with the given
    id.

    .. :quickref: Linter; Get the state of a given linter.

    :param str linter_id: The id of the linter
    :returns: A response containing the JSON serialized linter

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use the linters in the
                                 course attached to the linter with the given
                                 id. (INCORRECT_PERMISSION)
    """
    options = None
    if helpers.extended_requested():
        options = [
            joinedload(
                models.AssignmentLinter.tests,
            ).selectinload(
                models.LinterInstance.work,
            )
        ]
    linter = helpers.get_or_404(
        models.AssignmentLinter,
        linter_id,
        options=options,
        also_error=lambda l: not l.assignment.is_visible
    )

    auth.LinterPermissions(linter).ensure_may_see()

    if helpers.extended_requested():
        return helpers.extended_jsonify(
            linter, use_extended=models.AssignmentLinter
        )
    else:
        return jsonify(linter)


@api.route(
    '/linters/<linter_id>/linter_instances/<linter_instance_id>',
    methods=['GET']
)
@site_settings.Opt.LINTERS_ENABLED.required
def get_linter_instance_state(linter_id: str, linter_instance_id: str
                              ) -> ExtendedJSONResponse[models.LinterInstance]:
    """Get the state of the :class:`.models.AssignmentLinter` with the given
    id.

    .. :quickref: Linter; Get the state of a given linter.

    :param str linter_id: The id of the linter
    :returns: A response containing the JSON serialized linter
    """
    linter_instance = helpers.filter_single_or_404(
        models.LinterInstance,
        models.LinterInstance.id == linter_instance_id,
        models.AssignmentLinter.id == linter_id,
        also_error=lambda l: l.work.deleted
    )

    auth.LinterPermissions(linter_instance.tester).ensure_may_see()

    return helpers.extended_jsonify(
        linter_instance, use_extended=models.LinterInstance
    )
