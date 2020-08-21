"""This module implements the ``CGEnum`` class.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import typing as t

_PREFIX = 'is_'
_PREFIX_LEN = len(_PREFIX)


class CGEnum(enum.Enum):
    """A emum subclass that already implements the ``__to_json`` method and
    with useful checker methods.


    >>> class E(CGEnum):
    ...  b = 1
    ...  c = 2
    >>> e = E.c
    >>> e.is_c
    True
    >>> e.is_b
    False
    """

    def __getattr__(self, name: str) -> t.Any:
        if name.startswith(_PREFIX):
            try:
                found = self.__class__[name[_PREFIX_LEN:]]
                return self is found
            except KeyError:
                pass

        return super().__getattribute__(name)

    def __to_json__(self) -> str:
        return self.name
