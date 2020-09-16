from __future__ import annotations

import typing as t

from typing_extensions import Final, Literal

_T = t.TypeVar('_T')
_Y = t.TypeVar('_Y')


# This class is just used for type annotations, but the just classes are not
# subclasses of this type. In the plugin we expand ``Maybe[T]`` to
# ``t.Union[Just[T], _Nothing]`` so we can take advantage of the literal values
# for ``is_just`` and ``is_nothing``.
class Maybe(t.Generic[_T]):
    pass


class Just(t.Generic[_T]):
    __slots__ = ('value')

    is_just: Literal[True] = True
    is_nothing: Literal[False] = False

    def __init__(self, value: _T) -> None:
        self.value: Final = value

    def map(self, mapper: t.Callable[[_T], _Y]) -> Just[_Y]:
        return Just(mapper(self.value))


class _Nothing(t.Generic[_T]):
    __slots__ = ()

    is_just: Literal[False] = False
    is_nothing: Literal[True] = True

    def map(self, mapper: t.Callable[[_T], _Y]) -> _Nothing[_Y]:
        return Nothing


Nothing: _Nothing[t.Any] = _Nothing()
