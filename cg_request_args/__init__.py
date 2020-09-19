from __future__ import annotations

import abc
import ast
import copy
import enum
import json as _json
import typing as t
import datetime
import textwrap
import contextlib
import collections
import dataclasses
import email.utils

import yaml
import flask
import structlog
import validate_email
import dateutil.parser
from typing_extensions import Final, Literal, Protocol, TypedDict
from werkzeug.datastructures import FileStorage

import cg_maybe
from cg_helpers import readable_join
from cg_dt_utils import DatetimeWithTimezone

logger = structlog.get_logger()

if t.TYPE_CHECKING:
    from .open_api import OpenAPISchema


class _BaseDict(TypedDict):
    pass


_BASE_DICT = t.TypeVar('_BASE_DICT', bound=_BaseDict)


class MissingType(enum.Enum):
    token = 0


_GENERATE_SCHEMA: t.Optional['OpenAPISchema'] = None


@contextlib.contextmanager
def _schema_generator(schema: 'OpenAPISchema'
                      ) -> t.Generator[None, None, None]:
    global _GENERATE_SCHEMA
    _GENERATE_SCHEMA = schema
    try:
        yield
    finally:
        _GENERATE_SCHEMA = None


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


@dataclasses.dataclass(frozen=True)
class _SwaggerFunc:
    __slots__ = ('operation_name', 'no_data', 'func')
    operation_name: str
    no_data: bool
    func: t.Callable


_SWAGGER_FUNCS: t.Dict[str, _SwaggerFunc] = {}


def swaggerize(operation_name: str,
               no_data: bool = False) -> t.Callable[[_T_CAL], _T_CAL]:
    def __wrapper(func: _T_CAL) -> _T_CAL:
        if func.__name__ in _SWAGGER_FUNCS:
            raise AssertionError(
                'The function {} was already registered.'.format(
                    func.__name__
                )
            )
        _SWAGGER_FUNCS[func.__name__
                       ] = _SwaggerFunc(operation_name, no_data, func)
        return func

    return __wrapper


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


_T_PARSER_LIKE = t.TypeVar('_T_PARSER_LIKE', bound='_ParserLike')


class _ParserLike(t.Generic[_T_COV]):
    __slots__ = ('__description', )

    def __init__(self) -> None:
        self.__description: t.Optional[str] = None

    def add_description(
        self: _T_PARSER_LIKE, description: str
    ) -> _T_PARSER_LIKE:
        self.__description = description
        return self

    @abc.abstractmethod
    def try_parse(self, value: object) -> _T_COV:
        ...

    @abc.abstractmethod
    def describe(self) -> str:
        ...

    @abc.abstractmethod
    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        ...

    def to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        res = self._to_open_api(schema)
        if self.__description is not None:
            desc = schema.make_comment(self.__description)
            if '$ref' in res:
                return {'description': desc, 'allOf': [res]}
            return {**res, 'description': desc}
        return res

    def __or__(self: _ParserLike[_T],
               other: _ParserLike[_Y]) -> _ParserLike[t.Union[_T, _Y]]:
        return Union(self, other)

    def from_flask(
        self,
        *,
        log_replacer: t.Callable[[str, object], object] = None,
    ) -> _T_COV:
        if _GENERATE_SCHEMA is not None:
            json_schema = self.to_open_api(_GENERATE_SCHEMA)
            raise _Schema({'application/json': {'schema': json_schema}})

        json = flask.request.json()

        if isinstance(json, dict):
            to_log = json
            if log_replacer is not None:
                to_log = {k: log_replacer(k, v) for k, v in json.items()}
            logger.info('JSON request processed', request_data=to_log)
        elif log_replacer is None:
            logger.info('JSON request processed', request_data=to_log)
        else:
            # The replacers are used for top level objects, in this case it is
            # better to be extra sure we don't log passwords so simply the
            # type.
            logger.info(
                'JSON request processed',
                request_data='<FILTERED>',
                request_data_type=type(json),
            )

        try:
            return self.try_parse(json)
        except _ParseError as exc:
            if log_replacer is None:
                raise exc
            # Don't do ``from exc`` as that might leak the value
            raise SimpleParseError(  # pylint: disable=raise-missing-from
                self,
                '<REDACTED>',
                extra={
                    'message': (
                        'we cannot show you as this data should contain'
                        ' confidential information, but the input value was of'
                        ' type {}'
                    ).format(type(json))
                }
            )


class Union(t.Generic[_T, _Y], _ParserLike[t.Union[_T, _Y]]):
    __slots__ = ('__parser', )

    def __init__(
        self, first: _ParserLike[_T], second: _ParserLike[_Y]
    ) -> None:
        super().__init__()
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

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return self.__parser.to_open_api(schema)

    def try_parse(self, value: object) -> t.Union[_T, _Y]:
        return self.__parser.try_parse(value)


