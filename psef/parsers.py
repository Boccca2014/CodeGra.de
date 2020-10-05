"""
This module implements parsers that raise a `APIException` when they fail.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import typing as t
import email.utils
from datetime import timezone

import dateutil.parser
from validate_email import validate_email

from cg_dt_utils import DatetimeWithTimezone
from psef.errors import APICodes, APIException

T = t.TypeVar('T', bound=enum.Enum)


def init_app(_: t.Any) -> None:
    pass


@t.overload
def parse_datetime(to_parse: object) -> DatetimeWithTimezone:  # pylint: disable=missing-docstring,unused-argument
    ...


@t.overload
def parse_datetime(  # pylint: disable=missing-docstring,unused-argument,function-redefined
    to_parse: object,
    allow_none: bool,
) -> t.Optional[DatetimeWithTimezone]:
    ...


def parse_datetime(  # pylint: disable=function-redefined
    to_parse: object,
    allow_none: bool = False,
) -> t.Optional[DatetimeWithTimezone]:
    """Parse a datetime string using dateutil.

    :param to_parse: The object to parse, if this is not a string the parsing
        will always fail.
    :param allow_none: Allow ``None`` to be passed without raising a
        exception. if ``to_parse`` is ``None`` and this option is ``True`` the
        result will be ``None``.
    :returns: The parsed DatetimeWithTimezone object.
    :raises APIException: If the parsing fails for whatever reason.
    """
    if to_parse is None and allow_none:
        return None

    if isinstance(to_parse, str):
        try:
            parsed = dateutil.parser.parse(to_parse)
        except (ValueError, OverflowError):
            pass
        else:
            # This assumes that datetimes without tzinfo are in UTC. That is
            # not correct according to the ISO spec, however it is what we used
            # to do so we need to do this because of backwards compatibility.
            return DatetimeWithTimezone.from_datetime(
                parsed, default_tz=timezone.utc
            )

    raise APIException(
        'The given date is not valid!',
        '{} cannot be parsed by dateutil.'.format(to_parse),
        APICodes.INVALID_PARAM, 400
    )
