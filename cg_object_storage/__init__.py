import os
import abc
import uuid
import shutil
import typing as t
import contextlib
from os import path as os_path

import structlog
from typing_extensions import Protocol

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


class _Putter(Protocol[FileT]):
    def from_file(self, src_path: str, *, move: bool) -> FileT:
        ...

    def from_string(self, source: str) -> FileT:
        ...

    def from_stream(
        self,
        stream: utils.ReadableStream,
        *,
        max_size: FileSize,
        size: Maybe[FileSize] = Nothing,
    ) -> Maybe[FileT]:
        ...

    def rollback(self) -> None:
        ...


class _Storage(t.Generic[FileT]):
    @abc.abstractmethod
    def get(self, name: str) -> Maybe[FileT]:
        ...

    @abc.abstractmethod
    def check_health(self, min_free_space: FileSize) -> bool:
        ...

    @abc.abstractmethod
    def _get_putter(self) -> _Putter[FileT]:
        ...

    @contextlib.contextmanager
    def putter(self) -> t.Generator[_Putter[FileT], None, None]:
        putter = self._get_putter()
        try:
            yield putter
        except:
            putter.rollback()
            raise


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
        with self.__storage.putter() as putter:
            return putter.from_file(self.path, move=False)

    @property
    def creation_time(self) -> DatetimeWithTimezone:
        mtime = os_path.getmtime(self.path)
        return DatetimeWithTimezone.utcfromtimestamp(mtime)

    def save_to_disk(self, dst_path: str) -> None:
        shutil.copyfile(src=self.path, dst=dst_path, follow_symlinks=False)


def _is_file(path: str) -> bool:
    if os_path.islink(path):
        logger.error(
            'Symlink found in storage',
            path=path,
        )
        return False
    return os_path.isfile(path)


class _LocalFilePutter:
    __slots__ = ('__storage', '__new_files')

    def __init__(self, storage: 'LocalStorage') -> None:
        self.__storage = storage
        self.__new_files: t.List[str] = []

    @property
    def _directory(self) -> str:
        return self.__storage._directory  # pylint: disable=protected-access

    def _make_path(self) -> t.Tuple[str, str]:
        directory = self._directory
        while True:
            opt = str(uuid.uuid4())
            path = os_path.normpath(
                os_path.realpath(os_path.join(directory, opt))
            )
            if path.startswith(directory) and not os_path.exists(path):
                break

        return opt, path

    def from_file(self, src_path: str, *, move: bool) -> LocalFile:
        name, dst_path = self._make_path()

        assert _is_file(src_path)

        self.__new_files.append(dst_path)
        if move:
            shutil.move(src=src_path, dst=dst_path)
        else:
            shutil.copy(src=src_path, dst=dst_path)

        return LocalFile(name, self.__storage)

    def from_string(self, source: str) -> LocalFile:
        name, dst_path = self._make_path()
        self.__new_files.append(dst_path)

        with open(dst_path, 'w') as f:
            f.write(source)

        return LocalFile(name, self.__storage)

    def from_stream(
        self,
        stream: utils.ReadableStream,
        *,
        max_size: FileSize,
        size: Maybe[FileSize] = Nothing,
    ) -> Maybe[LocalFile]:
        min_size = size.alt(utils.get_size_lower_bound(stream))
        # We know that the stream will always be longer than the allowed
        # maximum size. In this case don't spend time copying stuff we will
        # remove later on anyway.
        if min_size.is_just and min_size.value > max_size:
            return Nothing

        name, dst_path = self._make_path()
        self.__new_files.append(dst_path)
        with open(dst_path, 'wb') as dst:
            if size.is_just:
                res = utils.exact_copy(stream, dst=dst, length=size.value)
            else:
                res = utils.limited_copy(stream, dst=dst, max_size=max_size)
        print('wrote', os_path.getsize(dst_path))

        if not res.complete:
            os.unlink(dst_path)
            return Nothing

        return Just(LocalFile(name, self.__storage))

    def rollback(self) -> None:
        for new_path in self.__new_files:
            try:
                os.unlink(new_path)
            except BaseException:  # pragma: no cover
                pass

        self.__new_files.clear()


class LocalStorage(_Storage[LocalFile]):
    __slots__ = ('_directory', )

    def __init__(self, directory: str) -> None:
        self._directory = directory

    def check_health(self, min_free_space: FileSize) -> bool:
        """Check if the this storage is a healthy state.

        :param check_size: The minimum amount of free space required.

        :returns: ``True`` if health is ok ``False`` otherwise.
        """
        path = self._directory
        mode = os.R_OK | os.W_OK | os.X_OK
        ok = os_path.isdir(path) and os.access(path, mode)

        if ok:
            free_space = shutil.disk_usage(path).free
            ok = free_space > min_free_space

        return ok

    def safe_join(self, child: str) -> Maybe[str]:
        path = os_path.normpath(
            os_path.realpath(os_path.join(self._directory, child))
        )
        if not path.startswith(self._directory):
            return Nothing
        elif not _is_file(path):
            return Nothing

        return Just(path)

    def get(self, name: str) -> Maybe[LocalFile]:
        path = self.safe_join(name)
        return path.map(lambda _: LocalFile(name, self))

    def _get_putter(self) -> _LocalFilePutter:
        return _LocalFilePutter(self)


Storage = _Storage[File]
Putter = _Putter[File]
