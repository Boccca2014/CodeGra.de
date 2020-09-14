from __future__ import annotations

import abc
import ast
import copy
import enum
import typing as t
import datetime
import textwrap
import contextlib

import yaml
import flask
import dateutil.parser
from typing_extensions import Final, Literal, Protocol, TypedDict

from cg_helpers import readable_join
from cg_dt_utils import DatetimeWithTimezone


class _BaseDict(TypedDict):
    pass


_BASE_DICT = t.TypeVar('_BASE_DICT', bound=_BaseDict)


class MissingType(enum.Enum):
    token = 0


_GENERATE_SCHEMA = False


@contextlib.contextmanager
def _schema_generator() -> t.Generator[None, None, None]:
    global _GENERATE_SCHEMA
    _GENERATE_SCHEMA = True
    try:
        yield
    finally:
        _GENERATE_SCHEMA = False


class _Schema(BaseException):
    def __init__(self, schema: t.Mapping[str, t.Any]) -> None:
        super().__init__()
        self.schema = schema


_T = t.TypeVar('_T')
_T_COV = t.TypeVar('_T_COV', covariant=True)
_Y = t.TypeVar('_Y')
_Z = t.TypeVar('_Z')
_X = t.TypeVar('_X')
MISSING: Literal[MissingType.token] = MissingType.token

_PARSE_ERROR = t.TypeVar('_PARSE_ERROR', bound='_ParseError')

_T_CAL = t.TypeVar('_T_CAL', bound=t.Callable)

_SWAGGER_FUNCS = []


def swagerize(func: _T_CAL) -> _T_CAL:
    _SWAGGER_FUNCS.append(func)
    return func


class _Just(t.Generic[_T]):
    __slots__ = ('value')

    is_just: Literal[True] = True
    is_nothing: Literal[False] = False

    def __init__(self, value: _T) -> None:
        self.value: Final = value


class _Nothing:
    __slots__ = ()

    is_just: Literal[False] = False
    is_nothing: Literal[True] = True


Nothing = _Nothing()


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

    @abc.abstractmethod
    def to_open_api(self) -> t.Mapping[str, t.Any]:
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

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return self.__parser.to_open_api()

    def try_parse(self, value: object) -> t.Union[_T, _Y]:
        return self.__parser.try_parse(value)


class Nullable(t.Generic[_T], _ParserLike[t.Union[_T, None]]):
    __slots__ = ('__parser', )

    def __init__(self, parser: _ParserLike[_T]):
        self.__parser = parser

    def describe(self) -> str:
        return f'Union[None, {self.__parser.describe()}]'

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {
            **self.__parser.to_open_api(),
            'nullable': True,
        }

    def try_parse(self, value: object) -> t.Optional[_T]:
        if value is None:
            return value

        try:
            return self.__parser.try_parse(value)
        except SimpleParseError as err:
            raise SimpleParseError(self, value) from err


_SIMPLE_VALUE = t.TypeVar('_SIMPLE_VALUE', str, int, float, bool, None)

_TYPE_OPEN_API_LOOKUP = {
    str: 'string',
    float: 'number',
    bool: 'boolean',
    int: 'integer',
    type(None): 'null',
}


def _type_to_open_api(typ: t.Type) -> str:
    return _TYPE_OPEN_API_LOOKUP[typ]


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

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {'type': _type_to_open_api(self.typ)}

    def try_parse(self, value: object) -> _SIMPLE_VALUE:
        if isinstance(value, self.typ):
            return value
        if self.typ is float and isinstance(value, int):
            return float(value)  # type: ignore
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

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {'anyOf': [_type_to_open_api(typ) for typ in self.typs]}

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

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {
            'type': 'string',
            'enum': [opt.name for opt in self.__typ],
        }

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


class StringEnum(t.Generic[_T], _ParserLike[_T]):
    __slots__ = ('__opts', )

    def __init__(self, *opts: str) -> None:
        self.__opts = opts

    def describe(self) -> str:
        return 'Enum[{}]'.format(', '.join(self.__opts))

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {
            'type': 'string',
            'enum': list(self.__opts),
        }

    def try_parse(self, value: object) -> _T:
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

        if value not in self.__opts:
            raise SimpleParseError(self, value)
        return t.cast(_T, value)


