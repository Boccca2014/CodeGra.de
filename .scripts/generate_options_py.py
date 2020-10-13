#!/usr/bin/env python
import os
import typing as t
import datetime
import textwrap
import subprocess

import yaml

T = t.TypeVar('T')

CUR_DIR = os.path.dirname(__file__)

PREAMBLE = '''
"""This module defines all site settings used.

.. note:

    This module is automatically generated, don't edit manually.

SPDX-License-Identifier: AGPL-3.0-only
"""
# pylint: skip-file
import typing as t
from typing_extensions import Final
import dataclasses
import functools
import datetime
from typing_extensions import TypedDict

import cg_request_args as rqa
from cg_object_storage.types import FileSize

from . import models, PsefFlask, exceptions

import structlog
logger = structlog.get_logger()

_T = t.TypeVar('_T')
_CallableT = t.TypeVar('_CallableT', bound=t.Callable)

@dataclasses.dataclass
class _OptionCategory:
    name: str


@dataclasses.dataclass(frozen=True)
class Option(t.Generic[_T]):
    name: str = dataclasses.field(hash=True)
    default: _T = dataclasses.field(init=False, hash=False)
    default_obj: dataclasses.InitVar[object]
    parser: rqa._Parser[_T] = dataclasses.field(hash=False)

    def __post_init__(self, default_obj: object) -> None:
        default: _T = self.parser.try_parse(default_obj)
        object.__setattr__(self, 'default', default)

    @property
    def value(self) -> _T:
        return models.SiteSetting.get_option(self)

    def set_and_commit_value(self, new_value: _T) -> None:
        """Set and commit a value to the database.

        Don't use this method in normal code, it exists because it is very
        useful when testing.
        """
        models.db.session.add(models.SiteSetting.set_option(self, new_value))
        models.db.session.commit()

    class AsJSON(TypedDict):
        name: str
        default: t.Any
        value: t.Any

    def __to_json__(self) -> AsJSON:
        return {
            'name': self.name,
            'default': self.default,
            'value': self.value,
        }

    def ensure_enabled(self: 'Option[bool]') -> None:
        """Check if a certain option is enabled.

        :returns: Nothing.
        """
        if not self.value:
            logger.warning('Tried to use disabled feature', feature=self.name)
            raise exceptions.OptionException(self)

    def required(self: 'Option[bool]', f: _CallableT) -> _CallableT:
        """A decorator used to make sure the function decorated is only called
        with a certain feature enabled.

        :returns: The value of the decorated function if the given feature is
            enabled.
        """
        @functools.wraps(f)
        def __decorated_function(*args: t.Any, **kwargs: t.Any) -> t.Any:
            self.ensure_enabled()
            return f(*args, **kwargs)

        return t.cast(_CallableT, __decorated_function)
'''


def write_doc(f, doc, indent_num):
    indent = ' ' * indent_num + '#: '
    f.write(
        '\n'.join(
            textwrap.wrap(
                doc, 79, initial_indent=indent, subsequent_indent=indent
            )
        )
    )
    f.write('\n')


def get_options():
    with open(
        os.path.join(CUR_DIR, '..', 'seed_data', 'site_settings.yml'), 'r'
    ) as f:
        return yaml.safe_load(f)


def parse_type(opt):
    typ = opt.get('type')
    assert isinstance(typ, str)
    is_list = False
    if typ.endswith('[]'):
        is_list = True
        typ = typ[:-2]

    if typ == 'time-delta':
        parser = 'rqa.RichValue.TimeDelta'
        py_type = 'datetime.timedelta'
    elif typ == 'file-size':
        parser = 'rqa.RichValue.FileSize'
        py_type = 'FileSize'
    elif typ == 'integer':
        parser = 'rqa.SimpleValue.int'
        py_type = 'int'
    elif typ == 'string':
        parser = 'rqa.SimpleValue.str'
        py_type = 'str'
    elif typ == 'boolean':
        parser = 'rqa.SimpleValue.bool'
        py_type = 'bool'
    else:
        raise AssertionError(
            'Unknown type encountered at {}: {}'.format(opt['tag'], typ)
        )

    if is_list:
        return f'rqa.List({parser})', f't.Sequence[{py_type}]'
    return parser, py_type


