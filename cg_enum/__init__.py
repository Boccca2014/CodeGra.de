"""This module implements the ``CGEnum`` class.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import typing as t

from sqlalchemy import Enum

_PREFIX = 'is_'
_PREFIX_LEN = len(_PREFIX)

_T = t.TypeVar('_T', bound='_CGEnumMeta')
ENUM = t.TypeVar('ENUM', bound='CGEnum')


# This meta class is responsible for adding the needed properties (all the
# ``is_X`` properties) to the enum. This is way faster than doing the
# ``__getattr__`` magic, as we don't need to do string manipulation now every
# time we access a property.
class _CGEnumMeta(enum.EnumMeta):
    @staticmethod
    def _make_is_equal_method(equal_to: 'CGEnum') -> property:
        def is_equal(self: 'CGEnum') -> bool:
            return self is equal_to

        return property(is_equal)

    def __new__(
        cls: t.Type[_T], name: str, bases: t.Tuple[t.Type, ...],
        classdict: t.Dict[str, t.Any]
    ) -> _T:
        res = t.cast(_T, super().__new__(cls, name, bases, classdict))
        value: 'CGEnum'
        for value in res:
            name = value.name  # type: ignore[attr-defined]
            setattr(res, f'{_PREFIX}{name}', cls._make_is_equal_method(value))
        return res


class CGEnum(enum.Enum, metaclass=_CGEnumMeta):
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

    # This overload is needed for the mypy plugin, as otherwise ``mypy`` has no
    # idea that we might have extra properties.
    def __getattr__(self, name: str) -> object:
        return super().__getattribute__(name)

    def __to_json__(self) -> str:
        return self.name


def named_equally(enumeration: t.Type[ENUM]) -> t.Type[ENUM]:
    """Make sure all the values in the given enum are unique and equal to their
    key.
    """
    enum.unique(enumeration)

    for name, member in enumeration.__members__.items():
        if name != member.value:
            raise ValueError(
                'Member {} has a wrong value: {}'.format(name, member.value)
            )

    return enumeration


if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=missing-class-docstring,unused-argument
    class CGDbEnum(t.Generic[ENUM]):
        def __init__(self, enums: t.Type[ENUM], *, name: str = None) -> None:
            ...
else:

    class CGDbEnum(Enum):  # pylint: disable=too-many-ancestors
        """Get a database type that has the same convenience methods as the
        :class:`.CGEnum` class.
        """

        def __init__(self, *enums: CGEnum, **kw: t.Any) -> None:
            enumeration = enums[0] if enums else kw['_enums'][0]
            super().__init__(*enums, **kw)

            class comparator_factory(Enum.Comparator):  # pylint: disable=invalid-name,missing-class-docstring
                def __getattr__(self, name: str) -> t.Any:
                    if name.startswith(_PREFIX):
                        return self.expr == enumeration[name[_PREFIX_LEN:]]
                    return super().__getattr__(name)

            self.comparator_factory = comparator_factory

        # This overload is needed for the mypy plugin, as otherwise ``mypy``
        # has no idea that we might have extra properties.
        def __getattr__(self, name: str) -> object:
            return super().__getattribute__(name)
