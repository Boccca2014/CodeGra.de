"""This modules handles archives and extracting them in a safe way.

This original version of this module from `here
<https://github.com/gdub/python-archive>`_ and licensed under MIT. It has been
extensively modified.

SPDX-License-Identifier: MIT
"""

# Copyright (c) Gary Wilson Jr. <gary@thegarywilson.com> and contributors.
# All rights reserved.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import io
import os
import abc
import uuid
import typing as t
import tarfile
import zipfile
import contextlib
import dataclasses
from os import path

import py7zlib
import structlog

from cg_maybe import Just, Maybe
from cg_object_storage import File, Putter, FileSize

from . import app
from .helpers import register, add_warning
from .exceptions import APIWarnings
from .extract_tree import ExtractFileTree

T = t.TypeVar('T', bound='_BaseArchive')
TT = t.TypeVar('TT')

logger = structlog.get_logger()


@dataclasses.dataclass
class _Symlink:
    target: str


@dataclasses.dataclass(order=True, repr=True)
class ArchiveMemberInfo(t.Generic[TT]):  # pylint: disable=unsubscriptable-object
    """Information for member of an archive.

    :ivar name: The complete name of the member including previous directories.
    :ivar is_dir: Is the member a directory
    """
    name: t.Sequence[str] = dataclasses.field(init=False)
    orig_name: str
    is_dir: bool
    size: FileSize
    orig_file: TT

    def __post_init__(self) -> None:
        self.name = [p for p in self.orig_name.split('/') if p and p != '.']


class ArchiveException(Exception):
    """Base exception class for all archive errors."""


class _LimitedCopyOverflow(ArchiveException):
    """Exception that gets raised when a limited copy has data left too write.
    """


class UnrecognizedArchiveFormat(ArchiveException):
    """Error raised when passed file is not a recognized archive format."""


class UnsafeArchive(ArchiveException):
    """Error raised when passed file is unsafe to extract.

    This can be the case when the archive contains paths that would be
    extracted outside of the target directory.
    """

    def __init__(
        self, msg: str, member: t.Optional[ArchiveMemberInfo] = None
    ) -> None:
        super().__init__(msg)
        self.member = member


_archive_handlers: register.Register[str, t.Type['_BaseArchive']
                                     ] = register.Register()


class ArchiveTooLarge(ArchiveException):
    """Error raised when archive is too large when extracted."""

    def __init__(self, max_size: FileSize) -> None:
        super().__init__()
        self.max_size = max_size


class FileTooLarge(ArchiveTooLarge):
    pass


