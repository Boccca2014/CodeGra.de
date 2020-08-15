"""
This module contains code to humanize various numbers.

SPDX-License-Identifier: AGPL-3.0-only
"""
import sys
import math
import typing as t
import datetime as dt

from typing_extensions import Literal

if t.TYPE_CHECKING:  # pragma: ignore
    import psef.archive  # pylint: disable=unused-import


def size(_size: 'psef.archive.FileSize') -> str:
    """Get a human readable size.

    >>> size(512)
    '512B'
    >>> size(1024)
    '1KB'

    :param size: The size in bytes.
    :returns: A string that is the amount of bytes which is human readable.
    """
    size_f: float = _size

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_f < 1024.0:
            break
        size_f /= 1024.0

    if int(size_f) == size_f:
        return f"{int(size_f)}{unit}"
    return f"{size_f:.2f}{unit}"


_POSSIBLE_TIMES = Literal['s', 'm', 'h', 'd', 'M', 'y']


def _timedelta_to(delta: dt.timedelta, to: _POSSIBLE_TIMES) -> int:
    opts = [('s', 1), ('m', 60), ('h', 60), ('d', 24), ('m', 30.5), ('y', 12)]
    cur = abs(delta.total_seconds())
    for opt, amount in opts:
        cur /= amount
        if opt == to:
            return round(cur)

    assert False


_TIMEDELTA_MAPPING: t.List[t.Union[t.Tuple[t.Tuple[_POSSIBLE_TIMES, float],
                                           t.Callable[[dt.timedelta], str],
                                           t.Callable[[dt.timedelta], str],
                                           t.Callable[[dt.timedelta], str],
                                           ],
                                   t.Tuple[t.Tuple[_POSSIBLE_TIMES, float],
                                           t.Callable[[dt.timedelta], str],
                                           ],
                                   ]]

_TIMEDELTA_MAPPING = [
    (
        ('s', 45),
        lambda _: 'a few seconds',
        lambda _: 'just now',
        lambda t: f'{_timedelta_to(t, "s")} seconds ago',
    ),
    (('s', 46), lambda t: f'{_timedelta_to(t, "s")} seconds'),
    (('m', 2), lambda _: 'a minute'),
    (('m', 50), lambda t: f'{_timedelta_to(t, "m")} minutes'),
    (('h', 2), lambda _: 'an hour'),
    (('h', 48), lambda t: f'{_timedelta_to(t, "h")} hours'),
    (('d', 26), lambda t: f'{_timedelta_to(t, "d")} days'),
    (('m', 2), lambda _: 'a month'),
    (('m', 12), lambda t: f'{_timedelta_to(t, "M")} months'),
    (('y', 2), lambda _: 'a year'),
    (('y', math.inf), lambda t: f'{_timedelta_to(t, "y")} years'),
]


def timedelta(delta: dt.timedelta, *, no_prefix: bool = False) -> str:
    """Humanize a timedelta.

    :param delta: The delta to huminze, it may be negative too (which will be
        formatted differently).

    :returns: A human readable format of the delta.
    """
    for (unit, time), *formatters in _TIMEDELTA_MAPPING:
        if time == math.inf or _timedelta_to(delta, unit) < time:
            past = delta.total_seconds() < 0
            if len(formatters) == 1 or no_prefix:
                base = formatters[0](delta)
                if no_prefix:
                    return base
                elif past:
                    return f'{base} ago'
                else:
                    return f'in {base}'
            else:
                assert len(formatters) == 3
                return formatters[2 if past else 1](delta)

    assert False
