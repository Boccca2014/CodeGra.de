#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import glob
import json
import socket
import typing as t


def recv(s: socket.socket) -> str:
    message = b''

    while True:
        m = s.recv(1024)
        message += m
        if not m:
            break

    return message.decode()


def main() -> None:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect('/dev/cg_socket')

    student_dir = os.getenv('STUDENT')
    assert student_dir is not None
    files = glob.glob(student_dir + '/*')
    severities = ['fatal', 'error', 'warning', 'info']
    comments = [
        {
            'severity': severities[i % len(severities)],
            'code': None,
            'origin': 'Fake linter',
            'msg': 'Wow nice linter dude!',
            'line': {
                'start': 0,
                'end': 0
            },
            'column': {
                'start': 0,
                'end': None
            },
            'path': f[len(student_dir):].split('/'),
        } for i, f in enumerate(files)
    ]

    s.sendall(
        json.dumps({
            'op': 'put_comments',
            'comments': comments,
        }).encode('utf8')
    )
    s.sendall(b'\0')
    print(recv(s))


if __name__ == '__main__':
    main()
