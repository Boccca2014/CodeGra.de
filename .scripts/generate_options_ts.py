#!/usr/bin/env python
import os
import json
import typing as t
import datetime
import textwrap
import subprocess
import dataclasses

import yaml

import psef
import cg_json
import cg_request_args as rqa
import generate_options_py

CUR_DIR = os.path.dirname(__file__)


@dataclasses.dataclass(frozen=True)
class Option:
    tag: str
    ts_type: str
    is_list: bool
    default: t.Any
    ts_format: str
    frontend: str
    doc: str
    group: str

    def write_type(self, f):
        if self.is_list:
            f.write('readonly ')
        f.write(self.ts_type)
        if self.is_list:
            f.write('[]')

    def write_doc(self, f, indent_num):
        indent = ' ' * indent_num + '// '
        f.write(
            '\n'.join(
                textwrap.wrap(
                    self.doc,
                    79,
                    initial_indent=indent,
                    subsequent_indent=indent
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

    ts_format = ''
    if typ == 'time-delta':
        ts_type = 'number'
        ts_format = 'timedelta'
    elif typ == 'file-size':
        ts_type = 'number'
        ts_format = 'filesize'
    elif typ == 'integer':
        ts_type = 'number'
    elif typ == 'string':
        ts_type = 'string'
    elif typ == 'boolean':
        ts_type = 'boolean'
    else:
        raise AssertionError(
            'Unknown type encountered at {}: {}'.format(opt['tag'], typ)
        )

    return ts_type, ts_format, is_list


def parse_option(opt):
    tag = opt['tag']
    assert isinstance(tag, str)

    ts_type, ts_format, is_list = parse_type(opt)
    default = eval(generate_options_py.parse_type(opt)[0]).try_parse(
        opt['default']
    )

    frontend = opt.get('frontend', False)
    assert isinstance(frontend, bool)

    doc = opt['doc']

    return Option(
        tag=tag,
        ts_type=ts_type,
        is_list=is_list,
        default=default,
        ts_format=ts_format,
        frontend=frontend,
        doc=doc,
        group=opt.get('group', 'General')
    )


def main():
    options = get_options()
    assert isinstance(options, list)

    all_opts = [parse_option(opt) for opt in options]
    frontend_opts = [opt for opt in all_opts if opt.frontend]

    out_file = os.path.join(CUR_DIR, '..', 'src', 'models', 'siteSettings.ts')
    with open(out_file, 'w') as f:
        f.write('/* eslint-disable */\n')
        f.write('export interface FrontendSiteSettings {\n')
        for opt in frontend_opts:
            opt.write_doc(f, 4)
            f.write('    ')
            f.write(opt.tag)
            f.write(': ')

            opt.write_type(f)
            f.write(';\n')
        f.write('}\n\n')

        f.write(
            'export interface SiteSettings extends FrontendSiteSettings {\n'
        )
        for opt in all_opts:
            if opt in frontend_opts:
                continue
            opt.write_doc(f, 4)
            f.write('    ')
            f.write(opt.tag)
            f.write(': ')
            opt.write_type(f)

            f.write(';\n')
        f.write('}\n\n')

        f.write(
            'export const FRONTEND_SETTINGS_DEFAULTS = Object.freeze(<const>{\n'
        )
        for opt in frontend_opts:
            f.write('    ')
            f.write(opt.tag)
            f.write(': ')
            json.dump(cg_json.JSONResponse.dump_to_object(opt.default), f)
            f.write(',\n')
        f.write('});\n\n')

        f.write('export const ALL_SITE_SETTINGS = Object.freeze(<const>[\n')
        for opt in all_opts:
            f.write('    {')
            f.write(f' name: {opt.tag!r},')
            f.write(f' typ: {opt.ts_type!r},')
            f.write(f' doc: {opt.doc!r},')
            f.write(f' format: {opt.ts_format!r},')
            f.write(f' group: ')
            json.dump(opt.group, f)
            f.write(', list: ')
            json.dump(opt.is_list, f)
            f.write(' },\n')
        f.write(']);\n\n')


if __name__ == '__main__':
    with psef.create_app(skip_all=True).app_context():
        main()
