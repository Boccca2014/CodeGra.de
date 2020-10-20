#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import os
import re
import sys
import glob
import typing as t

WARNING = """
Do not edit this enum as it is automatically generated by
"{filename}".""".format(filename=os.path.basename(__file__))

HEADER = """This file contains all wrapper scripts used by CodeGrade in
the "Code Quality" AutoTest step."""

PY_HEADER = """\"\"\"{header}

.. warning::

  {warning}

SPDX-License-Identifier: AGPL-3.0-only
\"\"\"
# pylint: skip-file
# flake8: noqa=E501
# yapf: disable

import cg_enum

""".format(
    header=HEADER,
    warning='\n  '.join(WARNING.split('\n')),
)

TS_HEADER = """/**
{header}

{warning}

SPDX-License-Identifier: AGPL-3.0-only
*/
/* eslint-disable */

""".format(
    header=HEADER,
    warning=WARNING,
)

ESCAPE_REPLACE_RE = re.compile(r'[ \-]')
ESCAPE_REMOVE_RE = re.compile(r'\W')


def escape(s: str) -> str:
    return re.sub(
        ESCAPE_REMOVE_RE,
        '',
        re.sub(ESCAPE_REPLACE_RE, '_', s),
    )


def render_py_enum_entry(script: str) -> str:
    base = os.path.basename(script)
    return f"{escape(base)} = '{base}'"


def render_py_enum(scripts: t.Iterable[str]) -> str:
    return """class CodeQualityWrapper(cg_enum.CGEnum):
    custom = 'custom'
    {}
""".format(
    '\n    '.join(
        render_py_enum_entry(s)
        for s in sorted(scripts)
    ),
)


def render_ts_enum_entry(script: str) -> str:
    base = os.path.basename(script)
    return f"{escape(base)} = '{escape(base)}'"


def render_ts_enum(scripts: t.Iterable[str]) -> str:
    return """export enum CodeQualityWrapper {{
    custom = 'custom',
    {}
}}
""".format(
    ',\n    '.join(
        render_ts_enum_entry(s)
        for s in sorted(scripts)
    ),
)


def main() -> None:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    psef_dir = os.path.join(base_dir, 'psef')

    wrapper_dir = os.path.join(psef_dir, 'auto_test', 'code_quality_wrappers')
    wrapper_scripts = glob.glob(os.path.join(wrapper_dir, 'cg-*'))

    py_out_path = os.path.join(wrapper_dir, '__init__.py')
    ts_out_path = os.path.join(base_dir, 'src', 'code_quality_wrappers.ts')

    print(f'Writing to "{py_out_path}"', end=' ... \n')
    sys.stdout.flush()

    with open(py_out_path, 'w') as out:
        out.write(PY_HEADER)
        out.write(render_py_enum(wrapper_scripts))

    print(f'Writing to "{ts_out_path}"', end=' ... \n')
    sys.stdout.flush()

    with open(ts_out_path, 'w') as out:
        out.write(TS_HEADER)
        out.write(render_ts_enum(wrapper_scripts))

    print('done!')


if __name__ == '__main__':
    main()