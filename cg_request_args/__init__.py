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
_T_COV = t.TypeVar('_T_COV', covariant=True)
_Y = t.TypeVar('_Y')
_Z = t.TypeVar('_Z')
_X = t.TypeVar('_X')
MISSING: Literal[MissingType.token] = MissingType.token


class ParseError(ValueError):
    pass


class _ParserLike(t.Generic[_T_COV]):
    @abc.abstractmethod
    def try_parse(self, value: object) -> _T_COV:
        ...

    def __or__(self: _ParserLike[_T],
               other: _ParserLike[_Y]) -> _ParserLike[t.Union[_T, _Y]]:
        if (isinstance(self,
                       _SimpleValue)) and isinstance(other, _SimpleValue):
            return _SimpleUnion(self.typ, other.typ)
        if (isinstance(self,
                       _SimpleUnion)) and isinstance(other, _SimpleValue):
            return _SimpleUnion(*self.typs, other.typ)
        if (isinstance(self,
                       _SimpleValue)) and isinstance(other, _SimpleUnion):
            return _SimpleUnion(self.typ, *other.typs)
        if (isinstance(self,
                       _SimpleUnion)) and isinstance(other, _SimpleUnion):
            return _SimpleUnion(*self.typs, *other.typs)
        return _Union(self, other)


_SIMPLE_VALUE = t.TypeVar('_SIMPLE_VALUE', str, int, float, bool, None)


class _SimpleValue(t.Generic[_SIMPLE_VALUE], _ParserLike[_SIMPLE_VALUE]):
    __slots__ = ('typ', )

    def __init__(self, typ: t.Type[_SIMPLE_VALUE]) -> None:
        self.typ: Final[t.Type[_SIMPLE_VALUE]] = typ

    def try_parse(self, value: object) -> _SIMPLE_VALUE:
        if isinstance(value, self.typ):
            return value
        raise


_SIMPLE_UNION = t.TypeVar(
    '_SIMPLE_UNION', bound=t.Union[str, int, float, bool, None]
)


class _SimpleUnion(t.Generic[_SIMPLE_UNION], _ParserLike[_SIMPLE_UNION]):
    __slots__ = ('typs', )

    def __init__(self, *typs: t.Type[_SIMPLE_UNION]) -> None:
        self.typs: Final[t.Tuple[t.Type[_SIMPLE_UNION], ...]] = typs

    def try_parse(self, union: object) -> _SIMPLE_UNION:
        if isinstance(union, self.typs):
            return union  # type: ignore
        raise


class _RichValue(t.Generic[_SIMPLE_VALUE, _T], _ParserLike[_T]):
    __slots__ = ('__value', '__converter')

    def __init__(
        self, typ: t.Type[_SIMPLE_VALUE],
        converter: t.Callable[[_SIMPLE_VALUE], _T]
    ) -> None:
        self.__value: Final[_SimpleValue[_SIMPLE_VALUE]] = _SimpleValue(typ)
        self.__converter: Final[t.Callable[[_SIMPLE_VALUE], _T]] = converter

    def try_parse(self, value: object) -> _T:
        res = self.__value.try_parse(value)
        # TODO: Error handling
        return self.__converter(res)


class _Union(t.Generic[_T, _Y], _ParserLike[t.Union[_T, _Y]]):
    __slots__ = ('__first', '__second')

    def __init__(
        self, first: _ParserLike[_T], second: _ParserLike[_Y]
    ) -> None:
        self.__first = first
        self.__second = second

    def try_parse(self, value: object) -> t.Union[_T, _Y]:
        try:
            return self.__first.try_parse(value)
        except ParseError as first_err:
            try:
                return self.__second.try_parse(value)
            except ParseError as second_err:
                raise


class _List(t.Generic[_T], _ParserLike[t.List[_T]]):
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


_Key = t.TypeVar('_Key', bound=str)


class _Argument(t.Generic[_T, _Key], _ParserLike[_T]):
    __slots__ = ('key', '__value', '__doc')

    def __init__(
        self,
        key: _Key,
        value: _ParserLike[_T],
        doc: str,
    ) -> None:
        self.key: Final = key
        self.__value = value
        self.__doc = doc

    def try_parse(self, value: object) -> _T:
        return self.__value.try_parse(value)


class _RequiredArgument(t.Generic[_T, _Key], _Argument[_T, _Key]):
    pass


class _OptionalArgument(t.Generic[_T, _Key], _Argument[_T, _Key]):
    pass


class _FixedMapping(t.Generic[_BASE_DICT], _ParserLike[_BASE_DICT]):
    __slots__ = ('__arguments', )

    def __init__(self, *arguments: object) -> None:
        self.__arguments = t.cast(t.Sequence[_Argument], arguments)

    def try_parse(self, value: object) -> _BASE_DICT:
        if not isinstance(value, dict):
            raise

        result = {}
        errors = []
        for arg in self.__arguments:
            if arg.key not in value:
                if isinstance(arg, _OptionalArgument):
                    result[arg.key] = MISSING
                else:
                    errors.append(ParseError())
                continue

            try:
                result[arg.key] = arg.try_parse(value[arg.key])
            except ParseError as exc:
                errors.append(exc)

        if errors:
            raise

        return t.cast(_BASE_DICT, result)


if __name__ == '__main__':
    mapping = _FixedMapping(
        _RequiredArgument(
            'a',
            _Union(
                _SimpleValue(str),
                _RichValue(str, DatetimeWithTimezone.fromisoformat),
            ),
            'hello',
        ),
        _OptionalArgument(
            'b',
            _List(_SimpleValue(int)),
            'hello',
        ),
    )

    print(_SimpleValue(int) | _SimpleValue(str))

    print(mapping.try_parse({'a': 'd', 'b': [10, 100]}))
