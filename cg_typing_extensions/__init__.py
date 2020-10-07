"""This module contains various helpers for mypy.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

T_DICT = t.TypeVar('T_DICT', bound=dict)  # pylint: disable=invalid-name


def make_typed_dict_extender(base: t.Any, extends_to: t.Type) -> t.Callable:  # pylint: disable=unused-argument
    """Get a function to extend the TypedDict ``base`` to the TypedDict
    ``extends_to``.
    """

    def _extend(**kwargs: t.Any) -> dict:
        base.update(kwargs)
        return base

    return _extend
