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
    __slots__ = ('complete', 'amount')
    complete: bool
    amount: FileSize


_BUFFER_SIZE = 16 * 1024


def limited_copy(
    src: ReadableStream, dst: t.IO[bytes], max_size: FileSize
) -> CopyResult:
    """Copy ``max_size`` bytes from ``src`` to ``dst``.

    >>> import io
    >>> dst = io.BytesIO()
    >>> limited_copy(io.BytesIO(b'1234567890'), dst, 15)
    (True, 10)
    >>> dst.seek(0)
    0
    >>> dst.read()
    b'1234567890'
    >>> dst = io.BytesIO()
    >>> limited_copy(io.BytesIO(b'1234567890'), dst, 5)
    [False, 5]


    :raises _LimitedCopyOverflow: If more data was in source than
        ``max_size``. In this case some data may have been written to ``dst``,
        but this is not guaranteed.
    """
    size_left: int = max_size
    written = 0
    src_read = src.read
    dst_write = dst.write

    while True:
        buf = src_read(_BUFFER_SIZE)
        if not buf:
            break
        elif len(buf) > size_left:
            return CopyResult(complete=False, amount=FileSize(written))

        dst_write(buf)

        written = written + len(buf)
        size_left = size_left - len(buf)

    return CopyResult(complete=True, amount=FileSize(written))


def get_size_lower_bound(stream: ReadableStream) -> cg_maybe.Maybe[FileSize]:
    if isinstance(stream, LimitedStream):
        return cg_maybe.Just(FileSize(stream.limit))
    return cg_maybe.Nothing
