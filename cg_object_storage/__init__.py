"""This module provides an abstraction over object like storage providers.

SPDX-License-Identifier: AGPL-3.0-only
"""
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
    """This class represents a single file in the storage provider.
    """

    @abc.abstractmethod
    def delete(self) -> None:
        """Delete this file from the storage provider.
        """
        ...

    @abc.abstractmethod
    def open(self) -> t.BinaryIO:
        """Open this file for reading.

        This method should be used in a contextmanager.
        """
        ...

    @property
    @abc.abstractmethod
    def size(self) -> FileSize:
        """Get the size of the file.
        """
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """The name of the file.

        You should be able to find this file using this name attribute using
        the storage provider. So ``storage.get(f.name).unsafe_extract().name ==
        f.name)``.
        """
        ...

    @property
    @abc.abstractmethod
    def exists(self) -> bool:
        """Check that this file still exists in the storage.
        """
        ...

    @property
    @abc.abstractmethod
    def creation_time(self) -> DatetimeWithTimezone:
        """Get the time this file was created.

        As files cannot be updated this may also be the latest modification
        time.
        """
        ...

    @abc.abstractmethod
    def save_to_disk(self, dst_path: str) -> None:
        """Write this file to disk at the given path.

        :param dst_path: The location where the file should be saved.
        """
        ...

    @abc.abstractmethod
    def copy(self: 'FileT', putter: '_Putter[FileT]') -> 'FileT':
        """Copy this file using the given ``putter``.

        :param putter: Used to insert the copy of the file.
        """
        ...


FileT = t.TypeVar('FileT', bound=File, covariant=True)


class _Putter(Protocol[FileT]):
    # pylint: disable=unused-argument, no-self-use
    def from_file(self, src_path: str, *, move: bool) -> FileT:
        """Create a new file from a file from the local filename.

        :param src_path: The source location from which the file should be
            created.
        :param move: If ``true`` the file located at ``src_path`` will be
            deleted after this function returns.

        :returns: The created file.
        """
        ...

    def from_string(self, source: str) -> FileT:
        """Create a new file from a string.

        :param source: The content of the new file.

        :returns: The created file.
        """
        ...

    def from_stream(
        self,
        stream: utils.ReadableStream,
        *,
        max_size: FileSize,
        size: Maybe[FileSize] = Nothing,
    ) -> Maybe[FileT]:
        """Create a new file from a stream (fileobject).

        :param stream: The stream from which we should create the stream. By
            default we will completely consume the stream (upto ``max_size``
            bytes), if ``size`` is not ``Nothing`` no more bytes than ``size``
            will be read.
        :param max_size: The maximum size the resulting file may have.
        :param size: If ``Just`` this can be used to control the size of the
            resulting file. If less data is available in ``stream`` ``Nothing``
            will be returned.

        :returns: Maybe the created file, if the stream was valid. Cases where
                  ``Nothing`` is returned include (but are not limited to): the
                  stream contained more data than ``max_size``.
        """
        ...

    def rollback(self) -> None:
        """Remove all created files with this putter.

        .. note:: Deleted files (e.g. ``move`` parameter) are not restored.
        """
        ...

    # pylint: enable=unused-argument, no-self-use


class _Storage(t.Generic[FileT]):
    @abc.abstractmethod
    def get(self, name: str) -> Maybe[FileT]:
        """Get the file with the given name.

        :param name: The name of the file you want to get.

        :returns: Maybe the found file, depending on if it exists.
        """
        ...

    @abc.abstractmethod
    def check_health(self, min_free_space: FileSize) -> bool:
        """Check that the health of this storage provider is OK.

        :param min_free_space: The minimum free space this provider should
            have.

        :returns: A boolean indicating the health of the storage.
        """
        ...

    @abc.abstractmethod
    def _get_putter(self) -> _Putter[FileT]:
        ...

    @contextlib.contextmanager
    def putter(self) -> t.Generator[_Putter[FileT], None, None]:
        """Get a putter as a context manager.

        :returns: A putter that will automatically be rolled back when the
                  block in the context manager raises.
        """
        putter = self._get_putter()
        try:
            yield putter
        # pylint: disable=bare-except
        except:
            putter.rollback()
            raise


