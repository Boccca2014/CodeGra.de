"""
This module defines all API routes with the main directory "login". This APIs
are used to handle starting and closing the user session and update the :class:
User object of the logged in user.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from flask import request
from flask_limiter.util import get_remote_address

import cg_request_args as rqa
from cg_json import (
    JSONResponse, ExtendedJSONResponse, MultipleExtendedJSONResponse
)
from psef.exceptions import (
    APICodes, PermissionException, WeakPasswordException
)

from . import api
from .. import auth, mail, models, helpers, limiter, current_user
from ..errors import APICodes, APIWarnings, APIException
from ..models import db
from ..helpers import (
    EmptyResponse, validate, add_warning, jsonify_options, ensure_json_dict,
    request_arg_true, ensure_keys_in_dict, make_empty_response
)
from ..permissions import GlobalPermission as GPerm


def _login_rate_limit() -> t.Tuple[str, str]:
    try:
        username = request.get_json()['username'].lower()
    except:  # pylint: disable=bare-except
        username = '?UNKNOWN?'

    return (username, get_remote_address())


@api.route("/login", methods=["POST"])
@limiter.limit(
    '5 per minute', key_func=_login_rate_limit, deduct_on_err_only=True
)
@rqa.swaggerize('login')
def login(
) -> MultipleExtendedJSONResponse[models.User.LoginResponse, models.User]:
    """Login using your username and password.

    .. :quickref: User; Login a given user.

    :returns: A response containing the JSON serialized user

    :query with_permissions: Setting this to true will add the key
        ``permissions`` to the user. The value will be a mapping indicating
        which global permissions this user has.

    :raises APIException: If no user with username exists or the password is
        wrong. (LOGIN_FAILURE)
    :raises APIException: If the user with the given username and password is
        inactive. (INACTIVE_USER)
    """
    data = rqa.Union(
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'username',
                rqa.SimpleValue.str,
                'Your username',
            ),
            rqa.RequiredArgument(
                'password',
                rqa.RichValue.Password,
                'Your password',
            )
        ).add_description('The data required when you want to login').add_tag(
            'tag', 'login'
        ),
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'username',
                rqa.SimpleValue.str,
                'The username of the user you want to impersonate',
            ),
            rqa.RequiredArgument(
                'own_password',
                rqa.RichValue.Password,
                'Your own password',
            ),
        ).add_description(
            'The data required when you want to impersonate a user'
        ).add_tag('tag', 'impersonate')
    ).from_flask(
        log_replacer=lambda k, v: '<PASSWORD>' if 'password' in k else v
    )
    user: t.Optional[models.User]

    if data.tag == 'impersonate':
        auth.ensure_permission(GPerm.can_impersonate_users)

        if current_user.password != data.own_password:
            raise APIException(
                'The supplied own password is incorrect',
                f'The user {current_user.id} has a different password',
                APICodes.INVALID_CREDENTIALS, 403
            )

        user = helpers.filter_single_or_404(
            models.User,
            models.User.username == data.username,
            ~models.User.is_test_student,
            models.User.active,
        )

    else:
        # WARNING: Do not use the `helpers.filter_single_or_404` function here
        # as we have to return the same error for a wrong email as for a wrong
        # password!
        user = db.session.query(
            models.User,
        ).filter(
            models.User.username == data.username,
            ~models.User.is_test_student,
        ).first()

        if user is None or user.password != data.password:
            exc_msg = 'The supplied username or password is wrong.'

            # If the given username looks like an email we notify the user that
            # their username is probably not the same as their email. Note that
            # this doesn't check if the user was found, so this does not leak
            # information about the existence of a user with the given
            # username.
            try:
                validate.ensure_valid_email(data.username)
            except validate.ValidationException:
                pass
            else:
                exc_msg += (
                    ' You have to login to CodeGrade using your username,'
                    ' which is probably not the same as your email.'
                )

            raise APIException(
                exc_msg, (
                    f'The user with username "{data.username}" does not exist '
                    'or has a different password'
                ), APICodes.LOGIN_FAILURE, 400
            )

        if not user.is_active:
            raise APIException(
                'User is not active',
                f'The user with id "{user.id}" is not active any more',
                APICodes.INACTIVE_USER, 403
            )

        # Check if the current password is safe, and add a warning to the
        # response if it is not.
        try:
            validate.ensure_valid_password(data.password, user=user)
        except WeakPasswordException:
            add_warning(
                (
                    'Your password does not meet the requirements, consider '
                    'changing it.'
                ),
                APIWarnings.WEAK_PASSWORD,
            )

    auth.set_current_user(user)

    if request_arg_true('with_permissions'):
        jsonify_options.get_options().add_permissions_to_user = user

    return MultipleExtendedJSONResponse.make(
        {
            'user': user,
            'access_token': user.make_access_token(),
        },
        use_extended=models.User,
    )


@api.route("/login", methods=["GET"])
@rqa.swaggerize('get')
@auth.login_required
def self_information() -> t.Union[JSONResponse[models.User],
                                  JSONResponse[t.Dict[int, str]],
                                  ExtendedJSONResponse[models.User],
                                  ]:
    """Get the info of the currently logged in user.

    .. :quickref: User; Get information about the currently logged in user.

    :query type: If this is ``roles`` a mapping between course_id and role name
        will be returned, if this is ``extended`` the result of
        :py:meth:`.models.User.__extended_to_json__()` will be returned. If
        this is something else or not present the result of
        :py:meth:`.models.User.__to_json__()` will be returned.
    :query with_permissions: Setting this to true will add the key
        ``permissions`` to the user. The value will be a mapping indicating
        which global permissions this user has.
    :returns: A response containing the JSON serialized user

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    args = request.args
    if args.get('type') == 'roles':
        return JSONResponse.make(
            {
                role.course_id: role.name
                for role in current_user.courses.values()
            }
        )
    elif helpers.extended_requested() or args.get('type') == 'extended':
        user = models.User.resolve(current_user)
        if request_arg_true('with_permissions'):
            jsonify_options.get_options().add_permissions_to_user = user
        return ExtendedJSONResponse.make(user, use_extended=models.User)

    return JSONResponse.make(current_user)


