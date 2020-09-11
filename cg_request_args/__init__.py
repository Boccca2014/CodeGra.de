from __future__ import annotations

import abc
import copy
import enum
import typing as t
import collections.abc

from typing_extensions import Final, Literal, Protocol, TypedDict

from cg_helpers import readable_join
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

_PARSE_ERROR = t.TypeVar('_PARSE_ERROR', bound='_ParseError')


class _ParseError(ValueError):
    __slots__ = ('parser', 'found', 'extra', 'location')

    def __init__(
        self,
        parser: _ParserLike,
        found: object,
        *,
        extra: t.Mapping[str, str] = None
    ):
        super().__init__()
        self.parser = parser
        self.found = found
        self.extra = {} if extra is None else extra
        self.location: t.Sequence[t.Union[int, str]] = []

    def _loc_to_str(self) -> str:
        res = []
        for idx, loc in enumerate(self.location):
            if idx == 0:
                res.append(str(loc))
            elif isinstance(loc, int):
                res.append('[{}]'.format(loc))
            else:
                res.append('.{}'.format(loc))

        return ''.join(res)

    def __str__(self) -> str:
        res = f'{self._to_str()}.'
        return f'{res[0].upper()}{res[1:]}'

    def _to_str(self) -> str:
        if self.found is MISSING:
            got = 'Nothing'
        else:
            got = repr(self.found)

        described = self.parser.describe()

        if described[0].lower() in ('a', 'i', 'e', 'u'):
            prefix = 'an'
        else:
            prefix = 'a'
        base = '{} {} is required, but got {}'.format(prefix, described, got)

        if self.extra.get('message') is not None:
            base = f'{base} ({self.extra["message"]})'

        if self.location:
            return 'at index "{}" {}'.format(self._loc_to_str(), base)
        return base

    def __copy__(self: _PARSE_ERROR) -> _PARSE_ERROR:
        res = type(self)(self.parser, self.found, extra=self.extra)
        res.location = self.location
        return res

    def add_location(
        self: _PARSE_ERROR, location: t.Union[int, str]
    ) -> _PARSE_ERROR:
        res = copy.copy(self)
        res.location = [location, *res.location]
        return res


class SimpleParseError(_ParseError):
    pass


class MultipleParseErrors(_ParseError):
    def __init__(
        self,
        parser: _ParserLike,
        found: object,
        errors: t.Sequence[_ParseError] = None,
        *,
        extra: t.Mapping[str, str] = None,
    ):
        super().__init__(parser, found, extra=extra)
        self.errors = [] if errors is None else errors

    def __copy__(self) -> MultipleParseErrors:
        res = super().__copy__()
        res.errors = self.errors
        return res

    def _to_str(self) -> str:
        res = super()._to_str()
        if not self.errors:
            return res
        reasons = readable_join([err._to_str() for err in self.errors])
        return f'{res}, which is incorrect because {reasons}'


class _ParserLike(t.Generic[_T_COV]):
    @abc.abstractmethod
    def try_parse(self, value: object) -> _T_COV:
        ...

    @abc.abstractmethod
    def describe(self) -> str:
        ...

    def __or__(self: _ParserLike[_T],
               other: _ParserLike[_Y]) -> _ParserLike[t.Union[_T, _Y]]:
        return Union(self, other)


class Union(t.Generic[_T, _Y], _ParserLike[t.Union[_T, _Y]]):
    __slots__ = ('__parser', )

    def __init__(
        self, first: _ParserLike[_T], second: _ParserLike[_Y]
    ) -> None:
        self.__parser: _ParserLike[t.Union[_T, _Y]]

        if isinstance(first, SimpleValue) and isinstance(second, SimpleValue):
            self.__parser = _SimpleUnion(first.typ, second.typ)
        elif (
            isinstance(first, _SimpleUnion) and
            isinstance(second, SimpleValue)
        ):
            self.__parser = _SimpleUnion(*first.typs, second.typ)
        elif (
            isinstance(first, SimpleValue) and
            isinstance(second, _SimpleUnion)
        ):
            self.__parser = _SimpleUnion(first.typ, *second.typs)
        elif (
            isinstance(first, _SimpleUnion) and
            isinstance(second, _SimpleUnion)
        ):
            self.__parser = _SimpleUnion(*first.typs, *second.typs)
        else:
            self.__parser = _RichUnion(first, second)

    def describe(self) -> str:
        return self.__parser.describe()

    def try_parse(self, value: object) -> t.Union[_T, _Y]:
        return self.__parser.try_parse(value)


_SIMPLE_VALUE = t.TypeVar('_SIMPLE_VALUE', str, int, float, bool, None)

_TYPE_NAME_LOOKUP = {
    str: 'str',
    float: 'float',
    bool: 'bool',
    int: 'int',
    type(None): 'None',
    dict: 'mapping',
    list: 'list',
}


