import os
import abc
import uuid
import shutil
import typing as t
import contextlib
from os import path as os_path

import structlog

from cg_maybe import Just, Maybe, Nothing
from cg_dt_utils import DatetimeWithTimezone

from . import utils
from .types import FileSize

logger = structlog.get_logger()


class File:
    @abc.abstractmethod
    def delete(self) -> None:
        ...

    @abc.abstractmethod
    def open(self) -> t.BinaryIO:
        ...

    @property
    @abc.abstractmethod
    def size(self) -> FileSize:
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    def copy(self: 'FileT') -> 'FileT':
        ...

    @property
    @abc.abstractmethod
    def exists(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def creation_time(self) -> DatetimeWithTimezone:
        ...

    @abc.abstractmethod
    def save_to_disk(self, dst_path: str) -> None:
        pass


FileT = t.TypeVar('FileT', bound=File, covariant=True)

class _BulkPutter(t.Generic[FileT]):
    @abc.abstractmethod
    def put_from_file(self, src_path: str, *, move: bool) -> FileT:
        ...

    @abc.abstractmethod
    def put_from_string(self, source: str) -> FileT:
        ...

    @abc.abstractmethod
    def put_from_stream(
        self, stream: utils.ReadableStream, *, max_size: FileSize
    ) -> Maybe[FileT]:
        ...


class _Storage(t.Generic[FileT]):
    @abc.abstractmethod
    def get(self, name: str) -> Maybe[FileT]:
        ...

    @abc.abstractmethod
    def put_from_file(self, src_path: str, *, move: bool) -> FileT:
        ...

    @abc.abstractmethod
    def put_from_string(self, source: str) -> FileT:
        ...

    @abc.abstractmethod
    def put_from_stream(
        self, stream: utils.ReadableStream, *, max_size: FileSize
    ) -> Maybe[FileT]:
        ...

    @abc.abstractmethod
    def check_health(self, min_free_space: FileSize) -> bool:
        ...

    @contextlib.contextmanager
    def bulk_put(self) -> _BulkPutter[FileT]:
        return self


class LocalFile(File):
    __slots__ = ('__name', '__storage', '__size')

    def __init__(self, name: str, storage: 'LocalStorage') -> None:
        self.__name = name
        self.__storage = storage
        self.__size: t.Optional[FileSize] = None

    @property
    def exists(self) -> bool:
        return self.__storage.safe_join(self.__name).is_just

    @property
    def path(self) -> str:
        return self.__storage.safe_join(self.__name).unsafe_extract()

    @property
    def name(self) -> str:
        return self.__name

    def delete(self) -> None:
        path = self.__storage.safe_join(self.__name).unsafe_extract()
        os.unlink(path)

    def open(self) -> t.BinaryIO:
        return open(self.path, 'rb')

    @property
    def size(self) -> FileSize:
        if self.__size is None:
            self.__size = FileSize(max(1, os_path.getsize(self.path)))
        return self.__size

    def copy(self) -> 'LocalFile':
        return self.__storage.put_from_file(self.path, move=False)

    @property
    def creation_time(self) -> DatetimeWithTimezone:
        mtime = os_path.getmtime(self.path)
        return DatetimeWithTimezone.utcfromtimestamp(mtime)

    def save_to_disk(self, dst_path: str) -> None:
        shutil.copyfile(src=self.path, dst=dst_path, follow_symlinks=False)


class LocalStorage(_Storage[LocalFile]):
    __slots__ = ('__directory', )

    def __init__(self, directory: str) -> None:
        self.__directory = directory

    def check_health(self, min_free_space: FileSize) -> bool:
        """Check if the this storage is a healthy state.

        :param check_size: The minimum amount of free space required.

        :returns: ``True`` if health is ok ``False`` otherwise.
        """
        path = self.__directory
        mode = os.R_OK | os.W_OK | os.X_OK
        ok = os_path.isdir(path) and os.access(path, mode)

        if ok:
            free_space = shutil.disk_usage(path).free
            ok = free_space > min_free_space

        return ok

    @staticmethod
    def _is_file(path: str) -> bool:
        if os_path.islink(path):
            logger.error(
                'Symlink found in storage',
                path=path,
            )
            return False
        return os_path.isfile(path)

    def safe_join(self, child: str) -> Maybe[str]:
        path = os_path.normpath(
            os_path.realpath(os_path.join(self.__directory, child))
        )
        if not path.startswith(self.__directory):
            return Nothing
        elif not self._is_file(path):
            return Nothing

        return Just(path)

    def get(self, name: str) -> Maybe[LocalFile]:
        path = self.safe_join(name)
        return path.map(lambda name: LocalFile(name, self))

    def _make_path(self) -> t.Tuple[str, str]:
        while True:
            opt = str(uuid.uuid4())
            path = os_path.normpath(
                os_path.realpath(os_path.join(self.__directory, opt))
            )
            if path.startswith(self.__directory) and not os_path.exists(path):
                break

        return opt, path

    def put_from_file(self, src_path: str, *, move: bool) -> LocalFile:
        name, dst_path = self._make_path()

        assert self._is_file(src_path)

        if move:
            shutil.move(src=src_path, dst=dst_path)
        else:
            shutil.copy(src=src_path, dst=dst_path)

        return LocalFile(name, self)

    def put_from_string(self, source: str) -> LocalFile:
        name, dst_path = self._make_path()
        with open(dst_path, 'w') as f:
            f.write(source)

        return LocalFile(name, self)

    def put_from_stream(
        self, stream: utils.ReadableStream, *, max_size: FileSize
    ) -> Maybe[LocalFile]:
        min_size = utils.get_size_lower_bound(stream)
        # We know that the stream will always be longer than the allowed
        # maximum size. In this case don't spend time copying stuff we will
        # remove later on anyway.
        if min_size.is_just and min_size.value > max_size:
            return Nothing

        name, dst_path = self._make_path()
        with open(dst_path, 'wb') as dst:
            res = utils.limited_copy(stream, dst=dst, max_size=max_size)

        if not res.complete:
            os.unlink(dst_path)
            return Nothing

        return Just(LocalFile(name, self))


Storage = _Storage[File]
BulkPutter = _BulkPutter[File]
