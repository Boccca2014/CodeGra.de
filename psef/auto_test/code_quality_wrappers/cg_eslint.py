#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import json
import tempfile
import typing as t
import subprocess

STUDENT = os.environ['STUDENT']


def handle_file_output(f):
    msgs = []

    for message in f['messages']:
        if message.get('fatal', False):
            severity = 'fatal'
        elif message['severity'] == 1:
            severity = 'warning'
        elif message['severity'] == 2:
            severity = 'error'

        msg = dict(
            [
                ('origin', 'ESLint'),
                ('msg', message['message']),
                ('code', message['ruleId']),
                ('severity', severity),
                (
                    'line',
                    dict(
                        [
                            ('start', message['line']),
                            ('end', message.get('endLine', message['line'])),
                        ]
                    )
                ),
                (
                    'column',
                    dict(
                        [
                            ('start', message['column']),
                            ('end', message.get('endColumn', None)),
                        ]
                    )
                ),
                ('path', f['filePath'][len(STUDENT):].split('/')),
            ]
        )
        msgs.append(msg)

    return msgs


def main(argv: t.Sequence[str]) -> int:
    """Run ESLint.
    """

    npm_root = subprocess.check_output(['npm', 'root', '-g'])

    # The check for success is something we really don't want here.
    proc = subprocess.run(  # pylint: disable=subprocess-run-check
        [
            'eslint',
            '--format', 'json',
            '--resolve-plugins-relative-to', npm_root,
            # Prevent students from modifying the config.
            '--no-eslintrc',
            '--no-inline-config',
            '--report-unused-disable-directives',
            *argv,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )

    # Exit code 1 means that linting was successful but that errors
    # were found.
    if proc.returncode not in (0, 1):
        print('ESLint crashed:\n', proc.stderr, file=sys.stderr)
        return proc.returncode

    comments = [
        c for f in json.loads(proc.stdout)
        for c in handle_file_output(f)
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