class Nullable(t.Generic[_T], _ParserLike[t.Union[_T, None]]):
    __slots__ = ('__parser', )

    def __init__(self, parser: _ParserLike[_T]):
        super().__init__()
        self.__parser = parser

    def describe(self) -> str:
        return f'Union[None, {self.__parser.describe()}]'

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return {
            **self.__parser.to_open_api(schema),
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
        super().__init__()
        self.typ: Final[t.Type[_SIMPLE_VALUE]] = typ

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return {'type': schema.simple_type_to_open_api_type(self.typ)}

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
        super().__init__()
        self.typs: Final[t.Tuple[t.Type[_SIMPLE_UNION], ...]] = typs

    def describe(self) -> str:
        return 'Union[{}]'.format(', '.join(map(_type_to_name, self.typs)))

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return {
            'anyOf': [
                schema.simple_type_to_open_api_type(t.cast(t.Type, typ))
                for typ in self.typs
            ]
        }

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
        super().__init__()
        self.__typ = typ

    def describe(self) -> str:
        return 'Enum[{}]'.format(
            ', '.join(repr(opt.name) for opt in self.__typ)
        )

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return schema.add_schema(self.__typ)

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
        super().__init__()
        self.__opts = opts

    def describe(self) -> str:
        return 'Enum[{}]'.format(', '.join(self.__opts))

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
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
        super().__init__()
        self.__first = first
        self.__second = second

    def describe(self) -> str:
        return f'Union[{self.__first.describe()}, {self.__second.describe()}]'

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return {
            'anyOf': [
                self.__first.to_open_api(schema),
                self.__second.to_open_api(schema)
            ]
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
        super().__init__()
        self.__el_type: Final = el_type

    def describe(self) -> str:
        return f'List[{self.__el_type.describe()}]'

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return {
            'type': 'array',
            'items': self.__el_type.to_open_api(schema),
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
    __slots__ = ('key', 'value')

    def __init__(
        self,
        key: _Key,
        value: _ParserLike[_T],
        doc: str,
    ) -> None:
        self.key: Final = key
        self.value = value
        self.value.add_description(doc)

    @abc.abstractmethod
    def describe(self) -> str:
        ...

    def to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return self.value.to_open_api(schema)

    def _try_parse(self, value: t.Mapping[str, object]) -> cg_maybe.Maybe[_T]:
        if self.key not in value:
            return cg_maybe.Nothing

        found = value[self.key]
        try:
            return cg_maybe.Just(self.value.try_parse(found))
        except _ParseError as err:
            raise err.add_location(self.key) from err


class RequiredArgument(t.Generic[_T, _Key], _Argument[_T, _Key]):
    def describe(self) -> str:
        return f'{self.key}: {self.value.describe()}'

    def try_parse(self, value: t.Mapping[str, object]) -> _T:
        res = self._try_parse(value)
        if isinstance(res, cg_maybe.Just):
            return res.value
        raise SimpleParseError(self.value, MISSING).add_location(self.key)


class OptionalArgument(t.Generic[_T, _Key], _Argument[_T, _Key]):
    def describe(self) -> str:
        return f'{self.key}?: {self.value.describe()}'

    def try_parse(self, value: t.Mapping[str, object]) -> cg_maybe.Maybe[_T]:
        return self._try_parse(value)


class _DictGetter(t.Generic[_BASE_DICT]):
    __slots__ = ('__data', )

    def __init__(self, data: _BASE_DICT) -> None:
        self.__data = data

    def __getattr__(self, key: str) -> object:
        return self.__data[key]

    def get(self, key: str) -> object:
        return self.__data.get(key)

    def __getitem__(self, key: str) -> object:
        return self.__data[key]

    def as_dict(self) -> _BASE_DICT:
        return self.__data


_T_FIXED_MAPPING = t.TypeVar('_T_FIXED_MAPPING', bound='FixedMapping')


class FixedMapping(
    t.Generic[_BASE_DICT], _ParserLike[_DictGetter[_BASE_DICT]]
):
    __slots__ = ('__arguments', '__tag', '__schema')

    def __init__(self, *arguments: object) -> None:
        super().__init__()
        self.__tag: t.Optional[t.Tuple[str, str]] = None
        self.__arguments = t.cast(
            t.Sequence[t.Union[RequiredArgument, OptionalArgument]], arguments
        )
        self.__schema: t.Optional[t.Type[_BASE_DICT]] = None

    def set_schema(self, schema: t.Type[_BASE_DICT]) -> None:
        """
        """
        self.__schema = schema

    def describe(self) -> str:
        return 'Mapping[{}]'.format(
            ', '.join(arg.describe() for arg in self.__arguments)
        )

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        if self.__schema is not None:
            return schema.add_schema(self.__schema)

        required = [
            arg.key for arg in self.__arguments
            if isinstance(arg, RequiredArgument)
        ]
        res = {
            'type': 'object',
            'properties': {
                arg.key: arg.to_open_api(schema)
                for arg in self.__arguments
            },
        }
        if required:
            res['required'] = required
        return res

    def add_tag(self, key: str, value: str) -> FixedMapping[_BASE_DICT]:
        self.__tag = (key, value)
        return self

    def try_parse(
        self,
        value: object,
    ) -> _DictGetter[_BASE_DICT]:
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

        if self.__tag is not None:
            result[self.__tag[0]] = self.__tag[1]

        return _DictGetter(t.cast(_BASE_DICT, result))

    def combine(self, other: FixedMapping[t.Any]) -> FixedMapping[_BaseDict]:
        args = [*self.__arguments, *other.__arguments]
        return FixedMapping(*args)  # type: ignore


class LookupMapping(t.Generic[_T], _ParserLike[t.Mapping[str, _T]]):
    __slots__ = ('parser', )

    def __init__(self, parser: _ParserLike[_T]) -> None:
        super().__init__()
        self.__parser = parser

    def describe(self) -> str:
        return 'Mapping[str: {}]'.format(self.__parser.describe())

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return {
            'type': 'object',
            'additionalProperties': self.__parser.to_open_api(schema),
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
        super().__init__()
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
        super().__init__()
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

    def _to_open_api(self, schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
        return self._parser.to_open_api(schema)

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

        def _to_open_api(self,
                         schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
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

    class _EmailList(Constraint[str]):
        def __init__(self) -> None:
            super().__init__(SimpleValue(str))

        def ok(self, to_parse: str) -> bool:
            addresses = email.utils.getaddresses([to_parse.strip()])
            return (
                validate_email.validate_email(email) for _, email in addresses
            )

        @property
        def name(self) -> str:
            return ' as email list'

    EmailList = _EmailList()

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

        def _to_open_api(self,
                         schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
            return {
                **self._parser.to_open_api(schema),
                'minimum': self.__minimum,
            }

    class _Password(SimpleValue[str]):
        def __init__(self) -> None:
            super().__init__(str)

        def describe(self) -> str:
            return f'password as {super().describe()}'

        def _to_open_api(self,
                         schema: 'OpenAPISchema') -> t.Mapping[str, t.Any]:
            return {**super()._to_open_api(schema), 'format': 'password'}

        def try_parse(self, value: object) -> str:
            try:
                return super().try_parse(value)
            except _ParseError as exc:
                # Don't raise from as that might leak the value
                raise SimpleParseError(self, found='REDACTED')  # pylint: disable=raise-missing-from

    Password = _Password()


def __from_python_type(typ):  # type: ignore
    # This function doesn't play nice at all with our plugins, so simply skip
    # checking it.

    origin = getattr(typ, '__origin__', None)

    if isinstance(typ, type(TypedDict)):
        args = []
        for key, subtyp in typ.__annotations__.items():
            if key in typ.__required_keys__:
                args.append(
                    RequiredArgument(key, from_python_type(subtyp), '')
                )
            else:
                args.append(
                    OptionalArgument(key, from_python_type(subtyp), '')
                )
        res = FixedMapping(*args)
        res.set_schema(typ)
        return res
    elif typ in (str, int, bool):
        return SimpleValue(typ)
    elif origin in (list, collections.abc.Sequence):
        return List(from_python_type(typ.__args__[0]))
    elif origin == t.Union:
        res = from_python_type(typ.__args__[0])
        for item in typ.__args__[1:]:
            res = res | from_python_type(item)
        return res
    elif origin == Literal:
        return StringEnum(*typ.__args__)
    else:
        raise AssertionError(f'Could not convert: {typ}')


def from_python_type(typ: t.Type[_T]) -> _ParserLike[_T]:
    """Wrapper function to convert a python type to a ``cg_request_args``
    validator.

    Doing this is quite slow, so it is wise to do this only when loading the
    application (i.e. on top level).
    """
    return __from_python_type(typ)


class MultipartUpload(t.Generic[_T]):
    __slots__ = ('__parser', '__file_key', '__multiple')

    def __init__(
        self,
        parser: _ParserLike[_T],
        file_key: str,
        multiple: bool,
    ) -> None:
        self.__parser = parser
        self.__file_key = file_key
        self.__multiple = multiple

    def from_flask(self, ) -> t.Tuple[_T, t.Sequence[FileStorage]]:
        if _GENERATE_SCHEMA is not None:
            json_schema = self.__parser.to_open_api(_GENERATE_SCHEMA)
            file_type: t.Mapping[str, t.Any] = {
                'type': 'string',
                'format': 'binary',
            }
            if self.__multiple:
                file_type = {
                    'type': 'array',
                    'items': {**file_type},
                }
            raise _Schema({
                'multipart/form-data': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'json': json_schema,
                            self.__file_key: file_type,
                        },
                    },
                },
            })

        body = None
        if 'json' in flask.request.files:
            body = _json.load(flask.request.files['json'])
        if not body:
            body = flask.request.json()

        if isinstance(body, dict):
            to_log = body
            logger.info('JSON request processed', request_data=body)
        else:
            logger.info('JSON request processed', request_data=to_log)

        result = self.__parser.try_parse(body)

        if not flask.request.files:
            files = []
        elif self.__multiple:
            files = flask.request.files.getlist(self.__file_key)
            for key, f in flask.request.files.items():
                if key != self.__file_key and key.startswith(self.__file_key):
                    files.append(f)
        else:
            files = flask.request.files.get(self.__file_key, default=[])

        files = [f for f in files if f.filename]
        return result, files
