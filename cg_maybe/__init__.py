"""This module implements the ``Maybe`` monad.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from typing_extensions import Final, Literal

_T = t.TypeVar('_T', covariant=True)
_TT = t.TypeVar('_TT', covariant=True)
_Y = t.TypeVar('_Y')


class Just(t.Generic[_T]):
    __slots__ = ('value')

    is_just: Literal[True] = True
    is_nothing: Literal[False] = False

    def __init__(self, value: _T) -> None:
        self.value: Final = value

    def map(self, mapper: t.Callable[[_T], _TT]) -> 'Just[_TT]':
        return Just(mapper(self.value))

    def alt(self, alternative: 'Maybe[_T]') -> 'Maybe[_T]':
        return self

    def unsafe_extract(self) -> _T:
        return self.value

    def or_default(self, _value: _Y) -> _T:
        return self.value

    def if_just(self, cb: t.Callable[[_T], None]) -> None:
        cb(self.value)


class _Nothing(t.Generic[_T]):
    __slots__ = ()

    is_just: Literal[False] = False
    is_nothing: Literal[True] = True

    def map(self, _mapper: t.Callable[[_T], _TT]) -> '_Nothing[_TT]':
        return Nothing

    def alt(self, alternative: 'Maybe[_T]') -> 'Maybe[_T]':
        return alternative

    def or_default(self, value: _Y) -> _Y:
        return value

    def unsafe_extract(self) -> _T:
        raise AssertionError('Tried to extract a _Nothing')

    def if_just(self, cb: t.Callable[[_T], None]) -> None:
        pass


Nothing: _Nothing[t.Any] = _Nothing()

Maybe = t.Union[Just[_T], _Nothing[_T]]