class Archive(t.Generic[TT]):  # pylint: disable=unsubscriptable-object
    """
    Base Archive class.  Implementations should inherit this class.
    """

    def __init__(self, archive: '_BaseArchive[TT]', filename: str) -> None:
        self.__archive = archive
        self.__max_items_check_done = False
        self.__filename = filename

    @classmethod
    def is_archive(cls: t.Type['Archive'], filename: str) -> bool:
        """Is the filename an archive we can extract.

        :param filename: The filename to check.
        :returns: A boolean indicating if :meth:`.Archive.create_from_file` for
            this filename would work.
        """
        return cls.__get_base_archive_class(filename) is not None

    @staticmethod
    def __get_base_archive_class(
        filename: str
    ) -> t.Optional[t.Type['_BaseArchive[object]']]:
        base, tail_ext = os.path.splitext(filename.lower())
        cls = _archive_handlers.get(tail_ext)
        if cls is None:
            base, ext = os.path.splitext(base)
            cls = _archive_handlers.get(ext)
        return cls

    @classmethod
    @contextlib.contextmanager
    def create_from_fileobj(cls, filename: str, fileobj: t.IO[bytes]
                            ) -> t.Iterator['Archive[object]']:
        """Create a instance of this class from the given filename.

        :param filename: The path to the file as source for this archive.
        :returns: An instance of :class:`Archive` when the filename was a
            recognized archive format.
        """
        base_archive_cls = cls.__get_base_archive_class(filename)

        if base_archive_cls is None:
            raise UnrecognizedArchiveFormat(
                'Path is not a recognized archive format'
            )
        arr = base_archive_cls(fileobj)

        try:
            yield t.cast(t.Type[Archive[object]], cls)(arr, filename)
        finally:
            arr.close()

    def extract(self, putter: Putter, max_size: FileSize) -> ExtractFileTree:
        """Safely extract the current archive.

        :returns: Nothing
        """

        self.check_files()
        res = self.__extract_archive(putter, max_size)
        return res

    def __extract_archive(
        self, putter: Putter, max_size: FileSize
    ) -> ExtractFileTree:
        total_size = FileSize(0)
        base = ExtractFileTree(name=self.__filename)
        symlinks = []

        def raise_archive_too_large() -> t.NoReturn:
            logger.warning(
                'Archive contents exceeded size limit', max_size=max_size
            )
            raise ArchiveTooLarge(max_size)

        def maybe_raise_too_large(extra: int = 0) -> None:
            if total_size + extra > max_size:
                raise_archive_too_large()

        def maybe_single_too_large(size: FileSize) -> None:
            if size > app.max_single_file_size:
                logger.warning(
                    'File exceeded size limit',
                    max_size=max_size,
                )
                raise FileTooLarge(FileSize(app.max_single_file_size))

        for member in self.get_members():
            if member.is_dir:
                base.insert_dir(member.name)
            else:
                maybe_raise_too_large(member.size)
                maybe_single_too_large(member.size)

                new_file = self.__archive.extract_member(
                    member, FileSize(max_size - total_size), putter
                )
                if new_file.is_nothing:
                    raise_archive_too_large()

                if isinstance(new_file.value, _Symlink):
                    link = new_file.value
                    backing_file = putter.from_string(
                        (
                            'This file was a symbolic link to "{}" when '
                            'it was submitted, but CodeGrade does not '
                            'support symbolic links.\n'
                        ).format(link.target)
                    )
                    logger.warning(
                        'Symlink detected in archive',
                        filename=member.name,
                        link_target=link.target,
                    )
                    symlinks.append(link.target)
                else:
                    backing_file = new_file.value

                total_size = FileSize(total_size + backing_file.size)
                maybe_raise_too_large()
                base.insert_file(member.name, backing_file)

        if symlinks:
            add_warning(
                (
                    'The archive contained symbolic links which are not '
                    'supported by CodeGrade: {}. The links have been replaced '
                    'with a regular file explaining that these files were '
                    'symbolic links, and the path they pointed to. Note: '
                    'This may break your submission when viewed by the '
                    'teacher.'
                ).format(', '.join(symlinks)),
                APIWarnings.SYMLINK_IN_ARCHIVE,
            )

        return base

    def get_members(self) -> t.Iterable[ArchiveMemberInfo[TT]]:
        """Get the members of this archive.

        This function also makes sure the archive doesn't contain too many
        members.

        :returns: The members of the archive.
        """
        max_amount = app.config['MAX_NUMBER_OF_FILES']
        if not self.__max_items_check_done:
            if not self.__archive.has_less_items_than(max_amount):
                raise UnsafeArchive(
                    f'Archive contains too many files, maximum is {max_amount}'
                )
            self.__max_items_check_done = True
        return sorted(self.__archive.get_members())

    def check_files(self) -> None:
        """
        Check that all of the files contained in the archive are within the
        target directory.


        :param to_path: The path were the archive should be extracted to.
        :returns: Nothing
        """
        _base_path = f'/{uuid.uuid4()}/'

        for member in self.get_members():
            paths = (
                path.normpath(
                    path.realpath(path.join(_base_path, member.orig_name))
                ),
                path.normpath(path.join(_base_path, member.orig_name)),
                path.normpath(path.join(_base_path, *member.name)),
            )

            if not member.name or not all(
                p.startswith(_base_path) and p != _base_path for p in paths
            ):
                raise UnsafeArchive(
                    'Archive member destination is outside the target'
                    ' directory', member
                )

        if self.__archive.has_unsafe_filetypes():
            raise UnsafeArchive('The archive contains unsafe filetypes')


