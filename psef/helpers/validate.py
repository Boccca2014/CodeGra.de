"""This module contains all code needed to validate user input for fields.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from zxcvbn import zxcvbn
from validate_email import validate_email as _validate_email

from ..exceptions import APICodes, ValidationException, WeakPasswordException


@t.overload
def ensure_valid_password(  # pylint: disable=missing-docstring,unused-argument
    new_password: str,
    *,
    user: 'psef.models.User',
) -> None:
    ...  # pylint: disable=pointless-statement


@t.overload
def ensure_valid_password(  # pylint: disable=function-redefined,missing-docstring,unused-argument
    new_password: str,
    *,
    name: str,
    email: str,
    username: str,
) -> None:
    ...  # pylint: disable=pointless-statement


def ensure_valid_password(  # pylint: disable=function-redefined
    new_password: str,
    *,
    user: t.Optional['psef.models.User'] = None,
    name: t.Optional[str] = None,
    email: t.Optional[str] = None,
    username: t.Optional[str] = None,
) -> None:
    """Ensure that the given password is valid and strong enough.

    The user, username, name and email are used to determine the strength, as
    the password should not be derived from that information.

    :param new_password: The new password.
    :param user: The user whose password is to be updated.
    :param name: The name of the user.
    :param email: The email of the user.
    :param username: The username of the user.
    :returns: Nothing.
    :raises WeakPasswordException: When the password is empty or not
        strong enough.
    """

    extra_inputs: t.List[str] = [name or '', username or '', email or '']
    if user:
        extra_inputs += [user.username, user.name, user.email]
    extra_inputs = [
        item for l in extra_inputs for item in l.split() + [l] if item
    ]

    # Type should be caught by mypy but just in case.
    if new_password and isinstance(new_password, str):
        result = zxcvbn(
            new_password,
            user_inputs=extra_inputs,
        )
    else:
        result = {
            'score': -1,
            'feedback':
                {
                    'warning': 'An empty password is not allowed',
                    'suggestions': ['Add more characters to your password', ],
                }
        }

    min_score = psef.site_settings.Opt.MIN_PASSWORD_SCORE.value
    if result['score'] < min_score:
        msg = 'Your chosen password is not secure enough.'
        if not result['feedback']['warning']:
            result['feedback']['warning'] = msg
        raise WeakPasswordException(
            msg, (
                f'The given password achieved a score of {result["score"]} '
                f'but a minimum of {min_score} was required.'
            ),
            APICodes.WEAK_PASSWORD,
            feedback=result['feedback']
        )


def ensure_valid_email(email: str) -> None:
    """Ensure that a given email is valid.

    :param email: The email to check.
    :returns: Nothing.
    :raises ValidationException: When the email is not valid.
    """
    if not _validate_email(email):
        raise ValidationException(
            'The given email is not valid.',
            'The email "{email}" is not valid.',
        )


if t.TYPE_CHECKING:  # pragma: no cover
    import psef  # pylint: disable=unused-import
