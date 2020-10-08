"""This module contains all code needed to register classes and functions under
one or more keys.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t
from collections import OrderedDict

if t.TYPE_CHECKING:  # pragma: no cover
    from cg_sqlalchemy_helpers.types import \
        Base  # pylint: disable=unused-import

T = t.TypeVar('T')  # pylint: disable=invalid-name
V = t.TypeVar('V')  # pylint: disable=invalid-name
TT = t.TypeVar('TT')  # pylint: disable=invalid-name
V_TABLE = t.TypeVar('V_TABLE', bound=t.Type['Base'])  # pylint: disable=invalid-name


class Register(t.Generic[T, V]):  # pylint: disable=unsubscriptable-object
    """Register things under keys using decorators.

    This class can be viewed as a ordered dict, however instead of setting
    things using subscripts it uses decorators.

    >>> reg = Register()
    >>> @reg.register('hello')
    ... def test_func(): pass
    >>> @reg.register_all(['world', 'bye'])
    ... def test_func2(): pass
    >>> reg.get('world') == test_func2
    True
    >>> reg.get('world2') is None
    True
    >>> list(reg.get_all()) == [
    ...     ('hello', test_func),
    ...     ('world', test_func2),
    ...     ('bye', test_func2),
    ... ]
    True
    """

    def __init__(self, name: str = None) -> None:
        self.__name = name
        self.__map: t.Dict[T, V] = OrderedDict()
        self.__frozen = False

    def freeze(self) -> None:
        self.__frozen = True

    def __str__(self) -> str:
        name = 'Anonymous' if self.__name is None else self.__name
        return f'{name}Register'

    def assert_not_frozen(self) -> None:
        assert not self.__frozen, 'This register is frozen'

    def register(self, key: T) -> t.Callable[[V], V]:
        """A decorator that can be used to register a single key.

        This decorator can be used to register an object with the given key.

        :param key: The key to register.
        :returns: A decorator, it registers the thing applied to this decorator
            under the given key.
        """
        return self.register_all([key])

    def register_all(self, keys: t.Iterable[T]) -> t.Callable[[V], V]:
        """A decorator that can be used to register multiple keys.

        This function is the same as :py:meth:`.Register.register`, the only
        difference is that multiple keys can be given instead of one.

        :param keys: The keys to register.
        :returns: A decorator that registers the given keys.
        """
        self.assert_not_frozen()

        def __decorator(cls: V) -> V:
            for key in keys:
                assert key not in self.__map
                self.__map[key] = cls
            return cls

        return __decorator

    @property
    def __members__(self) -> t.Mapping[T, V]:
        return self.__map

    @property
    def __name__(self) -> str:
        return str(self)

    def __contains__(self, key: T) -> bool:
        return key in self.__map

    def get_or(self, key: T, default: TT) -> t.Union[V, TT]:
        return self.__map.get(key, default)

    def get(self, key: T) -> t.Optional[V]:
        return self.__map.get(key)

    def __getitem__(self, key: T) -> V:
        return self.__map[key]

    def get_all(self) -> t.Iterable[t.Tuple[T, V]]:
        return self.__map.items()

    def keys(self) -> t.Iterable[T]:
        return self.__map.keys()

    def find(self, needle: V, default: TT) -> t.Union[T, TT]:
        """Find the key for a given value.

        >>> reg = Register()
        >>> @reg.register('hello')
        ... def test_func(): pass
        >>> @reg.register_all(['world', 'bye'])
        ... def test_func2(): pass
        >>> reg.find(test_func, None)
        'hello'
        >>> missing = object()
        >>> reg.find(object(), missing) is missing
        True

        :param needle: The value to search for.
        :param default: The default value to return if no value can be found.
        :returns: The key for this value, or the given default of none can be
            found.
        """
        for key, val in self.__map.items():
            if val == needle:
                return key
        return default


class TableRegister(t.Generic[V_TABLE], Register[str, V_TABLE]):
    """A registry especially designed for SQLAlchemy tables.

    This registry solves a small, but annoying, problem when using a
    :class:`.Register` with SQLAlchemy tables and the ``polymorphic_identity``
    feature. The first one is that you need to define all options in an enum in
    you base class, however you can only define (and register) your tables
    after the base class is defined. So you cannot use the ``.keys()`` method
    to define this enum.

    Then when defining it is annoying as you want the key under which you
    register your table to be the same as the value set for
    ``polymorphic_identity``, however this identity value is used by SQLAlchemy
    during creation of the class (yes, class not instance!) so setting it in
    decorator is not possible.

    This class solves those problems by making the workflow a bit different.
    First of all you define all possible options using the
    :meth:`.TableRegister.set_all_possible_options`. Later on you an register a
    table using the :meth:`.TableRegister.register_table` method which will
    read the key from the ``polymorphic_identity``.

    Finally you freeze the register, and it checks if all options declared
    using ``set_possible_options`` are also really registered.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.__possible_options: t.Optional[t.Sequence[str]] = None

    def set_possible_options(self, options: t.Sequence[str]) -> None:
        """Set all possible options.
        """
        self.assert_not_frozen()
        assert self.__possible_options is None, 'Options already set'
        self.__possible_options = options

    def freeze(self) -> None:
        assert self.__possible_options is not None
        assert set(self.keys()) == set(self.__possible_options)
        super().freeze()

    def register_table(self, cls: V_TABLE) -> V_TABLE:
        """Register an SQLAlchemy table in this register.

        The name under which the table is registered is read from
        ``cls.__mapper_args__['polymorphic_identity]``.

        :param cls: The table to register.

        :returns: The table unmodified.
        """
        assert self.__possible_options is not None, (
            'Possible options not yet set'
        )
        name = getattr(
            cls,
            '__mapper_args__',
            {},
        ).get('polymorphic_identity', None)

        assert (
            name is not None and name in self.__possible_options
        ), f'Unknown key: {name}'
        assert self.get(name) is None, 'Cannot register twice'
        self.register(name)(cls)

        return cls
