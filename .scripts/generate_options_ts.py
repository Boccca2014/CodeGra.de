#!/usr/bin/env python
import os
import json
import typing as t
import datetime
import textwrap
import subprocess

import yaml

import psef
import cg_json
import cg_request_args as rqa
import generate_options_py

CUR_DIR = os.path.dirname(__file__)


def write_doc(f, doc, indent_num):
    indent = ' ' * indent_num + '// '
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
        ts_type = 'number'
    elif typ == 'file-size':
        ts_type = 'number'
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

    if is_list:
        return f'readonly {ts_type}[]'
    return ts_type


def parse_option(opt):
    tag = opt['tag']
    assert isinstance(tag, str)

    ts_type = parse_type(opt)
    default = eval(generate_options_py.parse_type(opt)[0]).try_parse(
        opt['default']
    )

    frontend = opt.get('frontend', False)
    assert isinstance(frontend, bool)

    doc = opt['doc']

    return tag, ts_type, default, frontend, doc


def main():
    options = get_options()
    assert isinstance(options, list)
    opts = []
    frontend_opts = []

    for opt in options:
        tag, ts_type, default, frontend, doc = parse_option(opt)
        if frontend:
            opts.append((tag, ts_type, default, doc))

    out_file = os.path.join(CUR_DIR, '..', 'src', 'models', 'siteSettings.ts')
    with open(out_file, 'w') as f:
        f.write('export interface FrontendOptions {\n')
        for tag, typ, *_ in opts:
            write_doc(f, doc, 4)
            f.write('    ')
            f.write(tag)
            f.write(': ')
            f.write(typ)
            f.write(';\n')
        f.write('}\n\n')

        f.write('export const FrontendOptionsDefaults = Object.freeze(<const>{\n')
        for tag, _, default, *__ in opts:
            f.write('    ')
            f.write(tag)
            f.write(': ')
            json.dump(cg_json.JSONResponse.dump_to_object(default), f)
            f.write(',\n')
        f.write('});\n')


if __name__ == '__main__':
    with psef.create_app(skip_all=True).app_context():
        main()
