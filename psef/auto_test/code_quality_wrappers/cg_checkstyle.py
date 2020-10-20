#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import json
import typing as t
import subprocess
import xml.etree.ElementTree as ET

STUDENT = os.environ['STUDENT']
CHECKSTYLE_PATH = os.getenv('CHECKSTYLE_PATH')
CHECKSTYLE_JAR = f'{CHECKSTYLE_PATH}/checkstyle.jar'


def handle_file_output(file_el):
    msgs = []

    for error_el in file_el:
        if error_el.tag != 'error':  # pragma: no cover
            continue

        filename = file_el.attrib['name']
        attrib = error_el.attrib
        line = int(attrib['line'])

        filename = filename[len(STUDENT):]
        if filename.startswith('./'):
            filename = filename[2:]

        msgs.append(
            dict(
                [
                    ('origin', 'Checkstyle'),
                    ('msg', attrib['message']),
                    ('code', attrib['source']),
                    ('severity', attrib.get('severity', 'warning')),
                    ('line', dict([
                        ('start', line),
                        ('end', line),
                    ])),
                    (
                        'column',
                        dict(
                            [
                                ('start', int(attrib.get('column', 1))),
                                ('end', None),
                            ]
                        )
                    ),
                    ('path', filename.split('/')),
                ]
            ),
        )

    return msgs


def main(argv: t.Sequence[str]) -> int:
    """Run Checkstyle
    """

    # The check for success is something we really don't want here.
    proc = subprocess.run(  # pylint: disable=subprocess-run-check
        [
            'java',
            '-jar', CHECKSTYLE_JAR,
            '-f', 'xml',
            *argv,
            '.',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )

    if proc.returncode == 254:
        print(
            'The given submission could not be parsed as Java:\n',
            proc.stderr,
            file=sys.stderr,
        )
        return proc.returncode

    try:
        output = ET.fromstring(proc.stdout)
    except ET.ParseError:
        print(
            'The output could not be parsed as XML:\n',
            proc.stderr,
            file=sys.stderr,
        )
        return proc.returncode

    comments = [
        err for el in output for err in handle_file_output(el)
        if el.tag == 'file'
    ]

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
