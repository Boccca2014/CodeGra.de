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
        mcs: t.Type[_T], name: str, bases: t.Tuple[t.Type, ...],
        classdict: t.Dict[str, t.Any]
    ) -> _T:
        res = t.cast(_T, super().__new__(mcs, name, bases, classdict))
        value: 'CGEnum'
        for value in res:
            name = value.name  # type: ignore[attr-defined]
            setattr(res, f'{_PREFIX}{name}', mcs._make_is_equal_method(value))
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


if t.TYPE_CHECKING:
    class CGDbEnum(t.Generic[ENUM]):
        def __init__(self, enum: t.Type[ENUM], *, name: str = None) -> None:
            ...
else:
    class CGDbEnum(Enum):
        def __init__(self, *enums: CGEnum, **kw: t.Any) -> None:
            enum = enums[0] if enums else kw['_enums'][0]
            super().__init__(*enums, **kw)

            class comparator_factory(Enum.Comparator):
                def __getattr__(self, name: str) -> t.Any:
                    if name.startswith(_PREFIX):
                        return self.expr == enum[name[_PREFIX_LEN:]]
                    return super().__getattr__(name)

            self.comparator_factory = comparator_factory

        # This overload is needed for the mypy plugin, as otherwise ``mypy`` has no
        # idea that we might have extra properties.
        def __getattr__(self, name: str) -> object:
            return super().__getattribute__(name)
