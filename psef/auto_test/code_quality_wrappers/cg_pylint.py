#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import json
import tempfile
import typing as t
import subprocess


def handle_error(message):
    severity = message['type']

    # Pylint has 4 message types: 'error', 'warning', 'convention', and
    # 'refactor'.
    if severity in ('convention', 'refactor'):
        severity = 'info'

    return dict(
        [
            ('origin', 'PyLint'),
            ('msg', message['message']),
            ('code', message['symbol']),
            ('severity', severity),
            (
                'line',
                dict([
                    ('start', message['line']),
                    ('end', message['line']),
                ])
            ),
            ('column', dict([
                ('start', message['column']),
                ('end', None),
            ])),
            ('path', message['path'].split('/')),
        ]
    )


def main(argv: t.Sequence[str]) -> int:
    """Run PyLint.
    """

    # If the first argument is nonempty, it is the path to a config file, so
    # insert `--config` right before it. Otherwise drop the argument.
    if not argv:
        args = []
    elif argv[0]:
        args = ['--rcfile', *argv]
    else:
        args = argv[1:]

    # The check for success is something we really don't want here.
    proc = subprocess.run(  # pylint: disable=subprocess-run-check
        [
            'pylint',
            '--output-format', 'json',
            *args,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )

    if proc.returncode == 32:
        print('PyLint crashed:\n', proc.stdout, file=sys.stderr)
        return 32

    if proc.returncode == 1:
        print(
            'The submission is not a valid python module, it probably lacks'
            ' an `__init__` file.',
            file=sys.stderr,
        )
        return 1

    comments = [
        handle_error(err) for err in json.loads(proc.stdout)
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


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
