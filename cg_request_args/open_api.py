"""This module contains code to convert flask applications that use
``cg_request_args`` to Open API schemas.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import re
import sys
import uuid
import typing as t
import inspect
import datetime
import contextlib
import collections
from enum import Enum, EnumMeta
from collections import OrderedDict, defaultdict

import flask
import sphinx.pycode
from typing_extensions import Literal, TypedDict

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
}


@contextlib.contextmanager
def _disabled_auth() -> t.Generator[None, None, None]:
    try:
        orig = psef.auth.ensure_logged_in
        psef.auth.ensure_logged_in = lambda: None  # type: ignore
        yield
    finally:
        psef.auth.ensure_logged_in = orig


def _to_pascalcase(string: str) -> str:
    return ''.join(map(str.title, string.split('_')))


def _to_camelcase(string: str) -> str:
    first, *others = string.split('_')
    return ''.join([first.lower(), *map(str.title, others)])


def _clean_comment(comment: str) -> str:
    return _doc_without_sphinx(comment)


def _doc_without_sphinx(doc: str) -> str:
    res = []
    doc = inspect.cleandoc(doc)
    in_sphinx = False

    for line in doc.splitlines():
        if line.startswith('.. :'):
            continue
        note_match = re.match(r'^\.\. [^:]+:: *(.*)', line)
        if note_match is not None:
            line = note_match.group(1).strip()
            if not line:
                continue

        if line.startswith(':'):
            in_sphinx = True
            continue
        if in_sphinx and line.startswith(' '):
            continue
        in_sphinx = False
        res.append(line.strip())

    return '\n'.join(res)


def _first_docstring_line(doc: t.Optional[str]) -> str:
    first = (doc or '').split('\n\n')[0]
    return _clean_comment(first)


class _Tag(TypedDict):
    name: str
    description: str


class OpenAPISchema:
    """The class representing an Open API schema.

    Instances of this class can be used to convert a flask application to Open
    API schemas.
    """

    def __init__(
        self, type_globals: t.Dict[str, t.Any], no_pandoc: bool = False
    ) -> None:
        self._paths: t.Dict[str, t.Dict[str, t.Mapping]] = defaultdict(dict)
        self._schemas: t.Dict[str, t.Mapping] = {}
        self._type_globals = type_globals
        self._parsed_modules: t.Dict[str, sphinx.pycode.parser.Parser] = {}
        self._tags: t.Dict[str, _Tag] = {}
        self._no_pandoc = no_pandoc
        self._set_initial_schemas()

    def expand_anyof(self, anyof_lst: t.Iterable[t.Mapping[str, t.Any]]
                     ) -> t.List[t.Mapping[str, t.Any]]:
        res = []
        for opt in anyof_lst:
            if 'anyOf' in opt:
                res.extend(self.expand_anyof(opt['anyOf']))
            else:
                res.append(opt)
        return res

    def make_comment(self, comment: str) -> str:
        """Convert the given string to a description for Open API.

        The comment is converted to markdown, and any newlines are removed.
        """
        comment = _doc_without_sphinx(comment)
        if self._no_pandoc:
            return comment.strip()
        else:
            # This module is only needed when generating the open API with
            # swagger transforms enabled. However as we don't want to always
            # install it (as it is not needed for normal deploys) pylint and
            # isort will complain if we import it toplevel.
            import pypandoc  # pylint: disable=import-error,import-outside-toplevel
            res = pypandoc.convert_text(
                comment, 'gfm', format='rst', extra_args=['--wrap=none']
            ).strip()
            return re.sub(r'`[^`]*\.([^.]+)`', r'`\1`', res)

    def _set_initial_schemas(self) -> None:
        initial = {
            'BaseError': {
                'type': 'object',
                'x-is-error': True,
                'properties': {
                    'message': {'type': 'string'},
                    'description': {'type': 'string'},
                    'code': self.add_schema(psef.errors.APICodes),
                    'request_id': {
                        'type': 'string',
                        'format': 'uuid',
                        'description':
                            self.make_comment(
                                """
                                            The id of the request that went
                                            wrong. Please include this id when
                                            reporting bugs.
                                            """
                            ),
                    },
                },
            },
        }
        self._schemas.update(initial)

    @staticmethod
    def _get_schema_name(typ: t.Type) -> str:
        return typ.__qualname__

    def _maybe_add_tag(self, tag: str, func: t.Callable) -> None:
        if tag in self._tags:
            return
        description = self.make_comment(
            _first_docstring_line(sys.modules[func.__module__ or ''].__doc__)
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
                t.cast(t.Type, typ._evaluate(self._type_globals, {}))  # pylint: disable=protected-access
            )
        return typ

    def _comments_of(self, typ: t.Type, field: str) -> str:
        if typ.__module__ not in self._parsed_modules:
            base = os.path.join(os.path.dirname(__file__), '..')
            rel_path = f'{typ.__module__.replace(".", "/")}.py'
            with open(os.path.join(base, rel_path), 'r') as code:
                parser = sphinx.pycode.parser.Parser(code.read())
                parser.parse()
                self._parsed_modules[typ.__module__] = parser

        parsed = self._parsed_modules[typ.__module__]
        if typ.__name__ == 'AsExtendedJSON':
            extends = getattr(
                sys.modules[typ.__module__],
                typ.__qualname__.split('.')[0]
            ).AsJSON
        else:
            extends = getattr(typ, '__cg_extends__', None)

        try:
            res = parsed.comments[(typ.__qualname__, field)]
        except KeyError:
            while extends:
                try:
                    res = parsed.comments[(extends.__qualname__, field)]
                except KeyError:
                    extends = getattr(extends, '__cg_extends__', None)
                else:
                    break
            else:
                raise

        return self.make_comment(res)

    @staticmethod
    def simple_type_to_open_api_type(
        typ: t.Type[t.Union[str, int, float, bool, None]]
    ) -> str:
        """Convert the given type to an Open API type.
        """
        return _SIMPLE_TYPE_NAME_LOOKUP[typ]

    def _will_use(self, _typ: t.Type, maybe_uses: t.Iterable[t.Type]) -> bool:  # pylint: disable=too-many-branches,too-many-return-statements
        typ = self._maybe_resolve_forward(_typ)
        if not maybe_uses:
            return False

        origin = getattr(typ, '__origin__', None)

        if typ in maybe_uses:
            return True
        if isinstance(typ, type(TypedDict)):
            return any(
                self._will_use(val, maybe_uses)
                for val in t.cast(t.Any, typ).__annotations__.values()
            )
        elif typ in (int, str, bool, float):
            return False
        elif typ == DatetimeWithTimezone:
            return False
        elif typ == datetime.timedelta:
            return False
        elif origin in (list, collections.abc.Sequence):
            return self._will_use(typ.__args__[0], maybe_uses)
        elif origin == t.Union:
            return any(self._will_use(val, maybe_uses) for val in typ.__args__)
        elif origin == cg_json.JSONResponse:
            return self._will_use(typ.__args__[0], maybe_uses)
        elif origin == cg_json.ExtendedJSONResponse:
            return self._will_use(typ.__args__[0], maybe_uses)
        elif origin == cg_json.MultipleExtendedJSONResponse:
            return self._will_use(typ.__args__[0], maybe_uses)
        elif typ == t.Any:
            return False
        elif isinstance(typ, EnumMeta):
            return False
        elif hasattr(typ, '__extended_to_json__'):
            return self._will_use(
                inspect.signature(typ.__extended_to_json__).return_annotation,
                maybe_uses,
            )
        elif hasattr(typ, '__to_json__'):
            return self._will_use(
                inspect.signature(typ.__to_json__).return_annotation,
                maybe_uses,
            )
        elif origin in (dict, collections.abc.Mapping):
            _, value_type = typ.__args__
            return self._will_use(value_type, maybe_uses)
        elif origin == Literal:
            return False
        elif typ == type(None):
            return False
        else:
            raise AssertionError("Unknown type encountered")

    def add_schema(  # pylint: disable=too-many-branches
        self,
        _typ: t.Type,
        force_inline: bool = False,
        done: 'OrderedDict[t.Type, int]' = None,
        do_extended: t.Collection[t.Type] = tuple()
    ) -> t.Mapping[str, str]:
        """Add a schema for ``_typ`` to the current Open API and get a
        reference to it.
        """
        _typ = self._maybe_resolve_forward(_typ)
        schema_name = self._get_schema_name(_typ)

        if force_inline:
            force_inline = self._will_use(_typ, do_extended)

        if done is None:
            done = collections.OrderedDict([(_typ, True)])

        if schema_name in self._schemas and not (force_inline and do_extended):
            result = self._schemas[schema_name]
            force_inline = False
        elif isinstance(_typ, type(TypedDict)):
            if not force_inline:
                # Just so that recursion will refer to this schema.
                self._schemas[schema_name] = {'invalid': 'PLACEHOLDER'}

            typ: t.Any = _typ
            properties = {}

            for prop, prop_type in typ.__annotations__.items():
                prop_dct = self._typ_to_schema(
                    prop_type,
                    do_extended=do_extended,
                    inline=force_inline,
                    done=done
                )
                if '$ref' in prop_dct:
                    prop_dct = {'oneOf': [prop_dct]}
                properties[prop] = {
                    **prop_dct,
                    'description':
                        self.make_comment(
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

            if base_as_json is None:
                result = {
                    'type': 'object',
                    'properties': properties,
                    'required': [
                        p for p in typ.__annotations__.keys()
                        if p in typ.__required_keys__
                    ],
                    'description': self.make_comment(typ.__doc__ or ''),
                }
                if not result['required']:
                    result.pop('required')
            else:
                base = self.add_schema(
                    base_as_json, done=done, do_extended=do_extended
                )
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
                if not extra_items['required']:
                    extra_items.pop('required')
                result = {
                    'allOf': [base, extra_items],
                    'description': self.make_comment(typ.__doc__ or ''),
                }
        elif isinstance(_typ, EnumMeta):
            enum: t.Type[Enum] = _typ
            result = {
                'type': 'string',
                'enum': [e.name for e in enum],
                'description': self.make_comment(enum.__doc__ or ''),
            }
        else:
            raise AssertionError('Cannot make scheme for {}'.format(_typ))

        if force_inline:
            return result
        return self.add_as_schema(schema_name, result)

    def add_as_schema(self, schema_name: str, result: t.Mapping[str, t.Any]) -> t.Mapping[str, t.Any]:
        self._schemas[schema_name] = result
        return {'$ref': f'#/components/schemas/{schema_name}'}

    def _typ_to_schema(  # pylint: disable=too-many-return-statements,too-many-branches
        self,
        typ: t.Type,
        do_extended: t.Collection[t.Type],
        inline: bool,
        done: 'OrderedDict[t.Type, int]',
    ) -> t.Mapping[str, t.Any]:
        typ = self._maybe_resolve_forward(typ)
        if inline and done.get(typ, 0) > 0:
            raise AssertionError(
                'Recursion detected: {}'.format(
                    '.'.join(map(str, done.keys()))
                )
            )

        done.setdefault(typ, 0)
        done[typ] += 1

        origin = getattr(typ, '__origin__', None)

        try:
            if isinstance(typ, type(TypedDict)):
                return self.add_schema(
                    typ,
                    force_inline=inline,
                    done=done,
                    do_extended=do_extended
                )
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
                            typ.__args__[0],
                            do_extended=do_extended,
                            inline=inline,
                            done=done,
                        ),
                }
            elif origin == t.Union:
                nullable = False
                if type(None) in typ.__args__:
                    nullable = True
                any_of = self.expand_anyof(
                    self._typ_to_schema(
                        arg, do_extended=do_extended, inline=inline, done=done
                    ) for arg in typ.__args__ if arg != type(None)
                )
                if len(any_of) > 1:
                    return {
                        'anyOf': any_of,
                        'nullable': nullable,
                    }
                elif '$ref' in any_of[0]:
                    return {
                        'oneOf': any_of,
                        'nullable': True,
                    }
                else:
                    return {**any_of[0], 'nullable': nullable}
            elif origin == cg_json.JSONResponse:
                return self._typ_to_schema(
                    typ.__args__[0],
                    do_extended=tuple(),
                    inline=inline,
                    done=done,
                )
            elif origin == cg_json.ExtendedJSONResponse:
                next_extended = typ.__args__[0]

                if getattr(next_extended, '__origin__',
                           None) in (list, collections.abc.Sequence):
                    next_extended = next_extended.__args__[0]

                assert hasattr(next_extended, '__extended_to_json__')

                return self._typ_to_schema(
                    typ.__args__[0],
                    do_extended=(next_extended, ),
                    inline=inline,
                    done=done,
                )
            elif origin == cg_json.MultipleExtendedJSONResponse:
                if getattr(typ.__args__[1], '__origin__', None) == t.Union:
                    do_extended = typ.__args__[1].__args__
                else:
                    do_extended = (typ.__args__[1], )

                return self._typ_to_schema(
                    typ.__args__[0],
                    do_extended=do_extended,
                    inline=True,
                    done=done,
                )
            elif typ == t.Any:
                return {'type': 'object'}
            elif typ == uuid.UUID:
                return {'type': 'string', 'format': 'uuid'}
            elif isinstance(typ, EnumMeta):
                return self.add_schema(typ, force_inline=inline)
            elif typ in do_extended and hasattr(typ, '__extended_to_json__'):
                # We don't support recursion anyway for extended_to_json so we
                # never need to do this extended.
                next_do_extended = [ext for ext in do_extended if ext != typ]
                return self._typ_to_schema(
                    inspect.signature(typ.__extended_to_json__
                                      ).return_annotation,
                    do_extended=next_do_extended,
                    inline=bool(inline and next_do_extended),
                    done=done,
                )
            elif hasattr(typ, '__to_json__') or hasattr(origin, '__to_json__'):
                return self._typ_to_schema(
                    inspect.signature((origin or
                                       typ).__to_json__).return_annotation,
                    do_extended=do_extended,
                    inline=inline,
                    done=done,
                )
            elif origin in (dict, collections.abc.Mapping):
                _, value_type = typ.__args__
                return {
                    'type': 'object',
                    'additionalProperties':
                        self._typ_to_schema(
                            value_type,
                            do_extended=do_extended,
                            inline=inline,
                            done=done,
                        ),
                }
            elif origin == Literal:
                return {
                    'type': 'string',
                    'enum': list(typ.__args__),
                }
            elif str(typ).startswith('<function NewType.<locals>.new_type'):
                return self._typ_to_schema(
                    typ.__supertype__,
                    do_extended=do_extended,
                    inline=inline,
                    done=done,
                )
            else:
                raise AssertionError(
                    'Unknown type found: {} (origin: {}) (path: {})'.format(
                        typ, origin, '.'.join(map(str, done.keys()))
                    )
                )
        finally:
            if done[typ] == 1:
                done.pop(typ)
            else:
                done[typ] -= 1

    @staticmethod
    def _get_routes_from_app(app: flask.Flask) -> t.Iterable[
        t.Tuple[t.Tuple[str, str], t.Sequence[t.Tuple[str, t.Sequence[str]]]]]:
        endpoints = []
        for rule in app.url_map.iter_rules():
            url, endpoint = (
                next(app.url_map.iter_rules(rule.endpoint), None),
                rule.endpoint
            )
            if url is None:
                continue
            url_with_endpoint = (url, endpoint)
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

    def _prepare_url(self, url: str, endpoint_func: t.Callable
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
                'description': self.make_comment('\n'.join(doc)),
                'schema': schema,
            })
            url_parts.append('{' + name + '}')

        return ''.join(url_parts), parameters

    def _maybe_add_endpoint(
        self, endpoint_func: t.Callable, url: str, method: str
    ) -> None:
        try:
            swagger_func = _SWAGGER_FUNCS[endpoint_func.__name__]
        except KeyError:
            return

        operation_id = swagger_func.operation_name
        func = swagger_func.func

        signature = inspect.signature(func)
        ret = signature.return_annotation
        tags = self._find_and_add_tags(endpoint_func)

        responses: OrderedDict = OrderedDict([
            (400, {'$ref': '#/components/responses/IncorrectParametersError'}),
            (409, {'$ref': '#/components/responses/IncorrectParametersError'}),
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
            schema = self._typ_to_schema(
                ret, do_extended=tuple(), inline=False, done=OrderedDict()
            )
            if schema.get('type') == 'object':
                out_schema_name = (
                    f'ResultData{method.capitalize()}'
                    f'{tags[0]}'
                    f'{_to_pascalcase(operation_id)}'
                )
                self._schemas[out_schema_name] = schema
                schema = {'$ref': f'#/components/schemas/{out_schema_name}'}
            responses[200] = {
                'description': 'The response if no errors occured',
                'content': {'application/json': {'schema': schema}}
            }
            responses.move_to_end(200, last=False)

        result: t.Dict[str, t.Any] = {
            'responses': dict(responses),
            'summary': ' '.join(o.title() for o in operation_id.split('_')),
            'description': self.make_comment(endpoint_func.__doc__ or ''),
            'tags': tags,
            'operationId': f'{tags[0].lower()}_{operation_id}',
        }
        url, parameters = self._prepare_url(url, endpoint_func)

        if parameters:
            result['parameters'] = parameters

        if (
            method.lower() not in ('get', 'delete') and
            not swagger_func.no_data
        ):
            with _schema_generator(self), _disabled_auth():
                try:
                    func(**signature.parameters)
                except _Schema as exc:
                    in_schema = exc.schema
                    in_type = exc.typ
                else:
                    assert False

                if in_type == 'multipart/form-data' and '$ref' not in in_schema[
                    'properties']['json']:
                    inner_schema_name = f'Json{_to_pascalcase(operation_id)}{tags[0]}'
                    self._schemas[inner_schema_name] = in_schema['properties'
                                                                 ]['json']
                    in_schema['properties']['json'] = {
                        '$ref': f'#/components/schemas/{inner_schema_name}'
                    }

                if '$ref' not in in_schema:
                    schema_name = f'{_to_pascalcase(operation_id)}{tags[0]}Data'
                    self._schemas[schema_name] = in_schema
                    in_schema = {'$ref': f'#/components/schemas/{schema_name}'}

            body = {
                'content': {in_type: {'schema': in_schema}},
                'required': True,
            }
            result['requestBody'] = body

        if getattr(func, 'login_required_route', False):
            result['security'] = [{'bearerAuth': []}]

        self._paths[url][method.lower()] = result

    def collect_for_current_app(self) -> t.Mapping[str, t.Any]:
        """Collect the Open API schema for the current flask app.
        """
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
            'servers': [{
                'url': 'https://{instance}.codegra.de',
                'variables': {
                    'instance': {
                        'description': 'The instance you are on',
                        'default': 'app',
                    },
                },
            }],
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
                    'IncorrectParametersError': {
                        'description': 'Some parameters were wrong',
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref': '#/components/schemas/BaseError'
                                },
                            },
                        },
                    },
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