class _LocalFile(File):
    __slots__ = ('__name', '__joiner', '__size')

    def __init__(
        self, name: str, joiner: t.Callable[[str], Maybe[str]]
    ) -> None:
        self.__name = name
        self.__joiner = joiner
        self.__size: t.Optional[FileSize] = None

    @property
    def exists(self) -> bool:
        return self.__joiner(self.__name).is_just

    @property
    def _path(self) -> str:
        return self.__joiner(self.__name).unsafe_extract()

    @property
    def name(self) -> str:
        return self.__name

    def delete(self) -> None:
        path = self.__joiner(self.__name).unsafe_extract()
        os.unlink(path)

    def open(self) -> t.BinaryIO:
        return open(self._path, 'rb')

    @property
    def size(self) -> FileSize:
        if self.__size is None:
            self.__size = FileSize(max(1, os_path.getsize(self._path)))
        return self.__size

    def copy(self, putter: '_Putter[_LocalFile]') -> '_LocalFile':
        return putter.from_file(self._path, move=False)

    @property
    def creation_time(self) -> DatetimeWithTimezone:
        mtime = os_path.getmtime(self._path)
        return DatetimeWithTimezone.utcfromtimestamp(mtime)

    def save_to_disk(self, dst_path: str) -> None:
        shutil.copyfile(src=self._path, dst=dst_path, follow_symlinks=False)


def _is_file(path: str) -> bool:
    if os_path.islink(path):  # pragma: no cover
        logger.error(
            'Symlink found in storage',
            path=path,
            report_to_sentry=True,
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

    @property
    def _safe_join(self) -> t.Callable[[str], Maybe[str]]:
        return self.__storage._safe_join  # pylint: disable=protected-access

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

    def from_file(self, src_path: str, *, move: bool) -> _LocalFile:
        """Create a file from a file on disk.
        """
        name, dst_path = self._make_path()

        assert _is_file(src_path)

        self.__new_files.append(dst_path)
        if move:
            shutil.move(src=src_path, dst=dst_path)
        else:
            shutil.copy(src=src_path, dst=dst_path)

        return _LocalFile(name, self._safe_join)

    def from_string(self, source: str) -> _LocalFile:
        """Create a file from a string.
        """
        name, dst_path = self._make_path()
        self.__new_files.append(dst_path)

        with open(dst_path, 'w') as f:
            f.write(source)

        return _LocalFile(name, self._safe_join)

    def from_stream(
        self,
        stream: utils.ReadableStream,
        *,
        max_size: FileSize,
        size: Maybe[FileSize] = Nothing,
    ) -> Maybe[_LocalFile]:
        """Create a file from a stream.
        """
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

        if not res.complete:
            os.unlink(dst_path)
            return Nothing

        return Just(_LocalFile(name, self._safe_join))

    def rollback(self) -> None:
        """Rollback all newly added files.
        """
        for new_path in self.__new_files:
            try:
                os.unlink(new_path)
            # pylint: disable=bare-except
            except:  # pragma: no cover
                pass

        self.__new_files.clear()


class LocalStorage(_Storage[_LocalFile]):
    """A storage that stores all files in a single directory.
    """
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

    def _safe_join(self, child: str) -> Maybe[str]:
        path = os_path.normpath(
            os_path.realpath(os_path.join(self._directory, child))
        )
        if not path.startswith(self._directory):
            return Nothing
        elif not _is_file(path):
            return Nothing

        return Just(path)

    def get(self, name: str) -> Maybe[_LocalFile]:
        path = self._safe_join(name)
        return path.map(lambda _: _LocalFile(name, self._safe_join))

    def _get_putter(self) -> _LocalFilePutter:
        return _LocalFilePutter(self)


Storage = _Storage[File]
Putter = _Putter[File]
