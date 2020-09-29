import os
import typing as t
import datetime
import textwrap
import subprocess

import yaml

T = t.TypeVar('T')

CUR_DIR = os.path.dirname(__file__)

PARSERS = """
def parse_integer(value: str) -> int:
    return int(value)


def parse_string(value: str) -> str:
    assert value, 'The value should not be empty'
    return value


def parse_timedelta(value: str) -> datetime.timedelta:
    number, opt = int(value[:-1]), value[-1]
    if opt == 's':
        return datetime.timedelta(seconds=number)
    elif opt == 'm':
        return datetime.timedelta(minutes=number)
    elif opt == 'h':
        return datetime.timedelta(hours=number)
    elif opt == 'd':
        return datetime.timedelta(days=number)
    raise AssertionError('Unknown prefix: {}'.format(opt))

_KB = 1 << 10
_MB = _KB << 10
_GB = _MB << 10

def parse_size(value: str) -> int:
    number, unit = int(value[:-2]), value[-2:]
    if unit == 'kb':
        return number * _KB
    elif unit == 'mb':
        return number * _MB
    elif unit == 'gb':
        return number * _GB
    else:
        raise AssertionError('Unknown limit encountered: {}'.format(unit))


def parse_array(parse_item: t.Callable[[str], '_T']
               ) -> '_Parser[t.Any]':

    def __inner(value: str) -> t.Sequence['_T']:
        res = tuple(parse_item(item.strip()) for item in value.split(','))
        assert res, 'The list should at least have one item'
        return res

    return __inner
"""

# The functions are also needed to parse the default values
exec(PARSERS)

PREAMBLE = f"""
import typing as t
import datetime
from typing_extensions import Literal, Protocol
import dataclasses

from cg_sqlalchemy_helpers import JSONB
from cg_sqlalchemy_helpers.mixins import IdMixin, TimestampMixin
from cg_sqlalchemy_helpers.types import ColumnProxy
from . import db, Base
from cg_cache.intra_request import cache_within_request

_T = t.TypeVar('_T', bool, datetime.timedelta, int, str, covariant=True)
T = t.TypeVar('T', bool, datetime.timedelta, int, t.Sequence[datetime.timedelta], str, covariant=True)


@dataclasses.dataclass
class _OptionCategory:
    name: str


# Work around for https://github.com/python/mypy/issues/5485
class _Parser(Protocol[T]):
    def __call__(self, value: str) -> T:
        ...


@dataclasses.dataclass
class _Option(t.Generic[T]):
    name: str
    default: T
    doc: str
    parser: _Parser[T]
    security: bool
    stored_parsed: bool
    category: t.Optional[_OptionCategory] = None


{PARSERS}
"""


def get_options():
    with open(
        os.path.join(CUR_DIR, '..', 'seed_data', 'admin_settings.yaml'), 'r'
    ) as f:
        return yaml.safe_load(f)


def parse_type(opt):
    typ = opt.get('type')
    assert isinstance(typ, str)
    is_list = False
    if typ.endswith('[]'):
        is_list = True
        typ = typ[:-2]

    if typ == 'duration':
        py_type = 'datetime.timedelta'
        parser = 'parse_timedelta'
        can_store = False
    elif typ == 'size':
        py_type = 'int'
        parser =  'parse_size'
        can_store = True
    elif typ == 'integer':
        py_type = 'int'
        parser =  'parse_integer'
        can_store = True
    elif typ == 'string':
        py_type = 'str'
        parser = 'parse_string'
        can_store = True
    else:
        raise AssertionError(
            'Unknown type encountered at {}: {}'.format(opt['tag'], typ)
        )

    if is_list:
        return f't.Sequence[{py_type}]', f'parse_array({parser})', can_store
    return py_type, parser, can_store


def parse_option(opt):
    tag = opt['tag']
    assert isinstance(tag, str)

    doc = opt['doc']
    assert isinstance(doc, str)

    security = opt.get('security', False)
    assert isinstance(security, bool)

    py_type, parser, can_store = parse_type(opt)
    default = eval(parser)(opt['default'])

    return tag, doc, security, py_type, parser, can_store, default


def main():
    options = get_options()
    assert isinstance(options, list)
    all_tags = []
    all_opts = []
    for opt in options:
        tag, doc, security, py_type, parser, can_store, default = parse_option(opt)
        all_opts.append(
            f"""
        _Option(name={tag!r}, doc=({doc!r}), parser={parser}, security={security!r}, default={default!r}, stored_parsed={can_store!r})
        """.strip()
        )
        all_tags.append((tag, py_type))

    out_file = os.path.join(
        CUR_DIR, '..', 'psef', 'models', 'admin_settings.py'
    )
    with open(out_file, 'w') as f:
        f.write(PREAMBLE)
        f.write('\n')
        f.write('_ALL_OPTIONS: t.Sequence[_Option] = (\n')
        for opt in all_opts:
            f.write(opt)
            f.write(',\n')
        f.write(')\n\n')
        f.write('_OPTIONS_LOOKUP = {o.name: o for o in _ALL_OPTIONS}\n')

        f.write(textwrap.dedent("""
        class AdminSetting(Base, TimestampMixin):
            _name = db.Column('name', db.Unicode, nullable=False, primary_key=True)
            _value: ColumnProxy[t.Any]  = db.Column('value', JSONB, nullable=False)
        """))

        for tag, py_type in all_tags:
            f.write('    @t.overload\n')
            f.write('    @classmethod\n')
            f.write(
                f'    def get_option(cls, name: Literal[{tag!r}]) -> {py_type}: ...\n'
            )

        f.write(textwrap.dedent("""
            @classmethod
            @cache_within_request
            def get_option(cls, name: str) -> t.Any:
                opt = _OPTIONS_LOOKUP[name]
                self = cls.query.get(name)
                if self is None:
                    return opt.default
                elif opt.stored_parsed:
                    return self._value
                return opt.parser(self._value)

        class AdminSettingHistory(Base, TimestampMixin, IdMixin):
            setting_name = db.Column(
                'name',
                db.Unicode,
                db.ForeignKey('admin_setting.name'),
                nullable=False,
            )
            old_value = db.Column('old_value', JSONB, nullable=True)
            new_value = db.Column('new_value', JSONB, nullable=False)
        """))

    subprocess.run(['isort', out_file])
    subprocess.run(['yapf', '-i', out_file])


if __name__ == '__main__':
    main()
