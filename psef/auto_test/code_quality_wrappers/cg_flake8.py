#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import json
import uuid
import typing as t
import subprocess


def handle_error(filename: str, line: str, col: str, code: str, msg: str):
    if filename.startswith('./'):
        filename = filename[2:]

    if code.startswith('E') or code.startswith('F'):
        severity = 'error'
    elif code.startswith('W'):
        severity = 'warning'
    elif code.startswith('C') or code.startswith('N8'):
        severity = 'info'

    return dict(
        [
            ('origin', 'Flake8'),
            ('msg', msg),
            ('code', code),
            ('severity', severity),
            ('line', dict([
                ('start', int(line)),
                ('end', int(line)),
            ])),
            ('column', dict([
                ('start', int(col)),
                ('end', None),
            ])),
            ('path', filename.split('/')),
        ]
    )


def main(argv: t.Sequence[str]) -> int:
    """Run Flake8.
    """

    # If the first argument is nonempty, it is the path to a config file, so
    # insert `--config` right before it. Otherwise drop the argument.
    if not argv:
        args = []
    elif argv[0]:
        args = ['--config', *argv]
    else:
        args = argv[1:]

    # This is not guessable
    sep = str(uuid.uuid4())
    fmt = '%(path)s{0}%(row)d{0}%(col)d{0}%(code)s{0}%(text)s'.format(sep)

    # The check for success is something we really don't want here.
    proc = subprocess.run(  # pylint: disable=subprocess-run-check
        [
            'flake8',
            '--disable-noqa',
            '--format', fmt,
            '--exit-zero',
            *args,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )

    if proc.returncode != 0:
        print('Flake8 crashed:\n', proc.stderr, file=sys.stderr)
        return proc.returncode

    comments = [
        handle_error(*err.split(sep))
        for err in proc.stdout.splitlines()
        if len(err.split(sep)) == 5
    ]

    if comments:
        output = json.dumps(
            dict([
                ('op', 'put_comments'),
                ('comments', comments),
            ]),
        )
        api_proc = subprocess.run(
            ['cg-api'], input=output.encode('utf8'), check=False
        )
        return api_proc.returncode

    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
