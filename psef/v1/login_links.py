"""This module defines all routes for login links.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
from datetime import timedelta

import structlog

import cg_helpers
from cg_json import JSONResponse, ExtendedJSONResponse
from cg_helpers import humanize

from . import api
from .. import auth, models, helpers
from ..models import db
from ..helpers import jsonify_options
from ..exceptions import APICodes, APIException

logger = structlog.get_logger()


@api.route('/login_links/<uuid:login_link_id>')
def get_login_link(login_link_id: uuid.UUID
                   ) -> JSONResponse[models.AssignmentLoginLink]:
    """Get a login link and the connected assignment.

    .. :quickref: Login link; Get a login link and its connected assignment.

    :param login_link_id: The id of the login link you want to get.

    :returns: The requested login link, which will also contain information
              about the connected assignment.
    """
    login_link = helpers.get_or_404(
        models.AssignmentLoginLink,
        login_link_id,
        also_error=lambda l:
        (not l.assignment.is_visible or not l.assignment.send_login_links)
    )

    auth.set_current_user(login_link.user)
    return JSONResponse.make(login_link)


@api.route('/login_links/<uuid:login_link_id>/login', methods=['POST'])
def login_with_link(login_link_id: uuid.UUID
                    ) -> ExtendedJSONResponse[models.User.LoginResponse]:
    """Login with the given login link.

    .. :quickref: Login link; Login with a login link.

    This will only work when the assignment connected to this link is
    available, and the deadline has not expired. The received JWT token will
    only be valid until the 30 minutes after the deadline, and only in the
    course connected to this link.

    .. note::

        The scope of the returned token will change in the future, this will
        not be considered a breaking change.

    :param login_link_id: The id of the login link you want to use to login.

    :returns: The logged in user and an access token.
    """
    login_link = helpers.get_or_404(
        models.AssignmentLoginLink,
        login_link_id,
        also_error=lambda l:
        (not l.assignment.is_visible or not l.assignment.send_login_links)
    )
    assignment = login_link.assignment
    deadline = assignment.deadline

    if assignment.state.is_hidden:
        assignment_id = assignment.id
        db.session.expire(assignment)

        assignment = models.Assignment.query.filter(
            models.Assignment.id == assignment_id
        ).with_for_update().one()
        logger.info(
            'Assignment is still hidden, checking if we have to open it',
            assignment_id=assignment_id,
            state=assignment.state,
            available_at=assignment.available_at,
        )

        # We reload the assignment from the database, so we have to check again
        # if it really still is hidden.
        if assignment.state.is_hidden:
            now = helpers.get_request_start_time()
            if (
                assignment.available_at is not None and
                now >= assignment.available_at
            ):
                assignment.state = models.AssignmentStateEnum.open
                db.session.commit()
            else:
                time_left = cg_helpers.handle_none(
                    cg_helpers.on_not_none(
                        assignment.available_at,
                        lambda avail: humanize.timedelta(
                            avail - now,
                            no_prefix=True,
                        ),
                    ), 'an infinite amount'
                )
                raise APIException(
                    (
                        'The assignment connected to this login link is still'
                        ' not available, please wait for {} for it to become'
                        ' available.'
                    ).format(time_left),
                    f'The assignment {assignment.id} is not available yet',
                    APICodes.INVALID_STATE, 409
                )

    if deadline is None or assignment.deadline_expired:
        raise APIException(
            (
                'The deadline for this assignment has already expired, so you'
                ' can no longer use this link.'
            ), f'The deadline for the assignment {assignment.id} has expired',
            APICodes.OBJECT_EXPIRED, 400
        )

    logger.info(
        'Logging in user with login link', user_to_login=login_link.user
    )

    auth.set_current_user(login_link.user)

    auth.AssignmentPermissions(assignment).ensure_may_see()
    jsonify_options.get_options().add_permissions_to_user = login_link.user

    return ExtendedJSONResponse.make(
        {
            'user': login_link.user,
            'access_token':
                login_link.user.make_access_token(
                    expires_at=deadline + timedelta(minutes=30),
                    for_course=assignment.course,
                ),
        },
        use_extended=models.User,
    )