class _RichUnion(t.Generic[_T, _Y], _ParserLike[t.Union[_T, _Y]]):
    __slots__ = ('__first', '__second')

    def __init__(
        self, first: _ParserLike[_T], second: _ParserLike[_Y]
    ) -> None:
        self.__first = first
        self.__second = second

    def describe(self) -> str:
        return f'Union[{self.__first.describe()}, {self.__second.describe()}]'

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {
            'anyOf': [self.__first.to_open_api(),
                      self.__second.to_open_api()]
        }

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

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {
            'type': 'array',
            'items': self.__el_type.to_open_api(),
        }

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
        self.doc = textwrap.dedent(doc).strip()

    @abc.abstractmethod
    def describe(self) -> str:
        ...

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {**self.value.to_open_api(), 'description': self.doc}

    def try_parse(self, value: t.Mapping[str, object]
                  ) -> t.Union[_Just[_T], _Nothing, _T]:
        if self.key not in value:
            return Nothing

        found = value[self.key]
        try:
            return _Just(self.value.try_parse(found))
        except _ParseError as err:
            raise err.add_location(self.key) from err


class RequiredArgument(t.Generic[_T, _Key], _Argument[_T, _Key]):
    def describe(self) -> str:
        return f'{self.key}: {self.value.describe()}'

    def try_parse(self, value: t.Mapping[str, object]) -> _T:
        res = super().try_parse(value)
        if isinstance(res, _Just):
            return res.value
        raise SimpleParseError(self.value, MISSING).add_location(self.key)


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

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        required = [
            arg.key for arg in self.__arguments
            if isinstance(arg, RequiredArgument)
        ]
        res = {
            'type': 'object',
            'properties': {
                arg.key: arg.to_open_api()
                for arg in self.__arguments
            },
        }
        if required:
            res['required'] = required
        return res

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

    def from_flask(self) -> _DictGetter[_BASE_DICT]:
        if _GENERATE_SCHEMA:
            raise _Schema(self.to_open_api())
        json = flask.request.get_json()
        return self.try_parse(json)


class LookupMapping(t.Generic[_T], _ParserLike[t.Mapping[str, _T]]):
    __slots__ = ('parser', )

    def __init__(self, parser: _ParserLike[_T]) -> None:
        self.__parser = parser

    def describe(self) -> str:
        return 'Mapping[str: {}]'.format(self.__parser.describe())

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return {
            'type': 'object',
            'additionalProperties': self.__parser.to_open_api(),
        }

    def try_parse(self, value: object) -> t.Mapping[str, _T]:
        if not isinstance(value, dict):
            raise SimpleParseError(self, value)

        result = {}
        errors = []
        for key, val in value.items():
            try:
                result[key] = self.__parser.try_parse(val)
            except _ParseError as exc:
                errors.append(exc)
        if errors:
            raise MultipleParseErrors(self, value, errors)

        return result


class _Transform(t.Generic[_T, _Y], _ParserLike[_T]):
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


class Constraint(t.Generic[_T], _ParserLike[_T]):
    __slots__ = ('_parser')

    def __init__(self, parser: _ParserLike[_T]):
        self._parser = parser

    @abc.abstractmethod
    def ok(self, value: _T) -> bool:
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    def describe(self) -> str:
        return f'{self._parser.describe()} {self.name}'

    def to_open_api(self) -> t.Mapping[str, t.Any]:
        return self._parser.to_open_api()

    def try_parse(self, value: object) -> _T:
        res = self._parser.try_parse(value)
        if not self.ok(res):
            raise SimpleParseError(self, value)
        return res


class RichValue:
    class _DateTime(_Transform[DatetimeWithTimezone, str]):
        def __init__(self) -> None:
            super().__init__(
                SimpleValue(str), self.__transform_to_datetime, 'DateTime'
            )

        def to_open_api(self) -> t.Mapping[str, t.Any]:
            return {
                'type': 'string',
                'format': 'date-time',
            }

        def __transform_to_datetime(self, value: str) -> DatetimeWithTimezone:
            try:
                parsed = dateutil.parser.isoparse(value)
            except (ValueError, OverflowError) as exc:
                raise SimpleParseError(
                    self,
                    value,
                    extra={
                        'message': "which can't be parsed as a valid datetime",
                    },
                ) from exc
            else:
                return DatetimeWithTimezone.from_datetime(
                    parsed, default_tz=datetime.timezone.utc
                )

    DateTime = _DateTime()

    class NumberGte(Constraint[int]):
        __slots__ = ('__minimum', )

        def __init__(self, minimum: int) -> None:
            super().__init__(SimpleValue(int))
            self.__minimum: Final = minimum

        @property
        def name(self) -> str:
            return f'larger than {self.__minimum}'

        def ok(self, value: int) -> bool:
            return value >= self.__minimum

        def to_open_api(self) -> t.Mapping[str, t.Any]:
            return {
                **self._parser.to_open_api(),
                'minimum': self.__minimum,
            }


if __name__ == '__main__':

    class Enum(enum.Enum):
        a = 5
        b = 10

    open_api = FixedMapping(
        RequiredArgument(
            'a',
            SimpleValue(str),
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
        RequiredArgument('abd', LookupMapping(SimpleValue(bool)), 'wee'),
    ).from_flask()
