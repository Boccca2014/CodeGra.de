"""This module implements generic helpers and convenience functions.

These helper functions should ideally all be pure(ish) functions that do not
depend a database choice or flask.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import typing as t
import itertools

T = t.TypeVar('T')
Y = t.TypeVar('Y')

__all__ = [
    'handle_none',
    'assert_never',
    'zip_times_with_offset',
    'remove_duplicates',
    'on_not_none',
    'flatten',
    'maybe_wrap_in_list',
]


def handle_none(value: t.Optional[T], default: Y) -> t.Union[T, Y]:
    """Get the given ``value`` or ``default`` if ``value`` is ``None``.

    >>> handle_none(None, 5)
    5
    >>> handle_none(5, 6)
    5
    >>> handle_none(5.5, 6)
    5.5
    """
    return default if value is None else value


def assert_never(never: t.NoReturn, of_enum: t.Type[enum.Enum]) -> t.NoReturn:
    """Assert that the value ``x`` never exists according to mypy.

    This allows you to enforce that you do an exhaustive check for an enum:

    >>> import enum
    >>> class MyEnum(enum.Enum):
    ...  a = 1
    ...  b = 2
    >>> var: MyEnum = MyEnum.a
    >>> if var is MyEnum.a:
    ...  pass
    ... elif var is MyEnum.b:
    ...  pass
    ... else:
    ...  assert_never(var, MyEnum)

    :param never: The value that should never exist

    :raises AssertionError: This function always raises an assertion error.
    """
    raise AssertionError(
        'Unhandled value "{}" for Enum "{}"'.format(never, of_enum.__name__)
    )


def zip_times_with_offset(
    lst: t.List[T],
    amount: int,
    get_offset_per_item: t.Callable[[int], int],
) -> t.Iterator[t.Tuple[T, ...]]:
    """Zip a list with itself with an offset of one for each item in the zip.

    This function almost equivalent to ``zip(*([lst] * amount))`` except that
    each item in the zip will be offset.

    >>> for items in zip_times_with_offset(list(range(6)), 3, lambda x: x * 2):
    ...  print(items)
    (0, 2, 4)
    (1, 3, 5)
    (2, 4, 0)
    (3, 5, 1)
    (4, 0, 2)
    (5, 1, 3)

    :param lst: The list to zip with itself.
    :param amount: The amount of times to zip the list with itself.
    :param get_offset_per_item: A method that should produce the amount of
        items this level should be offset with. It is called with one argument,
        the current recursion depth, which will be in the range ``[0,
        amount)``.

    :returns: A iterator that produces a tuple of length ``amount``. Item ``i``
              that is generated will be equal to ``(lst[i], lst[(i +
              offset_per_item) % len(lst)], ..., lst[(i + n * offset_per_item)
              % len(lst)])``.
    """
    if amount <= 0:
        raise TypeError(f'amount should be >0, not {amount}')

    def _zip_times_with_offset(
        lst: t.List[T],
        cur_amount: int,
    ) -> t.Iterator[t.Tuple[T, ...]]:
        if cur_amount == amount:
            for _ in lst:
                yield tuple()

        else:
            for item, zipped in zip(
                itertools.islice(
                    itertools.cycle(lst), get_offset_per_item(cur_amount), None
                ),
                _zip_times_with_offset(lst, cur_amount + 1),
            ):
                yield (item, *zipped)

    yield from _zip_times_with_offset(lst, 0)


def remove_duplicates(
    iterable: t.Iterable[T], make_key: t.Callable[[T], object]
) -> t.Iterator[T]:
    """Get an iterator of the given iterable with all duplicates removed.

    >>> for item in remove_duplicates(list(range(6)), lambda x: x % 2):
    ...  print(item)
    0
    1

    :param it: The iterable from which you want to remove duplicates.
    :param make_key: The key that is used to determine if the items are
        duplicate. The return value of the function should be hashable.

    :returns: A new iterator in which all duplicates are removed.
    """
    seen = set()
    for item in iterable:
        key = make_key(item)
        if key in seen:
            continue
        seen.add(key)
        yield item


def on_not_none(value: t.Optional[T],
                callback: t.Callable[[T], Y]) -> t.Optional[Y]:
    """Call a given ``callback`` if the given ``value`` is not none.

    :param value: The value to operate on if not ``None``.
    :param callback: The callback to call with ``value`` if the ``value`` is
        not ``None``.

    :returns: The return of the ``callback`` or ``None``.
    """
    if value is not None:
        return callback(value)
    return None


def flatten(it_to_flatten: t.Iterable[t.Iterable[T]]) -> t.List[T]:
    """Flatten a given iterable of iterables to a list.

    >>> flatten((range(2) for _ in range(4)))
    [0, 1, 0, 1, 0, 1, 0, 1]
    >>> flatten((range(i) for i in range(5)))
    [0, 0, 1, 0, 1, 2, 0, 1, 2, 3]
    >>> flatten((range(2) for _ in range(0)))
    []
    >>> flatten([[[1, 2]], [[1, 2]]])
    [[1, 2], [1, 2]]

    :param it_to_flatten: The iterable to flatten, which will be iterated
        completely.
    :returns: A fresh flattened list.
    """
    return [x for wrap in it_to_flatten for x in wrap]


def maybe_wrap_in_list(maybe_lst: t.Union[t.List[T], T]) -> t.List[T]:
    """Wrap an item into a list if it is not already a list.

    >>> maybe_wrap_in_list(5)
    [5]
    >>> maybe_wrap_in_list([5])
    [5]
    >>> maybe_wrap_in_list([5, 6])
    [5, 6]
    >>> maybe_wrap_in_list({5 : 6})
    [{5: 6}]
    >>> maybe_wrap_in_list((1, 2))
    [(1, 2)]

    :param maybe_lst: The item to maybe wrap.
    :returns: The item wrapped or just the item.
    """
    if isinstance(maybe_lst, list):
        return maybe_lst
    return [maybe_lst]