def parse_option(opt):
    tag = opt['tag']
    assert isinstance(tag, str)

    parser, py_type = parse_type(opt)
    default = opt['default']

    frontend = opt.get('frontend', False)
    assert isinstance(frontend, bool)

    doc = opt['doc']

    return tag, parser, py_type, default, frontend, doc


def main():
    options = get_options()
    assert isinstance(options, list)
    all_opts = []
    frontend_opts = []
    seen_tags = set()

    for opt in options:
        tag, parser, py_type, default, frontend, doc = parse_option(opt)
        assert tag not in seen_tags, f'Duplicate setting found {tag}'
        seen_tags.add(tag)
        all_opts.append((
            tag,
            f"""
        Option(name={tag!r}, parser={parser}, default_obj={default!r},)
        """.strip(),
            py_type,
            doc,
        ))
        if frontend:
            frontend_opts.append(tag)

    out_file = os.path.join(CUR_DIR, '..', 'psef', 'site_settings.py')
    with open(out_file, 'w') as f:
        f.write(PREAMBLE)
        f.write('\n')

        f.write('class Opt:\n')
        for tag, opt, *_ in all_opts:
            f.write('    ')
            f.write(tag)
            f.write(': Final = ')
            f.write(opt)
            f.write('\n')

        f.write('    _FRONTEND_OPTS: t.Sequence[Option] = [')
        for tag, *_ in all_opts:
            if tag in frontend_opts:
                f.write(tag)
                f.write(',')
        f.write(']\n')

        f.write('    _ALL_OPTS: t.Sequence[Option] = [')
        f.write('*_FRONTEND_OPTS,')
        for tag, *_ in all_opts:
            if tag not in frontend_opts:
                f.write(tag)
                f.write(',')
        f.write(']\n')

        f.write('    class FrontendOptsAsJSON(TypedDict):\n')
        f.write(
            '        """The JSON representation of options visible to all users."""\n'
        )
        for tag, _, py_type, doc in all_opts:
            if tag not in frontend_opts:
                continue
            write_doc(f, doc, 8)
            f.write('        ')
            f.write(tag)
            f.write(': ')
            f.write(py_type)
            f.write('\n')

        f.write('    @classmethod\n')
        f.write('    def get_frontend_opts(cls) -> FrontendOptsAsJSON:\n')
        f.write(
            '        lookup: t.Any = models.SiteSetting.get_options(cls._FRONTEND_OPTS)\n'
        )
        f.write('        return {\n')
        for tag, *_ in all_opts:
            if tag in frontend_opts:
                f.write(f"'{tag}': lookup[cls.{tag}],")
        f.write('}\n')

        f.write('    class AllOptsAsJSON(FrontendOptsAsJSON):\n')
        f.write('        """The JSON representation of all options."""\n')
        for tag, _, py_type, doc in all_opts:
            if tag in frontend_opts:
                continue
            write_doc(f, doc, 8)
            f.write('        ')
            f.write(tag)
            f.write(': ')
            f.write(py_type)
            f.write('\n')
        f.write(
            '    AllOptsAsJSON.__cg_extends__ = FrontendOptsAsJSON  # type: ignore\n'
        )

        f.write('    @classmethod\n')
        f.write('    def get_all_opts(cls) -> AllOptsAsJSON:\n')
        f.write(
            '        lookup: t.Any = models.SiteSetting.get_options(cls._ALL_OPTS)\n'
        )
        f.write('        return {\n')
        for tag, *_ in all_opts:
            f.write(f"'{tag}': lookup[cls.{tag}],")
        f.write('}\n')

        f.write('OPTIONS_INPUT_PARSER = rqa.Lazy(lambda: ')
        for idx, (tag, *_) in enumerate(all_opts):
            f.write('    (rqa.FixedMapping(\n ')
            f.write(
                f"        rqa.RequiredArgument('name', rqa.StringEnum({tag!r}), '',), \n"
            )
            f.write(
                f"        rqa.RequiredArgument('value', rqa.Nullable(Opt.{tag}.parser), '',), \n"
            )
            f.write(f"    ).add_tag('opt', Opt.{tag}))")
            if idx + 1 < len(all_opts):
                f.write(' | ')
            f.write('\n')
        f.write(").as_schema('SiteSettingInputAsJSON')\n")

        f.write('def init_app(_: PsefFlask) -> None:\n')
        f.write('    pass')

    subprocess.run(['isort', out_file])
    subprocess.run(['yapf', '-i', out_file])


if __name__ == '__main__':
    main()
