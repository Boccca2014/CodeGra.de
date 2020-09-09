from __future__ import annotations

import enum
import typing as t

from typing_extensions import Literal, TypedDict

from cg_dt_utils import DatetimeWithTimezone


class _BaseDict(TypedDict):
    pass


_BASE_DICT = t.TypeVar('_BASE_DICT', bound=_BaseDict)

VALUE_LIKE = t.Union[str, int, float, DatetimeWithTimezone]

ARG_TYPE = t.TypeVar(
    'ARG_TYPE', bound='t.Union[_RequiredArgument, _OptionalArgument, VALUE_LIKE, ListOf]'
)


class MissingType(enum.Enum):
    token = 0


MISSING: Literal[MissingType.token] = MissingType.token


class ListOf(t.Generic[ARG_TYPE]):
    def __init__(self, value: t.Type[ARG_TYPE]):
        self._value = value


class _RequiredArgument(t.Generic[_BASE_DICT]):
    def __init__(
        self,
        key: str,
        value: t.Type[ARG_TYPE],
        doc: str,
    ) -> None:
        pass


class _OptionalArgument(t.Generic[_BASE_DICT]):
    def __init__(
            self,
        key: str,
        value: t.Type[ARG_TYPE],
        doc: str,
    ) -> None:
        pass


@t.overload
def argument(
    key: str,
    value: t.Type[ARG_TYPE],
    doc: str,
    *,
    optional: Literal[False] = False
) -> _RequiredArgument[ARG_TYPE]:
    ...


@t.overload
def argument(
    key: str, value: t.Type[ARG_TYPE], doc: str, *, optional: Literal[True]
) -> _OptionalArgument[ARG_TYPE]:
    if optional:
        return _OptionalArgument(key, value, doc)
    return _RequiredArgument(key, value, doc)


def argument(
    key: str, value: t.Type[ARG_TYPE], doc: str, *, optional: bool = False
) -> t.Union[_RequiredArgument[ARG_TYPE], _OptionalArgument[ARG_TYPE]]:
    if optional:
        return _OptionalArgument(key, value, doc)
    return _RequiredArgument(key, value, doc)


class ArgumentParser(t.Generic[_BASE_DICT]):
    @classmethod
    def make_decorator(cls, name: str, *arguments: t.Iterable[ARG_TYPE])  -> t.Any:
        return ArgumentParser()


if t.TYPE_CHECKING:
    @ArgumentParser.make_decorator('parser', argument('id', int, 'some doc'))
    def tester(parser: object) -> t.Any:
        pass
