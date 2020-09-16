import re
import sys
import typing as t
import inspect
import datetime
import collections
from enum import Enum, EnumMeta
from collections import OrderedDict, defaultdict

import flask
import sphinx.pycode
from typing_extensions import TypedDict

import psef
import cg_json
import cg_flask_helpers
from cg_dt_utils import DatetimeWithTimezone

from . import _SWAGGER_FUNCS, _Schema, _schema_generator

_SIMPLE_TYPE_NAME_LOOKUP = {
    str: 'string',
    float: 'number',
    bool: 'boolean',
    int: 'integer',
    type(None): 'null',
}


def _to_pascalcase(string: str) -> str:
    return ''.join(map(str.title, string.split('_')))


def _to_camelcase(string: str) -> str:
    first, *others = string.split('_')
    return ''.join([first.lower(), *map(str.title, others)])


def _clean_comment(comment: str) -> str:
    return ' '.join(
        line.strip() for line in comment.splitlines() if line.strip()
    )


def _first_docstring_line(doc: t.Optional[str]) -> str:
    first = (doc or '').split('\n\n')[0]
    return _clean_comment(first)


class _Tag(TypedDict):
    name: str
    description: str


class OpenAPISchema:
    def __init__(self, type_globals: t.Dict[str, t.Any]) -> None:
        self._paths: t.Dict[str, t.Dict[str, t.Mapping]] = defaultdict(dict)
        self._schemas: t.Dict[str, t.Mapping] = {}
        self._type_globals = type_globals
        self._parsed_modules: t.Dict[str, sphinx.pycode.parser.Parser] = {}
        self._tags: t.Dict[str, _Tag] = {}
        self._set_initial_schemas()

    def _set_initial_schemas(self) -> None:
        initial = {
            'BaseError': {
                'type': 'object', 'properties': {
                    'message': {'type': 'string'},
                    'description': {'type': 'string'},
                    'code': self.add_schema(psef.errors.APICodes),
                    'request_id': {
                        'type': 'string',
                        'format': 'uuid',
                        'description':
                            _clean_comment(
                                """
                                            The id of the request that went
                                            wrong. Please include this id when
                                            reporting bugs.
                                            """
                            ),
                    },
                }
            },
        }
        self._schemas.update(initial)

    @staticmethod
    def _get_schema_name(typ: t.Type) -> str:
        return typ.__qualname__

    def _maybe_add_tag(self, tag: str, func: t.Callable) -> None:
        if tag in self._tags:
            return
        description = _first_docstring_line(
            sys.modules[func.__module__ or ''].__doc__
        )
        if description:
            self._tags[tag] = {'name': tag, 'description': description}

    def _find_and_add_tags(self, endpoint: t.Callable) -> t.List[str]:
        for line in (endpoint.__doc__ or '').splitlines():
            if '.. :quickref: ' in line:
                tags = [line.split('.. :quickref: ', 1)[-1].split(';', 1)[0]]
                for tag in tags:
                    self._maybe_add_tag(tag, endpoint)
                return tags
        raise AssertionError('Could not find quickref in docstring')

    def _maybe_resolve_forward(
        self, typ: t.Union[t.Type, t.ForwardRef]
    ) -> t.Type:
        if isinstance(typ, t.ForwardRef):
            return self._maybe_resolve_forward(
                t.cast(t.Type, typ._evaluate(self._type_globals, {}))
            )
        return typ

    def _comments_of(self, typ: t.Type, field: str) -> str:
        if typ.__module__ not in self._parsed_modules:
            with open(typ.__module__.replace('.', '/') + '.py', 'r') as code:
                parser = sphinx.pycode.parser.Parser(code.read())
                parser.parse()
                self._parsed_modules[typ.__module__] = parser

        parsed = self._parsed_modules[typ.__module__]
        if typ.__name__ == 'AsExtendedJSON':
            try:
                return parsed.comments[(typ.__qualname__, field)]
            except KeyError:
                return parsed.comments[(
                    typ.__qualname__.replace('.AsExtendedJSON', '.AsJSON'),
                    field,
                )]
        try:
            return parsed.comments[(typ.__qualname__, field)]
        except KeyError:
            if hasattr(typ, '__cg_extends__'):
                return parsed.comments[
                    (typ.__cg_extends__.__qualname__, field)]
            raise

    @staticmethod
    def simple_type_to_open_api_type(
        typ: t.Type[t.Union[str, int, float, bool, None]]
    ) -> str:
        return _SIMPLE_TYPE_NAME_LOOKUP[typ]

    def add_schema(self, _typ: t.Type) -> t.Mapping[str, str]:
        _typ = self._maybe_resolve_forward(_typ)
        schema_name = self._get_schema_name(_typ)

        if schema_name in self._schemas:
            pass
        elif isinstance(_typ, type(TypedDict)):
            typ: t.Any = _typ
            properties = {}
            self._schemas[schema_name] = {
                'infinite_recursion_preventer': '<PLACEHOLDER>'
            }

            for prop, prop_type in typ.__annotations__.items():
                prop_dct = self._typ_to_schema(prop_type, next_extended=False)
                if '$ref' in prop_dct:
                    prop_dct = {'allOf': [prop_dct]}
                properties[prop] = {
                    **prop_dct,
                    'description':
                        _clean_comment(
                            self._comments_of(typ, prop),
                        ),
                }

            # We know that every ``AsExtendedJSON`` extends the normal
            # ``AsJSON``, however this is not save in the object for some
            # reason, so we simply retrieve the ``AsJSON`` class and remove all
            # properties that one has from our found properties.
            base_as_json = None
            if typ.__name__ == 'AsExtendedJSON':
                base_as_json = getattr(
                    sys.modules[typ.__module__],
                    typ.__qualname__.split('.')[0]
                ).AsJSON
            elif hasattr(typ, '__cg_extends__'):
                base_as_json = typ.__cg_extends__

            if base_as_json is not None:

                base = self.add_schema(base_as_json)
                extra_props = {
                    k: v
                    for k, v in properties.items()
                    if k not in base_as_json.__annotations__
                }
                extra_items = {
                    'type': 'object',
                    'properties': extra_props,
                    'required': [
                        p for p in extra_props if p in typ.__required_keys__
                    ],
                }
                self._schemas[schema_name] = {'allOf': [base, extra_items]}
            else:
                self._schemas[schema_name] = {
                    'type': 'object',
                    'properties': properties,
                    'required': [
                        p for p in typ.__annotations__.keys()
                        if p in typ.__required_keys__
                    ],
                }
        elif isinstance(_typ, EnumMeta):
            enum: t.Type[Enum] = _typ
            self._schemas[schema_name] = {
                'type': 'string',
                'enum': [e.name for e in enum],
            }
        else:
            raise AssertionError('Cannot make scheme for {}'.format(_typ))

        return {'$ref': f'#/components/schemas/{schema_name}'}

    def _typ_to_schema(self, typ: t.Type,
                       next_extended: bool) -> t.Mapping[str, t.Any]:
        typ = self._maybe_resolve_forward(typ)

        origin = getattr(typ, '__origin__', None)

        if isinstance(typ, type(TypedDict)):
            return self.add_schema(typ)
        elif typ in (int, str, bool, float):
            return {'type': self.simple_type_to_open_api_type(typ)}
        elif typ == DatetimeWithTimezone:
            return {
                'type': 'string',
                'format': 'date-time',
            }
        elif typ == datetime.timedelta:
            return {
                'type': 'number',
                'format': 'time-delta',
            }
        elif origin in (list, collections.abc.Sequence):
            return {
                'type': 'array',
                'items':
                    self._typ_to_schema(
                        typ.__args__[0], next_extended=next_extended
                    ),
            }
        elif origin == t.Union:
            nullable = False
            if type(None) in typ.__args__:
                nullable = True
            any_of = [
                self._typ_to_schema(arg, next_extended=next_extended)
                for arg in typ.__args__ if arg != type(None)
            ]
            if len(any_of) > 1:
                return {
                    'anyOf': any_of,
                    'nullable': nullable,
                }
            elif '$ref' in any_of[0]:
                return {
                    'allOf': any_of,
                    'nullable': True,
                }
            else:
                return {**any_of[0], 'nullable': nullable}
        elif origin == cg_json.JSONResponse:
            return self._typ_to_schema(typ.__args__[0], next_extended=False)
        elif origin == cg_json.ExtendedJSONResponse:
            return self._typ_to_schema(typ.__args__[0], next_extended=True)
        elif typ == t.Any:
            return {}
        elif isinstance(typ, EnumMeta):
            return self.add_schema(typ)
        elif next_extended and hasattr(typ, '__extended_to_json__'):
            return self._typ_to_schema(
                inspect.signature(typ.__extended_to_json__).return_annotation,
                next_extended=False,
            )
        elif hasattr(typ, '__to_json__'):
            return self._typ_to_schema(
                inspect.signature(typ.__to_json__).return_annotation,
                next_extended=False
            )
        else:
            raise AssertionError('Unknown type found: {}'.format(typ))

    @staticmethod
    def _get_routes_from_app(app: flask.Flask) -> t.Iterable[
        t.Tuple[t.Tuple[str, str], t.Sequence[t.Tuple[str, t.Sequence[str]]]]]:
        endpoints = []
        for rule in app.url_map.iter_rules():
            url_with_endpoint = (
                next(app.url_map.iter_rules(rule.endpoint)), rule.endpoint
            )
            if url_with_endpoint not in endpoints:
                endpoints.append(url_with_endpoint)
        endpoints = [e for _, e in endpoints]
        for endpoint in endpoints:
            methodrules: t.Dict[str, t.List[str]] = {}
            for rule in app.url_map.iter_rules(endpoint):
                methods = rule.methods.difference(['OPTIONS', 'HEAD'])
                path = rule.rule
                for method in methods:
                    if method in methodrules:
                        methodrules[method].append(path)
                    else:
                        methodrules[method] = [path]
            yield endpoint, list(methodrules.items())

    @staticmethod
    def _prepare_url(url: str, endpoint_func: t.Callable
                     ) -> t.Tuple[str, t.Sequence[t.Mapping]]:
        parameters = []
        url_parts = []
        for part in re.split(r'(<[^>]+>)', url):
            if not part.startswith('<'):
                url_parts.append(part)
                continue
            part = part[1:-1]
            schema = {}
            if ':' in part:
                typ, part = part.split(':')
                if typ == 'int':
                    schema = {'type': 'integer'}
                elif typ == 'uuid':
                    schema = {'type': 'string', 'format': 'uuid'}
                elif typ == 'path':
                    pass
                else:
                    raise AssertionError(
                        'Unknown url type encountered: {}'.format(typ)
                    )

            found = False
            doc = []
            regex = re.compile('^:param[^:]* {}:'.format(part))
            for line in (endpoint_func.__doc__ or '').splitlines():
                line = line.strip()
                if regex.search(line):
                    found = True
                    line = line.split(':', 2)[-1].strip()
                if found:
                    if line.startswith(':') or not line:
                        break
                    doc.append(line)
            if not doc:
                raise AssertionError(
                    'No documentation found for {} in {}.{}'.format(
                        part, endpoint_func.__module__,
                        endpoint_func.__qualname__
                    )
                )

            name = _to_camelcase(part)
            parameters.append({
                'name': name,
                'required': True,
                'in': 'path',
                'style': 'simple',
                'description': ' '.join(doc),
                'schema': schema,
            })
            url_parts.append('{' + name + '}')

        return ''.join(url_parts), parameters

    def _maybe_add_endpoint(
        self, endpoint_func: t.Callable, url: str, method: str
    ) -> None:
        try:
            operation_id, func = _SWAGGER_FUNCS[endpoint_func.__name__]
        except KeyError:
            return

        signature = inspect.signature(func)
        ret = signature.return_annotation
        responses = OrderedDict([
            (401, {'$ref': '#/components/responses/UnauthorizedError'}),
            (
                403,
                {'$ref': '#/components/responses/IncorrectPermissionsError'}
            ),
            ('5XX', {'$ref': '#/components/responses/UnknownError'}),
        ])
        if ret == cg_flask_helpers.EmptyResponse:
            responses[204] = {'description': 'An empty response'}
            responses.move_to_end(204, last=False)
        else:
            schema = self._typ_to_schema(ret, next_extended=False)
            responses[200] = {
                'description': 'The response if no errors occured',
                'content': {'application/json': {'schema': schema}}
            }
            responses.move_to_end(200, last=False)

        tags = self._find_and_add_tags(endpoint_func)
        result: t.Dict[str, t.Any] = {
            'responses': dict(responses),
            'summary': _first_docstring_line(endpoint_func.__doc__),
            'tags': tags,
            'operationId': f'{tags[0].lower()}_{operation_id}',
        }
        url, parameters = self._prepare_url(url, endpoint_func)

        if parameters:
            result['parameters'] = parameters

        if method.lower() not in ('get', 'delete'):
            with _schema_generator(self):
                try:
                    func(**signature.parameters)
                except _Schema as exc:
                    in_schema = exc.schema
                else:
                    assert False
                if 'anyOf' in in_schema:
                    schema_name = f'InputData{method.capitalize()}{_to_pascalcase(operation_id)}'
                    self._schemas[schema_name] = in_schema
                    in_schema = {'$ref': f'#/components/schemas/{schema_name}'}
            result['requestBody'] = {
                'content': {'application/json': {'schema': in_schema}},
            }

        self._paths[url][method.lower()] = result

    def collect_for_current_app(self) -> t.Mapping[str, t.Any]:
        for endpoint, rules in self._get_routes_from_app(flask.current_app):
            endpoint_func = flask.current_app.view_functions[endpoint]
            for method, urls in rules:
                for url in urls:
                    self._maybe_add_endpoint(endpoint_func, url, method)

        return {
            'openapi': '3.0.3',
            'info': {
                'title': 'CodeGrade', 'version': 'v1', 'license': {
                    'name': 'AGPL-3.0',
                    'url': 'http://www.gnu.org/licenses/agpl-3.0.html',
                }, 'contact': {
                    'url': 'https://codegrade.com',
                    'email': 'support@codegrade.com',
                }
            },
            'security': [{'bearerAuth': []}],
            'paths': dict(self._paths),
            'tags': list(self._tags.values()),
            'components': {
                'schemas': self._schemas,
                'securitySchemes': {
                    'bearerAuth': {
                        'type': 'http',
                        'scheme': 'bearer',
                        'bearerFormat': 'JWT',
                    },
                },
                'responses': {
                    'IncorrectPermissionsError': {
                        'description':
                            'You do not have the necessary permission to this',
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref': '#/components/schemas/BaseError'
                                },
                            },
                        },
                    },
                    'UnauthorizedError': {
                        'description': 'Access token is missing or invalid',
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref': '#/components/schemas/BaseError'
                                },
                            },
                        },
                    },
                    'UnknownError': {
                        'description': 'Something unknown error',
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref': '#/components/schemas/BaseError'
                                },
                            },
                        },
                    },
                },
            },
        }
