"""This module implements the ``Maybe`` monad.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from typing_extensions import Final, Literal

_T = t.TypeVar('_T', covariant=True)
_TT = t.TypeVar('_TT', covariant=True)
_Y = t.TypeVar('_Y')


class Just(t.Generic[_T]):
    """The just part of the Maybe monad.
    """
    __slots__ = ('value', )

    is_just: Literal[True] = True
    is_nothing: Literal[False] = False

    def __init__(self, value: _T) -> None:
        self.value: Final = value

    def map(self, mapper: t.Callable[[_T], _TT]) -> 'Just[_TT]':
        """Transform this just by applying ``mapper`` to its argument and
        wrapping the result in a new ``Just``.

        >>> Just(5).map(lambda el: el * el)
        Just(25)
        >>> Nothing.map(lambda el: el * el)
        Nothing
        """
        return Just(mapper(self.value))

    def chain(self, chainer: t.Callable[[_T], 'Maybe[_TT]']) -> 'Maybe[_TT]':
        """Transforms ``this`` with a function that returns a ``Maybe``.

        >>> Just(5).chain(lambda el: Just(el * el))
        Just(25)
        >>> Just(5).chain(lambda _: Nothing)
        Nothing
        >>> Nothing.chain(lambda el: Just(el * el))
        Nothing
        >>> Nothing.chain(lambda _: Nothing)
        Nothing
        """
        return chainer(self.value)

    def __repr__(self) -> str:
        return f'Just({self.value})'

    def alt(self, _alternative: 'Maybe[_T]') -> 'Maybe[_T]':
        """Return the given ``alternative`` if called on a ``Nothing``,
        otherwise the method returns the value it is called on.

        >>> Just(5).alt(Just(10))
        Just(5)
        >>> Nothing.alt(Just(10))
        Just(10)
        """
        return self

    def unsafe_extract(self) -> _T:
        """Get the value from a ``Just``, or raise if called on a ``Nothing``.

        >>> Just(10).unsafe_extract()
        10
        """
        return self.value

    def or_default_lazy(self, _producer: t.Callable[[], _Y]) -> _T:
        """Get the value from a ``Just``, or return the given a default as
        produced by the given function.

        >>> Just(5).or_default_lazy(lambda: [print('call'), 10][-1])
        5
        >>> Nothing.or_default_lazy(lambda: [print('call'), 10][-1])
        call
        10
        """
        return self.value

    def or_default(self, _value: _Y) -> _T:
        """Get the value from a ``Just``, or return the given ``default``.

        >>> Just(5).or_default(10)
        5
        >>> Nothing.or_default(10)
        10
        """
        return self.value

    def if_just(self, callback: t.Callable[[_T], None]) -> None:
        """Call the given callback with the wrapped value if this value is a
        ``Just``, otherwise do nothing.

        >>> printer = lambda el: print('call', el)
        >>> Nothing.if_just(printer)
        >>> Just(5).if_just(printer)
        call 5
        """
        callback(self.value)

    def try_extract(self, _make_exception: t.Callable[[], Exception]) -> _T:
        """Try to extract the value, raising an exception created by the given
        argument if the value is ``Nothing``.

        >>> Just(5).try_extract(Exception)
        5
        >>> Nothing.try_extract(Exception)
        Traceback (most recent call last):
        ...
        Exception
        """
        return self.value


class _Nothing(t.Generic[_T]):
    """Singleton class to represent the ``Nothing`` part of a ``Maybe``.
    """
    __slots__ = ()

    is_just: Literal[False] = False
    is_nothing: Literal[True] = True

    # pylint: disable=no-self-use,missing-function-docstring
    def map(self, _mapper: t.Callable[[_T], _TT]) -> '_Nothing[_TT]':
        return Nothing

    def chain(self, _chainer: t.Callable[[_T], 'Maybe[_TT]']) -> '_Nothing[_TT]':
        return Nothing

    def alt(self, alternative: 'Maybe[_T]') -> 'Maybe[_T]':
        return alternative

    def or_default(self, value: _Y) -> _Y:
        return value

    def or_default_lazy(self, _producer: t.Callable[[], _Y]) -> _Y:
        return _producer()

    def unsafe_extract(self) -> _T:
        raise AssertionError('Tried to extract a _Nothing')

    def if_just(self, callback: t.Callable[[_T], None]) -> None:
        pass

    def try_extract(
        self, make_exception: t.Callable[[], Exception]
    ) -> t.NoReturn:
        raise make_exception()

    def __repr__(self) -> str:
        return 'Nothing'

    @classmethod
    def is_nothing_instance(cls, obj: object) -> bool:
        """Check if the given object is a Nothing object.

        >>> Nothing.is_nothing_instance(5)
        False
        >>> Nothing.is_nothing_instance(Nothing)
        True
        >>> Nothing.is_nothing_instance(Just(5))
        False
        """
        return isinstance(obj, cls)

    # pylint: enable=no-self-use,missing-function-docstring


Nothing: _Nothing[t.Any] = _Nothing()

Maybe = t.Union[Just[_T], _Nothing[_T]]

def from_nullable(val: t.Optional[_T]) -> Maybe[_T]:
    """Covert a nullable to a maybe.

    >>> from_nullable(5)
    Just(5)
    >>> from_nullable(None)
    Nothing
    """
    if val is None:
        return Nothing
    return Just(val)
