import re
import sys
import enum
import typing as t
import inspect
import datetime
import collections

import yaml
import flask
import sphinx.pycode
from typing_extensions import Literal, TypedDict

import psef
import cg_json
import cg_flask_helpers
from cg_dt_utils import DatetimeWithTimezone

from . import _SWAGGER_FUNCS, _Schema, _schema_generator, _type_to_open_api

_PARSED_MODULES = {}


def _first_docstring_line(doc: str) -> str:
    first = doc.split('\n\n')[0]
    return ' '.join(line.strip() for line in first.splitlines())


def _get_tag_description(endpoint: t.Callable) -> str:
    return _first_docstring_line(sys.modules[endpoint.__module__].__doc__)


def _to_camelcase(string: str) -> str:
    first, *others = string.split('_')
    return ''.join([first.lower(), *map(str.title, others)])


def _comments_of(typ: t.Type, field: str) -> str:
    if typ.__module__ not in _PARSED_MODULES:
        with open(typ.__module__.replace('.', '/') + '.py', 'r') as code:
            parser = sphinx.pycode.parser.Parser(code.read())
            parser.parse()
            _PARSED_MODULES[typ.__module__] = parser

    parsed = _PARSED_MODULES[typ.__module__]
    if typ.__name__ == 'AsExtendedJSON':
        try:
            return parsed.comments[(
                typ.__qualname__.replace('.AsExtendedJSON', '.AsJSON'), field
            )]
        except KeyError:
            return parsed.comments[(typ.__qualname__, field)]
    return parsed.comments[(typ.__qualname__, field)]


def _find_tags(endpoint: t.Callable) -> t.List[str]:
    for line in endpoint.__doc__.splitlines():
        if '.. :quickref: ' in line:
            return [line.split('.. :quickref: ', 1)[-1].split(';', 1)[0]]
    assert False


def _prepare_url(url, endpoint_func):
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
        for line in endpoint_func.__doc__.splitlines():
            line = line.strip()
            if regex.search(line):
                found = True
                line = line.split(':', 2)[-1].strip()
            if found:
                if line.startswith(':') or not line:
                    break
                doc.append(line)
        if not doc:
            raise AssertionError('No documentation found for {}'.format(part))

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


def _typ_to_schema(
    typ: t.Type, depth: int, next_extended: bool, todo: t.List[t.Type]
) -> t.Mapping[str, t.Any]:
    if isinstance(typ, t.ForwardRef):
        typ = typ._evaluate({'psef': psef}, {})

    origin = getattr(typ, '__origin__', None)

    if isinstance(typ, type(TypedDict)):
        if depth == 0:
            properties = {}
            for prop, prop_type in typ.__annotations__.items():
                prop_dct = _typ_to_schema(prop_type, depth + 1, False, todo)
                if '$ref' in prop_dct:
                    prop_dct = {'allOf': [prop_dct]}
                properties[prop] = {
                    **prop_dct,
                    'description': _comments_of(typ, prop).replace('\n', ' '),
                }

            # We know that every ``AsExtendedJSON`` extends the normal
            # ``AsJSON``, however this is not save in the object for some
            # reason, so we simply retrieve the ``AsJSON`` class and remove all
            # properties that one has from our found properties.
            if typ.__name__ == 'AsExtendedJSON':
                base_as_json = getattr(
                    sys.modules[typ.__module__],
                    typ.__qualname__.split('.')[0]
                ).AsJSON
                base = _typ_to_schema(base_as_json, 1, False, todo)
                extra_items = {
                    'type': 'object',
                    'properties': {
                        k: v
                        for k, v in properties.items()
                        if k not in base_as_json.__annotations__
                    },
                }
                return {'allOf': [base, extra_items]}

            return {
                'type': 'object',
                'properties': properties,
            }
        else:
            todo.append(typ)
            return {'$ref': f'#/components/schemas/{typ.__qualname__}'}
    elif typ in (int, str, bool, float):
        return {'type': _type_to_open_api(typ)}
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
    elif origin == list or origin == collections.abc.Sequence:
        return {
            'type': 'array',
            'items':
                _typ_to_schema(
                    typ.__args__[0], depth + 1, next_extended, todo
                ),
        }
    elif origin == t.Union:
        nullable = False
        if type(None) in typ.__args__:
            nullable = True
        anyOf = [
            _typ_to_schema(arg, depth + 1, next_extended, todo)
            for arg in typ.__args__ if arg != type(None)
        ]
        if len(anyOf) > 1:
            return {
                'anyOf': anyOf,
                'nullable': nullable,
            }
        elif '$ref' in anyOf[0]:
            return {
                'allOf': anyOf,
                'nullable': True,
            }
        else:
            return {**anyOf[0], 'nullable': nullable}
    elif origin == cg_json.JSONResponse:
        return _typ_to_schema(typ.__args__[0], depth + 0, False, todo)
    elif origin == cg_json.ExtendedJSONResponse:
        return _typ_to_schema(typ.__args__[0], depth, True, todo)
    elif typ == t.Any:
        return {}
    elif isinstance(typ, type) and psef.models.Base in typ.__mro__:
        if next_extended:
            return _typ_to_schema(typ.AsExtendedJSON, depth + 1, False, todo)
        else:
            return _typ_to_schema(typ.AsJSON, depth + 1, False, todo)

    elif isinstance(typ, type) and enum.Enum in typ.__mro__:
        return {'enum': [e.name for e in typ]}
    else:
        breakpoint()


