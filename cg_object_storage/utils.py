"""Util methods for writing and reading from streams.

SPDX-License-Identifier: AGPL-3.0-only
"""
import shutil
import typing as t
from dataclasses import dataclass

from werkzeug.wsgi import LimitedStream
from typing_extensions import Protocol

import cg_maybe

from .types import FileSize


class ReadableStream(Protocol):
    """A protocol representing an object from which you can read binary data.
    """

    def read(self, amount: int) -> bytes:  # pylint: disable=unused-argument,no-self-use
        ...


@dataclass
class CopyResult:
    """The result after doing a checked copy.
    """
    __slots__ = ('complete', 'amount')

    #: Was the copy completed as requested.
    complete: bool
    #: How many bytes were written.
    amount: FileSize


_BUFFER_SIZE = FileSize(16 * 1024)


def exact_copy(
    src: ReadableStream,
    dst: t.IO[bytes],
    length: FileSize,
    *,
    bufsize: FileSize = _BUFFER_SIZE
) -> CopyResult:
    """Copy exact ``length`` bytes from ``src`` to ``dst``

    This method was inspired by the ``copyfileobj`` method from the ``tarfile``
    module.
    """
    blocks, remainder = divmod(length, bufsize)

    for block in range(blocks):
        buf = src.read(bufsize)
        if len(buf) < bufsize:
            return CopyResult(
                complete=False, amount=FileSize(max(0, (block - 1) * bufsize))
            )
        dst.write(buf)

    if remainder:
        buf = src.read(remainder)
        if len(buf) < remainder:
            return CopyResult(
                complete=False, amount=FileSize(blocks * bufsize)
            )
        dst.write(buf)

    return CopyResult(complete=True, amount=length)


def limited_copy(
    src: ReadableStream,
    dst: t.IO[bytes],
    max_size: FileSize,
    *,
    bufsize: FileSize = _BUFFER_SIZE
) -> CopyResult:
    """Copy ``max_size`` bytes from ``src`` to ``dst``.

    """
    size_left: int = max_size
    written = 0
    src_read = src.read
    dst_write = dst.write

    while True:
        buf = src_read(bufsize)
        if not buf:
            break
        elif len(buf) > size_left:
            return CopyResult(complete=False, amount=FileSize(written))

        dst_write(buf)

        written = written + len(buf)
        size_left = size_left - len(buf)

    return CopyResult(complete=True, amount=FileSize(written))


def get_size_lower_bound(stream: ReadableStream) -> cg_maybe.Maybe[FileSize]:
    """Get the minimal amount of bytes in the given stream.

    :param stream: The stream to analyze.

    :returns: Nothing if we couldn't find any useful data, otherwise the
              minimum amount of bytes that are in the stream. There could be
              more, but not less.
    """
    if isinstance(stream, LimitedStream):
        return cg_maybe.Just(FileSize(stream.limit))
    return cg_maybe.Nothing