def _type_to_name(typ: t.Type) -> str:
    if typ in _TYPE_NAME_LOOKUP:
        return _TYPE_NAME_LOOKUP[typ]
    return str(typ)


class SimpleValue(t.Generic[_SIMPLE_VALUE], _ParserLike[_SIMPLE_VALUE]):
    __slots__ = ('typ', )

    def describe(self) -> str:
        return _type_to_name(self.typ)

    def __init__(self, typ: t.Type[_SIMPLE_VALUE]) -> None:
        self.typ: Final[t.Type[_SIMPLE_VALUE]] = typ

    def try_parse(self, value: object) -> _SIMPLE_VALUE:
        if isinstance(value, self.typ):
            return value
        raise SimpleParseError(self, found=value)


_SIMPLE_UNION = t.TypeVar(
    '_SIMPLE_UNION', bound=t.Union[str, int, float, bool, None]
)


class _SimpleUnion(t.Generic[_SIMPLE_UNION], _ParserLike[_SIMPLE_UNION]):
    __slots__ = ('typs', )

    def __init__(self, *typs: t.Type[_SIMPLE_UNION]) -> None:
        self.typs: Final[t.Tuple[t.Type[_SIMPLE_UNION], ...]] = typs

    def describe(self) -> str:
        return 'Union[{}]'.format(', '.join(map(_type_to_name, self.typs)))

    def try_parse(self, value: object) -> _SIMPLE_UNION:
        if isinstance(value, self.typs):
            return value  # type: ignore
        raise SimpleParseError(
            self,
            value,
            extra={
                'message':
                    '(which is of type {})'.format(_type_to_name(type(value)))
            }
        )


_ENUM = t.TypeVar('_ENUM', bound=enum.Enum)


class EnumValue(t.Generic[_ENUM], _ParserLike[_ENUM]):
    ___slots__ = ('__typ', )

    def __init__(self, typ: t.Type[_ENUM]) -> None:
        self.__typ = typ

    def describe(self) -> str:
        return 'Enum[{}]'.format(
            ', '.join(repr(opt.name) for opt in self.__typ)
        )

    def try_parse(self, value: object) -> _ENUM:
        if not isinstance(value, str):
            raise SimpleParseError(
                self,
                value,
                extra={
                    'message':
                        'which is of type {}, not string'.format(
                            _type_to_name(type(value))
                        )
                }
            )

        try:
            return self.__typ[value]
        except KeyError as err:
            raise SimpleParseError(self, value) from err


class _RichUnion(t.Generic[_T, _Y], _ParserLike[t.Union[_T, _Y]]):
    __slots__ = ('__first', '__second')

    def __init__(
        self, first: _ParserLike[_T], second: _ParserLike[_Y]
    ) -> None:
        self.__first = first
        self.__second = second

    def describe(self) -> str:
        return f'Union[{self.__first.describe()}, {self.__second.describe()}]'

    def try_parse(self, value: object) -> t.Union[_T, _Y]:
        try:
            return self.__first.try_parse(value)
        except _ParseError as first_err:
            try:
                return self.__second.try_parse(value)
            except _ParseError as second_err:
                raise SimpleParseError(
                    # TODO: Set extra
                    self,
                    value,
                    extra={}
                )


class List(t.Generic[_T], _ParserLike[t.List[_T]]):
    __slots__ = ('__el_type', )

    def __init__(self, el_type: _ParserLike[_T]):
        self.__el_type: Final = el_type

    def describe(self) -> str:
        return f'List[{self.__el_type.describe()}]'

    def try_parse(self, value: object) -> t.List[_T]:
        if not isinstance(value, list):
            raise SimpleParseError(self, value)

        el_type = self.__el_type
        res = []
        errors = []

        for idx, item in enumerate(value):
            try:
                res.append(el_type.try_parse(item))
            except _ParseError as e:
                errors.append(e.add_location(idx))

        if errors:
            raise MultipleParseErrors(self, value, errors)
        else:
            return res


_Key = t.TypeVar('_Key', bound=str)


class _Argument(t.Generic[_T, _Key]):
    __slots__ = ('key', 'value', 'doc')

    def __init__(
        self,
        key: _Key,
        value: _ParserLike[_T],
        doc: str,
    ) -> None:
        self.key: Final = key
        self.value = value
        self.doc = doc

    @abc.abstractmethod
    def describe(self) -> str:
        ...

    def try_parse(self, value: t.Mapping[str, object]
                  ) -> t.Union[_T, Literal[MissingType.token]]:
        if self.key not in value:
            return MISSING

        found = value[self.key]
        try:
            return self.value.try_parse(found)
        except _ParseError as err:
            raise err.add_location(self.key) from err


class RequiredArgument(t.Generic[_T, _Key], _Argument[_T, _Key]):
    def describe(self) -> str:
        return f'{self.key}: {self.value.describe()}'

    def try_parse(self, value: t.Mapping[str, object]) -> _T:
        res = super().try_parse(value)
        if res is MISSING:
            raise SimpleParseError(self.value, MISSING).add_location(self.key)
        return res