def _typs_to_schema(todo: t.List[t.Type]) -> t.Mapping[str, t.Any]:

    done = set()
    res = {}

    while todo:
        typ = todo.pop()
        if typ.__qualname__ in done:
            continue
        done.add(typ.__qualname__)
        res[typ.__qualname__] = _typ_to_schema(typ, 0, False, todo)

    return res


def collect_swagger() -> t.Any:

    swagger_lookup = {f.__name__: f for f in _SWAGGER_FUNCS}

    def get_routes(app, endpoint=None, order=None):
        endpoints = []
        for rule in app.url_map.iter_rules(endpoint):
            url_with_endpoint = (
                next(app.url_map.iter_rules(rule.endpoint)), rule.endpoint
            )
            if url_with_endpoint not in endpoints:
                endpoints.append(url_with_endpoint)
        if order == 'path':
            endpoints.sort()
        endpoints = [e for _, e in endpoints]
        for endpoint in endpoints:
            methodrules = {}
            for rule in app.url_map.iter_rules(endpoint):
                methods = rule.methods.difference(['OPTIONS', 'HEAD'])
                path = rule.rule
                for method in methods:
                    if method in methodrules:
                        methodrules[method].append(path)
                    else:
                        methodrules[method] = [path]
            yield endpoint, list(methodrules.items())

    paths = collections.defaultdict(dict)

    schemas_todo = []
    found_tags = {}

    for endpoint, rules in get_routes(flask.current_app):
        endpoint_func = flask.current_app.view_functions[endpoint]
        func = swagger_lookup.get(endpoint_func.__name__)
        if func is None:
            continue

        signature = inspect.signature(func)

        for method, urls in rules:
            for url in urls:
                ret = signature.return_annotation
                if ret == cg_flask_helpers.EmptyResponse:
                    responses = {'204': {'description': 'An empty response'}}
                else:
                    responses = {
                        'default': {
                            'description': 'The response if no errors occured',
                            'content': {
                                'application/json': {
                                    'schema':
                                        _typ_to_schema(
                                            ret, 1, False, schemas_todo
                                        )
                                }
                            }
                        }
                    }

                tags = _find_tags(endpoint_func)
                result = {
                    'responses': responses,
                    'summary': _first_docstring_line(endpoint_func.__doc__),
                    'tags': tags,
                }
                for tag in tags:
                    if tag not in found_tags:
                        found_tags[tag] = {
                            'name': tag,
                            'description': _get_tag_description(endpoint_func),
                        }
                url, parameters = _prepare_url(url, endpoint_func)

                if parameters:
                    result['parameters'] = parameters

                if method.lower() not in ('get', 'delete'):
                    with _schema_generator():
                        try:
                            func(**signature.parameters)
                        except _Schema as exc:
                            in_schema = exc.schema
                        else:
                            assert False
                    result['requestBody'] = {
                        'content': {'application/json': {'schema': in_schema}},
                    }

                paths[url][method.lower()] = result

    schemas = _typs_to_schema(schemas_todo)

    with open('swagger.rst', 'w') as f:
        yaml.dump(
            {
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
                'paths': dict(paths),
                'tags': list(found_tags.values()),
                'components': {'schemas': schemas},
            },
            stream=f,
        )