class _BaseArchive(abc.ABC, t.Generic[TT]):
    @abc.abstractmethod
    def __init__(self, fileobj: t.IO[bytes]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def extract_member(
        self, member: ArchiveMemberInfo[TT], size_left: FileSize,
        putter: Putter
    ) -> Maybe[t.Union[File, _Symlink]]:
        """Extract the given filename to the given path.

        :param size_left: The maximum amount of size the extraction should
            take. This is also checked by the calling function after
            extraction.
        :returns: Nothing
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_members(self) -> t.Iterable[ArchiveMemberInfo[TT]]:
        """Get information of all the members of the archive.

        :returns: An iterable containing an :class:`.ArchiveMemberInfo` for
            each member of the archive, including directories.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def has_unsafe_filetypes(self) -> bool:
        """Check if the archive contains files which are not safe.

        All files that are not links, normal files or directories should be
        considered unsafe.

        :returns: True if any file is not safe.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        """Close the archive and delete all associated information with it.

        After calling this method the class cannot be used again.

        :returns: Nothing.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def has_less_items_than(self, max_items: int) -> bool:
        """Check if an archive has less items than the given max amount.


        .. warning::

            This method is used for a security check. Take care when
            calculating the size of the archive, as this could be an attack
            vector for a DDOS attack. This method is always called **before**
            :meth:`._BaseArchive.get_members`.

        :param max_items: The maximum amount of items, exclusive.
        :returns: True if the archive has less than ``max_items`` of items.
        """
        raise NotImplementedError


@_archive_handlers.register_all(
    [
        '.tar', '.tar.bz2', '.tar.gz', '.tgz', '.tz2', '.tar.xz', '.tbz',
        '.tb2', '.tbz2', '.txz'
    ]
)
class _TarArchive(_BaseArchive[tarfile.TarInfo]):  # pylint: disable=unsubscriptable-object
    def close(self) -> None:
        self._archive.close()

    def __init__(self, fileobj: t.IO[bytes]) -> None:
        self._archive = tarfile.open(fileobj=fileobj)

    def extract_member(
        self, member: ArchiveMemberInfo[tarfile.TarInfo], size_left: FileSize,
        putter: Putter
    ) -> Maybe[t.Union[File, _Symlink]]:
        """Extract the given member.

        :param member: The member to extract.
        """
        tarinfo = member.orig_file
        if tarinfo.islnk() or tarinfo.issym():
            return Just(_Symlink(tarinfo.linkname))

        assert tarinfo.isfile()
        assert getattr(tarinfo, 'sparse', None) is None

        fileobj = self._archive.fileobj
        assert fileobj is not None
        offset_data = tarinfo.offset_data  # type: ignore[attr-defined]
        fileobj.seek(offset_data)
        return putter.from_stream(
            fileobj, max_size=size_left, size=Just(FileSize(tarinfo.size))
        )

    def get_members(self) -> t.Iterable[ArchiveMemberInfo[tarfile.TarInfo]]:
        """Get all members from this tar archive.

        .. note::

            Only members returned by this function will be extracted. This
            function can therefore be used to filter out some files, like
            sparse files. Files that are symlinks should be kept, as special
            error handling is in place for such files.
        """
        for member in self._archive.getmembers():
            if not self._member_is_safe(member):
                continue

            name = member.name
            yield ArchiveMemberInfo(
                orig_name=name,
                is_dir=member.isdir(),
                size=FileSize(member.size),
                orig_file=member,
            )

    @staticmethod
    def _member_is_safe(member: tarfile.TarInfo) -> bool:
        if member.isfile():
            return getattr(member, 'sparse', None) is None

        return member.isdir() or member.issym() or member.islnk()

    def has_unsafe_filetypes(self) -> bool:
        return any(
            not self._member_is_safe(m) for m in self._archive.getmembers()
        )

    def has_less_items_than(self, max_items: int) -> bool:
        """Check if this archive has less than a given amount of members.

        :param max_items: The amount to check for.
        """
        i = 0
        while True:
            if self._archive.next() is None:
                break
            i += 1
            if i >= max_items:
                return False
        return True


@t.overload
def _get_members_of_archives(  # pylint: disable=function-redefined,missing-docstring,unused-argument
    archive_files: t.Iterable[zipfile.ZipInfo],
) -> t.Iterable[ArchiveMemberInfo[zipfile.ZipInfo]]:
    ...  # pylint: disable=pointless-statement


@t.overload
def _get_members_of_archives(  # pylint: disable=function-redefined,missing-docstring,unused-argument
    archive_files: t.Iterable[py7zlib.ArchiveFile],
) -> t.Iterable[ArchiveMemberInfo[py7zlib.ArchiveFile]]:
    ...  # pylint: disable=pointless-statement


def _get_members_of_archives(
    archive_files: t.Iterable[t.Union[zipfile.ZipInfo, py7zlib.ArchiveFile]],
) -> t.Iterable[ArchiveMemberInfo[t.Union[zipfile.ZipInfo, py7zlib.ArchiveFile]
                                  ]]:
    """Get the members of a 7zip or a *normal* zipfile.

    :param arch: The archive to get the archive members of.
    :returns: A iterable of archive member objects.
    """
    for member in archive_files:
        cur_is_dir = member.filename[-1] == '/'

        if cur_is_dir:
            yield ArchiveMemberInfo(
                orig_name=member.filename,
                is_dir=cur_is_dir,
                orig_file=member,
                size=FileSize(0),
            )
        elif isinstance(member, zipfile.ZipInfo):
            yield ArchiveMemberInfo(
                orig_name=member.filename,
                is_dir=False,
                orig_file=member,
                size=FileSize(member.file_size),
            )
        elif isinstance(member, py7zlib.ArchiveFile):
            yield ArchiveMemberInfo(
                orig_name=member.filename,
                is_dir=False,
                orig_file=member,
                size=FileSize(member.size),
            )


@_archive_handlers.register('.zip')
class _ZipArchive(_BaseArchive[zipfile.ZipInfo]):  # pylint: disable=unsubscriptable-object
    def close(self) -> None:
        self._archive.close()

    def has_unsafe_filetypes(self) -> bool:  # pylint: disable=no-self-use
        return False

    def __init__(self, fileobj: t.IO[bytes]) -> None:
        self._archive = zipfile.ZipFile(fileobj)

    def extract_member(
        self, member: ArchiveMemberInfo[zipfile.ZipInfo], size_left: FileSize,
        putter: Putter
    ) -> Maybe[File]:
        """Extract the given member.

        :param member: The member to extract.
        :param to_path: The location to which it should be extracted.
        """
        with self._archive.open(member.orig_file) as src:
            return putter.from_stream(src, max_size=size_left)

    def get_members(self) -> t.Iterable[ArchiveMemberInfo[zipfile.ZipInfo]]:
        """Get all members from this zip archive.
        """
        yield from _get_members_of_archives(self._archive.infolist())

    def has_less_items_than(self, max_items: int) -> bool:
        """Check if this archive has less than a given amount of members.

        :param max_items: The amount to check for.
        """
        # It is not possible to get the number of items in the zipfile without
        # reading them all, which is done on the ``__init__`` function.
        return len(self._archive.infolist()) < max_items


@_archive_handlers.register('.7z')
class _7ZipArchive(_BaseArchive[py7zlib.ArchiveFile]):  # pylint: disable=unsubscriptable-object
    def close(self) -> None:
        pass

    def has_unsafe_filetypes(self) -> bool:  # pylint: disable=no-self-use
        return False

    def __init__(self, fileobj: t.IO[bytes]) -> None:
        self._archive = py7zlib.Archive7z(fileobj)

    def extract_member(  # pylint: disable=no-self-use
        self, member: ArchiveMemberInfo[py7zlib.ArchiveFile],
            size_left: FileSize, putter: Putter
    ) -> Maybe[File]:
        """Extract the given member.

        :param member: The member to extract.
        :param to_path: The location to which it should be extracted.
        """
        # We cannot provide a maximum to read to this method...
        return putter.from_stream(
            io.BytesIO(member.orig_file.read()), max_size=size_left
        )

    def get_members(self
                    ) -> t.Iterable[ArchiveMemberInfo[py7zlib.ArchiveFile]]:
        """Get all members from this 7zip archive.
        """
        yield from _get_members_of_archives(self._archive.getmembers())

    def has_less_items_than(self, max_items: int) -> bool:
        """Check if this archive has less than a given amount of members.

        :param max_items: The amount to check for.
        """
        # It is not possible to get the number of items in the zipfile without
        # reading them all, which is done on the ``__init__`` function.
        return len(self._archive.getmembers()) < max_items