@api.route('/login', methods=['PATCH'])
def get_user_update() -> t.Union[EmptyResponse,
                                 JSONResponse[t.Mapping[str, str]],
                                 ExtendedJSONResponse[models.User],
                                 ]:
    """Change data of the current :class:`.models.User` and handle passsword
        resets.

    .. :quickref: User; Update the currently logged users information or reset
        a password.

    - If ``type`` is ``reset_password`` reset the password of the user with the
      given user_id with the given token to the given ``new_password``.
    - If ``type`` is ``reset_email`` send a email to the user with the given
      username that enables this user to reset its password.
    - if ``type`` is ``reset_on_lti`` the ``reset_email_on_lti`` attribute for
      the current is set to ``True``.
    - Otherwise change user info of the currently logged in user.

    :returns: An empty response with return code 204 unless ``type`` is
        ``reset_password``, in this case a mapping between ``access_token`` and
        a jwt token is returned.

    :<json int user_id: The id of the user, only when type is reset_password.
    :<json str username: The username of the user, only when type is
        reset_email.
    :<json str token: The reset password token. Only if type is
        reset_password.
    :<json str email: The new email of the user.
    :<json str name: The new full name of the user.
    :<json str old_password: The old password of the user.
    :<json str new_password: The new password of the user.

    :raises APIException: If not all required parameters ('email',
                          'o_password', 'name', 'n_password') were in the
                          request. (MISSING_REQUIRED_PARAM)
    :raises APIException: If the old password was not correct.
                          (INVALID_CREDENTIALS)
    :raises APIException: If the new password or name is not valid.
                          (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not edit his own info.
                                 (INCORRECT_PERMISSION)
    """
    if request.args.get('type', None) == 'reset_email':
        return user_patch_handle_send_reset_email()
    elif request.args.get('type', None) == 'reset_password':
        return user_patch_handle_reset_password()
    elif request.args.get('type', None) == 'reset_on_lti':
        return user_patch_handle_reset_on_lti()
    else:
        return user_patch_handle_change_user_data()


