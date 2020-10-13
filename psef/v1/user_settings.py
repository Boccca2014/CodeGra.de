"""
This module defines all API routes with for user settings.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from flask import request

import cg_request_args as rqa
from cg_json import JSONResponse
from cg_flask_helpers import EmptyResponse

from . import api
from .. import auth, models, current_user


def _get_user() -> 'models.User':
    token = request.args.get('token', None)
    if token is not None:
        return models.NotificationsSetting.verify_settings_change_token(token)
    else:
        auth.ensure_logged_in()
        return current_user


@api.route('/settings/notification_settings/', methods=['GET'])
@rqa.swaggerize('get_all_notification_settings')
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
@rqa.swaggerize('patch_notification_setting')
def update_notification_settings() -> EmptyResponse:
    """Update preferences for notifications.

    .. :quickref: User Setting; Update preferences for notifications.

    :query str token: The token with which you want to update the preferences,
        if not given the preferences are updated for the currently logged in
        user.
    :returns: Nothing.
    """
    data = rqa.FixedMapping(
        rqa.RequiredArgument(
            'reason',
            rqa.EnumValue(models.NotificationReasons),
            'For what type notification do you want to change the settings.',
        ),
        rqa.RequiredArgument(
            'value',
            rqa.EnumValue(models.EmailNotificationTypes),
            'The new value of the notification setting.',
        ),
    ).from_flask()

    user = _get_user()

    models.NotificationsSetting.update_for_user(
        user=user, reason=data.reason, value=data.value
    )
    models.db.session.commit()

    return EmptyResponse.make()


@api.route('/settings/ui_preferences/<name>', methods=['GET'])
@rqa.swaggerize('get_ui_preference')
def get_user_preference(name: str) -> JSONResponse[t.Optional[bool]]:
    """Get a single UI preferences.

    .. :quickref: User Setting; Get a single UI preference.

    :query str token: The token with which you want to get the preferences,
        if not given the preferences are retrieved for the currently logged in
        user.
    :param string name: The preference name you want to get.
    :returns: The preferences for the user as described by the ``token``.
    """
    pref = rqa.EnumValue(models.UIPreferenceName).try_parse(name)
    user = _get_user()

    return JSONResponse.make(
        models.UIPreference.get_preference_for_user(user, pref)
    )


@api.route('/settings/ui_preferences/', methods=['GET'])
@rqa.swaggerize('get_all_ui_preferences')
def get_user_preferences(
) -> JSONResponse[t.Mapping[str, t.Optional[bool]]]:
    """Get ui preferences.

    .. :quickref: User Setting; Get UI preferences.

    :query str token: The token with which you want to get the preferences,
        if not given the preferences are retrieved for the currently logged in
        user.
    :returns: The preferences for the user as described by the ``token``.
    """
    user = _get_user()

    return JSONResponse.make(
        {
            pref.name: value
            for pref, value in
            models.UIPreference.get_preferences_for_user(user).items()
        }
    )


@api.route('/settings/ui_preferences/', methods=['PATCH'])
@rqa.swaggerize('patch_ui_preference')
def update_user_preferences() -> EmptyResponse:
    """Update ui preferences.

    .. :quickref: User Setting; Update UI preferences.

    :query str token: The token with which you want to update the preferences,
        if not given the preferences are updated for the currently logged in
        user.
    :returns: Nothing.
    """
    data = rqa.FixedMapping(
        rqa.RequiredArgument(
            'name',
            rqa.EnumValue(models.UIPreferenceName),
            'The ui preference you want to change.',
        ),
        rqa.RequiredArgument(
            'value',
            rqa.SimpleValue.bool,
            'The new value of the preference.',
        ),
    ).from_flask()

    user = _get_user()

    models.UIPreference.update_for_user(
        user=user, name=data.name, value=data.value
    )
    models.db.session.commit()

    return EmptyResponse.make()
