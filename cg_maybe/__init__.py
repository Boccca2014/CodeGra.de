import typing as t

from typing_extensions import Final, Literal

_T = t.TypeVar('_T')
_Y = t.TypeVar('_Y')


class Just(t.Generic[_T]):
    __slots__ = ('value')

    is_just: Literal[True] = True
    is_nothing: Literal[False] = False

    def __init__(self, value: _T) -> None:
        self.value: Final = value

    def map(self, mapper: t.Callable[[_T], _Y]) -> 'Just[_Y]':
        return Just(mapper(self.value))

    def or_default(self, _value: _T) -> _T:
        return self.value


class _Nothing(t.Generic[_T]):
    __slots__ = ()

    is_just: Literal[False] = False
    is_nothing: Literal[True] = True

    def map(self, _mapper: t.Callable[[_T], _Y]) -> '_Nothing[_Y]':
        return Nothing

    def or_default(self, value: _T) -> _T:
        return value


Nothing: _Nothing[t.Any] = _Nothing()

Maybe = t.Union[Just[_T], _Nothing[_T]]