def user_patch_handle_send_reset_email() -> EmptyResponse:
    """Handle the ``reset_email`` type for the PATCH login route.

    :returns: An empty response.
    """
    data = ensure_json_dict(request.get_json())
    with helpers.get_from_map_transaction(data) as [get, _]:
        username = get('username', str)

    user = helpers.filter_single_or_404(
        models.User,
        ~models.User.is_test_student,
        models.User.username == username,
    )

    if not user.has_permission(GPerm.can_edit_own_password):
        raise PermissionException(
            (
                'This user does not have the necessary permissions to reset'
                ' its own password'
            ), f'The user {user.id} has insufficient permissions',
            APICodes.INCORRECT_PERMISSION, 403
        )

    mail.send_reset_password_email(user)
    db.session.commit()

    return make_empty_response()


def user_patch_handle_reset_password() -> JSONResponse[t.Mapping[str, str]]:
    """Handle the ``reset_password`` type for the PATCH login route.

    :returns: A response with a jsonified mapping between ``access_token`` and
        a token which can be used to login. This is only key available.
    """
    data = ensure_json_dict(
        request.get_json(),
        replace_log=lambda k, v: '<PASSWORD>' if 'password' in k else v
    )
    ensure_keys_in_dict(
        data, [('new_password', str), ('token', str), ('user_id', int)]
    )
    password = t.cast(str, data['new_password'])
    user_id = t.cast(int, data['user_id'])
    token = t.cast(str, data['token'])

    user = helpers.get_or_404(models.User, user_id)
    validate.ensure_valid_password(password, user=user)

    user.reset_password(token, password)
    db.session.commit()
    return JSONResponse.make({'access_token': user.make_access_token()})


def user_patch_handle_reset_on_lti() -> EmptyResponse:
    """Handle the ``reset_on_lti`` type for the PATCH login route.

    :returns: An empty response.
    """
    auth.ensure_logged_in()
    current_user.reset_email_on_lti = True
    db.session.commit()

    return make_empty_response()


def user_patch_handle_change_user_data() -> ExtendedJSONResponse[models.User]:
    """Handle the PATCH login route when no ``type`` is given.

    :returns: An empty response.
    """
    data = ensure_json_dict(
        request.get_json(),
        replace_log=lambda k, v: f'<PASSWORD "{k}">' if 'password' in k else v
    )

    ensure_keys_in_dict(
        data, [
            ('email', str), ('old_password', str), ('name', str),
            ('new_password', str)
        ]
    )
    email = t.cast(str, data['email'])
    old_password = t.cast(str, data['old_password'])
    new_password = t.cast(str, data['new_password'])
    name = t.cast(str, data['name'])

    def _ensure_password(
        changed: str,
        msg: str = 'To change your {} you need a correct old password.'
    ) -> None:
        if current_user.password != old_password:
            raise APIException(
                msg.format(changed), 'The given old password was not correct',
                APICodes.INVALID_CREDENTIALS, 403
            )

    if old_password != '':
        _ensure_password('', 'The given old password is wrong')

    if current_user.email != email:
        auth.ensure_permission(GPerm.can_edit_own_info)
        _ensure_password('email')
        validate.ensure_valid_email(email)
        current_user.email = email

    if new_password != '':
        auth.ensure_permission(GPerm.can_edit_own_password)
        _ensure_password('password')
        validate.ensure_valid_password(new_password, user=current_user)
        current_user.password = new_password

    if current_user.name != name:
        auth.ensure_permission(GPerm.can_edit_own_info)
        if name == '':
            raise APIException(
                'Your new name cannot be empty',
                'The given new name was empty', APICodes.INVALID_PARAM, 400
            )
        current_user.name = name

    db.session.commit()
    return ExtendedJSONResponse.make(current_user, use_extended=models.User)
