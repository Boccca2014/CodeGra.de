#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import io
import os
import csv
import sys
import json
import typing as t
import subprocess

STUDENT = os.environ['STUDENT']
PMD_PATH = os.environ['PMD_PATH']
PMD_BIN = f'{PMD_PATH}/bin/run.sh'


def handle_error(message):
    try:
        priority = int(message['Priority'])
    except ValueError:
        print(
            'Unknown priority %s encountered!' % message['Priority'],
            file=sys.stderr
        )
        sys.exit(2)
    line = int(message['Line'])

    # PMD severities can be an integer from 1 to 5, 1 being the highest
    if priority == 1:
        severity = 'fatal'
    elif priority == 2:
        severity = 'error'
    elif priority == 3:
        severity = 'warning'
    elif priority >= 4:
        severity = 'info'

    return dict(
        [
            ('origin', 'PMD'),
            ('msg', message['Description']),
            ('code', message['Rule']),
            ('severity', severity),
            ('line', dict([
                ('start', line),
                ('end', line),
            ])),
            ('column', dict([
                ('start', 1),
                ('end', None),
            ])),
            ('path', message['File'].split('/')),
        ]
    )


def main(argv: t.Sequence[str]) -> int:
    """Run PMD.

    Arguments are the same as for :py:meth:`Linter.run`.
    """

    if not argv or not argv[0]:
        print(
            'PMD requires a config file to be able to run',
            file=sys.stderr,
        )
        return 1

    config, *args = argv


    # The check for success is something we really don't want here.
    proc = subprocess.run(  # pylint: disable=subprocess-run-check
        [
            PMD_BIN,
            'pmd',
            '-failOnViolation', 'false',
            '-format', 'csv',
            '-shortnames',
            '-rulesets', config,
            *args,
            '-dir', '.',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )

    if proc.returncode != 0:
        print('PMD crashed, stdout:\n', proc.stderr, file=sys.stderr)
        return proc.returncode

    output = csv.DictReader(io.StringIO(proc.stdout))

    if output is None:
        print('Could not parse PMD output:\n', proc.stdout, file=sys.stderr)
        return 1

    comments = [handle_error(err) for err in output]

    if comments:
        api_input = json.dumps(
            dict([
                ('op', 'put_comments'),
                ('comments', comments),
            ]),
        )
        api_proc = subprocess.run(
            ['cg-api'], input=api_input.encode('utf8'), check=False
        )
        return api_proc.returncode

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
