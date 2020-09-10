from __future__ import annotations

import abc
import enum
import typing as t

from typing_extensions import Final, Literal, Protocol, TypedDict

from cg_dt_utils import DatetimeWithTimezone


class _BaseDict(TypedDict):
    pass


_BASE_DICT = t.TypeVar('_BASE_DICT', bound=_BaseDict)


class MissingType(enum.Enum):
    token = 0


_T = t.TypeVar('_T')
MISSING: Literal[MissingType.token] = MissingType.token


class ParseError(ValueError):
    pass


class _ParserLike(abc.ABC, t.Generic[_T]):
    @abc.abstractmethod
    def try_parse(self, value: object) -> _T:
        ...


_VALUE_LIKE = t.TypeVar('_VALUE_LIKE', str, int, float, DatetimeWithTimezone)


class Value(t.Generic[_VALUE_LIKE], _ParserLike[_VALUE_LIKE]):
    __slots__ = ('__typ', )

    def __init__(self, typ: t.Type[_VALUE_LIKE]) -> None:
        self.__typ: Final[t.Type[_VALUE_LIKE]] = typ

    def try_parse(self, value: object) -> _VALUE_LIKE:
        if isinstance(value, self.__typ):
            return value
        raise



class ListOf(t.Generic[_T], _ParserLike[t.List[_T]]):
    __slots__ = ('__el_type', )

    def __init__(self, el_type: _ParserLike[_T]):
        self.__el_type: Final = el_type

    def try_parse(self, value: object) -> t.List[_T]:
        if not isinstance(value, list):
            raise

        el_type = self.__el_type
        res = []
        errors = []

        for item in value:
            try:
                res.append(el_type.try_parse(item))
            except ParseError as e:
                errors.append(e)
        if errors:
            raise
        else:
            return res


# class _RequiredArgument(t.Generic[_BASE_DICT]):
#     def __init__(
#         self,
#         key: str,
#         value: t.Type[ARG_TYPE],
#         doc: str,
#     ) -> None:
#         pass


# class _OptionalArgument(t.Generic[_BASE_DICT]):
#     def __init__(
#         self,
#         key: str,
#         value: t.Type[ARG_TYPE],
#         doc: str,
#     ) -> None:
#         pass


# @t.overload
# def argument(
#     key: str,
#     value: t.Type[ARG_TYPE],
#     doc: str,
#     *,
#     optional: Literal[False] = False
# ) -> _RequiredArgument[ARG_TYPE]:
#     ...


# @t.overload
# def argument(
#     key: str, value: t.Type[ARG_TYPE], doc: str, *, optional: Literal[True]
# ) -> _OptionalArgument[ARG_TYPE]:
#     if optional:
#         return _OptionalArgument(key, value, doc)
#     return _RequiredArgument(key, value, doc)


# def argument(
#     key: str, value: t.Type[ARG_TYPE], doc: str, *, optional: bool = False
# ) -> t.Union[_RequiredArgument[ARG_TYPE], _OptionalArgument[ARG_TYPE]]:
#     if optional:
#         return _OptionalArgument(key, value, doc)
#     return _RequiredArgument(key, value, doc)


# class _DictParser(t.Generic[_BASE_DICT]):
#     def add_option(cls, name: str, *arguments: t.Iterable[ARG_TYPE]) -> t.Any:
#         return ArgumentParser()


if t.TYPE_CHECKING:
    reveal_type(ListOf(Value(int)))
    list_of_ints1 = ListOf(Value(int)).try_parse('[asdfasdf]')
    list_of_ints2 = ListOf(Value(int)).try_parse([1, 2])
    reveal_type(list_of_ints1)
    reveal_type(list_of_ints2)
