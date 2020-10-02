"""
This module defines all API routes with for user settings.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from flask import request

from cg_json import JSONResponse
from cg_flask_helpers import EmptyResponse

from . import api
from .. import auth, models, current_user
from ..helpers import get_from_request_transaction


def _get_user() -> 'models.User':
    token = request.args.get('token', None)
    if token is not None:
        return models.NotificationsSetting.verify_settings_change_token(token)
    else:
        auth.ensure_logged_in()
        return current_user


@api.route('/settings/notification_settings/', methods=['GET'])
def get_notification_settings(
) -> JSONResponse[models.NotificationSettingJSON]:
    """Update preferences for notifications.

    .. :quickref: User Setting; Get the preferences for notifications.

    :query str token: The token with which you want to get the preferences,
        if not given the preferences are retrieved for the currently logged in
        user.
    :returns: The preferences for the user as described by the ``token``.
    """
    user = _get_user()

    return JSONResponse.make(
        models.NotificationsSetting.get_notification_setting_json_for_user(
            user,
        )
    )


@api.route('/settings/notification_settings/', methods=['PATCH'])
def update_notification_settings() -> EmptyResponse:
    """Update preferences for notifications.

    .. :quickref: User Setting; Update preferences for notifications.

    :query str token: The token with which you want to update the preferences,
        if not given the preferences are updated for the currently logged in
        user.
    :>json string reason: The :class:`.models.NotificationReasons` which you
        want to update.
    :>json string value: The :class:`.models.EmailNotificationTypes` which
        should be the new value.
    :returns: Nothing.
    """
    user = _get_user()

    with get_from_request_transaction() as [get, _]:
        reason = get('reason', models.NotificationReasons)
        value = get('value', models.EmailNotificationTypes)

    models.NotificationsSetting.update_for_user(
        user=user, reason=reason, value=value
    )
    models.db.session.commit()

    return EmptyResponse.make()


@api.route('/settings/ui_preferences/', methods=['GET'])
def get_user_preferences() -> JSONResponse[t.Mapping[str, t.Optional[bool]]]:
    user = _get_user()

    return JSONResponse.make(
        {
            pref.name: value
            for pref, value in
            models.UIPreference.get_preferences_for_user(user).items()
        }
    )


@api.route('/settings/ui_preferences/', methods=['PATCH'])
def update_user_preferences() -> EmptyResponse:
    user = _get_user()

    with get_from_request_transaction() as [get, _]:
        name = get('name', models.UIPreferenceName)
        value = get('value', bool)

    models.UIPreference.update_for_user(user=user, name=name, value=value)
    models.db.session.commit()

    return EmptyResponse.make()
