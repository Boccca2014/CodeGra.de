#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import sys
import socket


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

    s.sendall(sys.stdin.buffer.read())
    s.sendall(b'\0')
    print(recv(s))


if __name__ == '__main__':
    main()
