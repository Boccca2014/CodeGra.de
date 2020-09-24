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
    __slots__ = ('complete', 'amount')
    complete: bool
    amount: FileSize


_BUFFER_SIZE = 16 * 1024


def exact_copy(
    src: ReadableStream,
    dst: t.IO[bytes],
    length: FileSize,
) -> CopyResult:
    """Copy exact ``length`` bytes from ``src`` to ``dst``

    This method was inspired by the ``copyfileobj`` method from the ``tarfile``
    module.
    """
    bufsize = _BUFFER_SIZE
    blocks, remainder = divmod(length, bufsize)

    for b in range(blocks):
        buf = src.read(bufsize)
        if len(buf) < bufsize:
            return CopyResult(
                complete=False, amount=FileSize(max(0, (b - 1) * bufsize))
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
    """
    size_left: int = max_size
    written = 0
    src_read = src.read
    dst_write = dst.write
    bufsize: int = _BUFFER_SIZE

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
    if isinstance(stream, LimitedStream):
        return cg_maybe.Just(FileSize(stream.limit))
    return cg_maybe.Nothing