class OptionalArgument(t.Generic[_T, _Key], _Argument[_T, _Key]):
    def describe(self) -> str:
        return f'{self.key}?: {self.value.describe()}'


class _DictGetter(t.Generic[_BASE_DICT]):
    __slots__ = ('__data', )

    def __init__(self, data: _BASE_DICT) -> None:
        self.__data = data

    def __getattr__(self, key: str) -> object:
        return self.__data[key]

    def as_dict(self) -> _BASE_DICT:
        return self.__data


class FixedMapping(
    t.Generic[_BASE_DICT], _ParserLike[_DictGetter[_BASE_DICT]]
):
    __slots__ = ('__arguments', )

    def __init__(self, *arguments: object) -> None:
        self.__arguments = t.cast(t.Sequence[_Argument], arguments)

    def describe(self) -> str:
        return 'Mapping[{}]'.format(
            ', '.join(arg.describe() for arg in self.__arguments)
        )

    def try_parse(self, value: object) -> _DictGetter[_BASE_DICT]:
        if not isinstance(value, dict):
            raise SimpleParseError(self, value)

        result = {}
        errors = []
        for arg in self.__arguments:
            try:
                result[arg.key] = arg.try_parse(value)
            except _ParseError as exc:
                errors.append(exc)

        if errors:
            raise MultipleParseErrors(self, value, errors)

        return _DictGetter(t.cast(_BASE_DICT, result))


class Transform(t.Generic[_T, _Y], _ParserLike[_T]):
    __slots__ = ('__parser', '__transform', '__transform_name')

    def __init__(
        self,
        parser: _ParserLike[_Y],
        transform: t.Callable[[_Y], _T],
        transform_name: str,
    ):
        self.__parser = parser
        self.__transform = transform
        self.__transform_name = transform_name

    def describe(self) -> str:
        return f'{self.__transform_name} as {self.__parser.describe()}'

    def try_parse(self, value: object) -> _T:
        res = self.__parser.try_parse(value)
        return self.__transform(res)


class Constrainer(t.Generic[_T]):
    @abc.abstractmethod
    def ok(self, value: _T) -> bool:
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    def and_(self, other: Constrainer[_T]) -> Constrainer[_T]:
        return Constraints.And(self, other)


_SIZED = t.TypeVar('_SIZED', bound=collections.abc.Sized)


class Constraints:
    class And(t.Generic[_T], Constrainer[_T]):
        def __init__(
            self, first: Constrainer[_T], second: Constrainer[_T]
        ) -> None:
            self.__first = first
            self.__second = second

        @property
        def name(self) -> str:
            return f'{self.__first.name} and {self.__second.name}'

        def ok(self, value: _T) -> bool:
            return self.__first.ok(value) and self.__second.ok(value)

    class NotEmpty(Constrainer[_SIZED]):
        def ok(self, value: _SIZED) -> bool:
            return len(value) >= 0

        @property
        def name(self) -> str:
            return 'non empty'

    class NumberGt(Constrainer[int]):
        __slots__ = ('__minimum', )

        def __init__(self, minimum: int) -> None:
            self.__minimum: Final = minimum

        @property
        def name(self) -> str:
            return f'larger than {self.__minimum}'

        def ok(self, value: int) -> bool:
            return value >= self.__minimum


class Constraint(t.Generic[_T], _ParserLike[_T]):
    __slots__ = ('__parser', '__constraint')

    def __init__(
        self, parser: _ParserLike[_T],
        constraint: t.Union[Constrainer[_T], t.Callable[[], Constrainer[_T]]]
    ):
        self.__parser = parser
        if isinstance(constraint, Constrainer):
            self.__constraint = constraint
        else:
            self.__constraint = constraint()

    def describe(self) -> str:
        return f'{self.__parser.describe()} {self.__constraint.name}'

    def try_parse(self, value: object) -> _T:
        res = self.__parser.try_parse(value)
        if not self.__constraint.ok(res):
            raise SimpleParseError(self, value)
        return res


if __name__ == '__main__':

    class Enum(enum.Enum):
        a = 5
        b = 10

    mapping = FixedMapping(
        RequiredArgument(
            'a',
            (
                SimpleValue(str)
                | Transform(
                    SimpleValue(str), DatetimeWithTimezone.fromisoformat,
                    'Datetime'
                )
            ),
            'hello',
        ),
        OptionalArgument(
            'b',
            List(SimpleValue(int)),
            'hello',
        ),
        RequiredArgument(
            'c',
            FixedMapping(RequiredArgument('a', SimpleValue(str), 'sow')),
            'de',
        ),
        OptionalArgument('enum', EnumValue(Enum), 'weo'),
    )
    print(mapping.describe())

    res = mapping.try_parse({'a': 5, 'c': {'a': '6'}, 'enum': 'b'})
