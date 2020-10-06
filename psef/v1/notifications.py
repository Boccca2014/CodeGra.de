"""
This route defines all routes for notifications.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import itertools

from sqlalchemy.orm import defaultload, contains_eager
from typing_extensions import TypedDict

from cg_json import JSONResponse, MultipleExtendedJSONResponse

from . import api
from .. import auth, models, helpers, current_user
from ..models import Notification, db
from ..helpers import request_arg_true


class NotificationsJSON(TypedDict):
    """JSON serialization for all notifications.
    """
    notifications: t.List[Notification]


class HasUnreadNotifcationJSON(TypedDict):
    """JSON serialization for checking if there are any unread notifications.
    """
    has_unread: bool


_MAX_NOTIFICATION_AMOUNT = 100

_ExtendedResponse = MultipleExtendedJSONResponse[
    NotificationsJSON, t.Union[models.CommentReply, Notification]]


def _make_response(json: NotificationsJSON) -> _ExtendedResponse:
    return MultipleExtendedJSONResponse.make(
        json, use_extended=(models.CommentReply, Notification)
    )


@api.route('/notifications/')
@auth.login_required
def get_all_notifications() -> t.Union[_ExtendedResponse,
                                       JSONResponse[HasUnreadNotifcationJSON],
                                       ]:
    """Get all notifications for the current user.

    .. :quickref: Notification; Get all notifications.

    :query boolean has_unread: If considered true a short digest will be send,
        i.e. a single object with one key ``has_unread`` with a boolean
        value. Please use this if you simply want to check if there are unread
        notifications.
    :returns: Either a :class:`.NotificationsJSON` or a
        `HasUnreadNotifcationJSON` based on the ``has_unread`` parameter.
    """
    notifications = db.session.query(Notification).join(
        Notification.comment_reply
    ).filter(
        ~models.CommentReply.deleted,
        Notification.receiver == current_user,
    ).order_by(
        Notification.read.asc(),
        Notification.created_at.desc(),
    ).options(
        contains_eager(Notification.comment_reply),
        defaultload(Notification.comment_reply).defer(
            models.CommentReply.last_edit
        ),
        defaultload(
            Notification.comment_reply,
        ).defaultload(
            models.CommentReply.comment_base,
        ).defaultload(
            models.CommentBase.file,
        ).selectinload(
            models.File.work,
        ),
    ).yield_per(_MAX_NOTIFICATION_AMOUNT)

    def can_see(noti: Notification) -> bool:
        return auth.NotificationPermissions(noti).ensure_may_see.as_bool()

    if request_arg_true('has_unread'):
        has_unread = any(
            map(can_see, notifications.filter(~Notification.read))
        )
        return JSONResponse.make({'has_unread': has_unread})

    return _make_response(
        NotificationsJSON(
            notifications=[
                n for n in
                itertools.islice(notifications, _MAX_NOTIFICATION_AMOUNT)
                if can_see(n)
            ]
        ),
    )


@api.route('/notifications/<int:notification_id>', methods=['PATCH'])
def update_notification(
    notification_id: int
) -> MultipleExtendedJSONResponse[Notification, t.
                                  Union[models.CommentReply, Notification]]:
    """Update the read status for the given notification.

    .. :quickref: Notification; Update a single notification.

    :>json boolean read: Should the notification be considered read.
    :param notification_id: The id of the notification to update.
    :returns: The updated notification.
    """
    with helpers.get_from_request_transaction() as [get, _]:
        read = get('read', bool)

    notification = helpers.get_or_404(
        Notification,
        notification_id,
        also_error=lambda n: (
            n.deleted or not auth.NotificationPermissions(
                n,
            ).ensure_may_see.as_bool()
        )
    )

    auth.NotificationPermissions(notification).ensure_may_edit()
    notification.read = read
    db.session.commit()

    return MultipleExtendedJSONResponse.make(
        notification, use_extended=(models.CommentReply, Notification)
    )


@api.route('/notifications/', methods=['PATCH'])
def update_notifications() -> _ExtendedResponse:
    """Update the read status for the given notifications.

    .. :quickref: Notification; Update multiple notifications in bulk.

    :>jsonarr int id: The id of the notification to update.
    :>jsonarr boolean read: Should the notification be considered read.
    :returns: The updated notifications in the same order as given in the body.
    """
    with helpers.get_from_request_transaction() as [get, _]:
        notifications: t.List[helpers.JSONType] = get('notifications', list)

    notifications_to_update = {}

    for noti_json in notifications:
        with helpers.get_from_map_transaction(
            helpers.ensure_json_dict(noti_json)
        ) as [get, _]:
            notification_id = get('id', int)
            read = get('read', bool)

        notifications_to_update[notification_id] = read

    found_notifications = helpers.get_in_or_error(
        Notification,
        Notification.id,
        list(notifications_to_update.keys()),
        also_error=lambda n: n.deleted,
        as_map=True,
    )
    result = []
    for n_id, read in notifications_to_update.items():
        found_notification = found_notifications[n_id]
        auth.NotificationPermissions(found_notification).ensure_may_edit()
        found_notification.read = read
        result.append(found_notification)

    db.session.commit()

    return _make_response({'notifications': result})
