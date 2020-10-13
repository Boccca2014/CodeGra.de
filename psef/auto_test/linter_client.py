#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import glob
import json
import socket
import typing as t


make_comment(path: t.Sequence[str]) -> t.Dict:
    import random
    return {
        'severity': random.choice([
            'fatal',
            'error',
            'warning',
            'info',
        ]),
        'code': random.choice([
            'W100',
            'E35',
            None,
            None,
        ]),
        'origin': random.choice([
            'Fake linter',
            'mylint',
        ]),
        'msg': random.choice([
            'Linter crashed!',
            'This is definitely wrong!',
            'This is probably wrong!',
            'Wow nice linter dude!',
        ]),
        'line': random.choice([
            { 'start': 1, 'end': 1 },
            { 'start': 2, 'end': 6 },
            { 'start': 3, 'end': 4 },
            { 'start': 4, 'end': 4 },
        ]),
        'column': random.choice([
            { 'start': 1, 'end': 1 },
            { 'start': 1, 'end': 28 },
            { 'start': 4, 'end': None },
            { 'start': 13, 'end': 13 },
        ]),
        'path': path,
    }


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

    import random
    comments = [
        c
        for f in files
        for c in [
            make_comment(f[len(student_dir):].split('/'))
            for _ in range(random.randint(1, 4))
        ]
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
