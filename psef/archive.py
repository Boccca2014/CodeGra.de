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

import os
import abc
import typing as t
import tarfile
import zipfile
import contextlib
import dataclasses
from os import path

import py7zlib
import structlog
from typing_extensions import Protocol

from . import app, models
from .helpers import register, add_warning
from .exceptions import APIWarnings

T = t.TypeVar('T', bound='_BaseArchive')
TT = t.TypeVar('TT')
FileSize = t.NewType('FileSize', int)

logger = structlog.get_logger()


@dataclasses.dataclass(order=True, repr=True)
class ArchiveMemberInfo(t.Generic[TT]):  # pylint: disable=unsubscriptable-object
    """Information for member of an archive.

    :ivar name: The complete name of the member including previous directories.
    :ivar is_dir: Is the member a directory
    """
    name: str
    is_dir: bool
    size: FileSize
    orig_file: TT


_BUFFER_SIZE = 16 * 1024


class ReadableStream(Protocol):
    """A protocol representing an object from which you can read binary data.
    """

    def read(self, amount: int) -> bytes:  # pylint: disable=unused-argument,no-self-use
        ...


def limited_copy(
    src: ReadableStream, dst: t.IO[bytes], max_size: FileSize
) -> FileSize:
    """Copy ``max_size`` bytes from ``src`` to ``dst``.

    >>> import io
    >>> dst = io.BytesIO()
    >>> limited_copy(io.BytesIO(b'1234567890'), dst, 15)
    10
    >>> dst.seek(0)
    0
    >>> dst.read()
    b'1234567890'
    >>> dst = io.BytesIO()
    >>> limited_copy(io.BytesIO(b'1234567890'), dst, 5)
    Traceback (most recent call last):
    ...
    _LimitedCopyOverflow


    :raises _LimitedCopyOverflow: If more data was in source than
        ``max_size``. In this case some data may have been written to ``dst``,
        but this is not guaranteed.
    """
    size_left = max_size
    written = FileSize(0)

    while True:
        buf: bytes = src.read(_BUFFER_SIZE)
        if not buf:
            break
        elif len(buf) > size_left:
            raise _LimitedCopyOverflow

        dst.write(buf)

        written = FileSize(written + len(buf))
        size_left = FileSize(size_left - len(buf))

    return written


def _safe_join(*args: str) -> str:
    assert args
    res = path.normpath(path.realpath(path.join(*args)))
    assert res.startswith(args[0])
    return res


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

    def __init__(self, archive: '_BaseArchive[TT]') -> None:
        self.__archive = archive
        self.__max_items_check_done = False

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
    def create_from_file(cls, filename: str) -> t.Iterator['Archive[object]']:
        """Create a instance of this class from the given filename.

        >>> with Archive.create_from_file('test_data/test_blackboard/correct.tar.gz') as arch:
        ...  arch
        <psef.archive.Archive object at 0x...>
        >>> with Archive.create_from_file('non_existing.tar.gz') as arch:
        ...  arch
        Traceback (most recent call last):
        ...
        FileNotFoundError: [Errno 2] No such file or directory: 'non_existing.tar.gz'
        >>> with Archive.create_from_file('not_an_archive') as arch:
        ...  arch
        Traceback (most recent call last):
        ...
        psef.archive.UnrecognizedArchiveFormat: Path is not a recognized archive format

        :param filename: The path to the file as source for this archive.
        :returns: An instance of :class:`Archive` when the filename was a
            recognized archive format.
        """
        base_archive_cls = cls.__get_base_archive_class(filename)

        if base_archive_cls is None:
            raise UnrecognizedArchiveFormat(
                'Path is not a recognized archive format'
            )
        arr = base_archive_cls(filename)

        try:
            yield t.cast(t.Type[Archive[object]], cls)(arr)
        finally:
            arr.close()

    def extract(self, to_path: str, max_size: FileSize) -> FileSize:
        """Safely extract the current archive.

        :param to_path: The path were the archive should be extracted to.
        :returns: Nothing
        """
        # Make sure we are passing a proper path as to_path
        assert to_path
        assert path.isabs(to_path)
        assert path.isdir(to_path)

        self.check_files(to_path)
        res = self.__extract_archive(to_path, max_size)
        self.replace_symlinks(to_path)
        return res

    def __extract_archive(
        self, base_to_path: str, max_size: FileSize
    ) -> FileSize:
        assert base_to_path
        total_size = FileSize(0)

        def maybe_raise_too_large(
            extra: int = 0, *, always: bool = False
        ) -> None:
            if always or total_size + extra > max_size:
                logger.warning(
                    'Archive contents exceeded size limit', max_size=max_size
                )
                raise ArchiveTooLarge(max_size)

        def maybe_single_too_large(size: FileSize) -> None:
            if size > app.max_single_file_size:
                logger.warning(
                    'File exceeded size limit',
                    max_size=max_size,
                )
                raise FileTooLarge(FileSize(app.max_single_file_size))

        for member in self.get_members():
            if member.is_dir:
                member_create_dir = _safe_join(base_to_path, member.name)
                assert member_create_dir.startswith(base_to_path)
                if not path.exists(member_create_dir):
                    os.makedirs(member_create_dir, mode=0o700)
            else:
                maybe_raise_too_large(member.size)
                maybe_single_too_large(member.size)

                member_to_path = _safe_join(base_to_path, member.name)
                member_to_dir = path.dirname(member_to_path)
                assert member_to_dir.startswith(base_to_path)
                if not path.exists(member_to_dir):
                    os.makedirs(member_to_dir, mode=0o700)

                try:
                    self.__archive.extract_member(
                        member, base_to_path, FileSize(max_size - total_size)
                    )
                except _LimitedCopyOverflow:  # pragma: no cover
                    maybe_raise_too_large(always=True)

                if path.islink(member_to_path):
                    total_size = FileSize(total_size + member.size)
                else:
                    real_size = FileSize(path.getsize(member_to_path))
                    maybe_single_too_large(real_size)
                    total_size = FileSize(total_size + real_size)
                maybe_raise_too_large()

        return total_size

    @staticmethod
    def replace_symlinks(to_path: str) -> None:
        """Replace symlinks in the given directory with regular files
        containing a notice that the symlink was replaced.

        :param to_path: Directory to scan for symlinks.
        :returns: Nothing
        """
        symlinks = []

        for parent, _, files in os.walk(to_path):
            for f in files:
                file_path = path.join(parent, f)

                if not path.islink(file_path):
                    assert path.isfile(file_path) or path.isdir(file_path)
                    # This cannot be covered, see:
                    # https://bitbucket.org/ned/coveragepy/issues/198/continue-marked-as-not-covered
                    continue  # pragma: no cover

                rel_path = path.relpath(file_path, to_path)
                link_target = os.readlink(file_path)

                symlinks.append(rel_path)
                os.remove(file_path)
                with open(file_path, 'w') as new_file:
                    new_file.write(
                        (
                            'This file was a symbolic link to "{}" when it '
                            'was submitted, but CodeGrade does not support '
                            'symbolic links.\n'
                        ).format(link_target),
                    )

                logger.warning(
                    'Symlink detected in archive',
                    filename=rel_path,
                    link_target=link_target,
                )

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

    def get_members(self) -> t.Iterable[ArchiveMemberInfo[TT]]:
        """Get the members of this archive.

        This function also makes sure the archive doesn't contain too many
        members.

        :returns: The members of the archive.
        """
        max_amount = models.AdminSetting.get_option('MAX_NUMBER_OF_FILES')
        if not self.__max_items_check_done:
            if not self.__archive.has_less_items_than(max_amount):
                raise UnsafeArchive(
                    f'Archive contains too many files, maximum is {max_amount}'
                )
            self.__max_items_check_done = True
        return self.__archive.get_members()

    def check_files(self, to_path: str) -> None:
        """
        Check that all of the files contained in the archive are within the
        target directory.


        >>> from pprint import pprint
        >>> class Bunch: pass
        >>> import psef
        >>> psef.archive.app = Bunch()
        >>> psef.archive.app.config = {'MAX_NUMBER_OF_FILES': 100000}
        >>> with Archive.create_from_file(
        ...  'test_data/test_submissions/multiple_dir_archive.tar.gz'
        ... ) as arch:
        ...  print(arch.check_files('/tmp/out'))
        None
        >>> with Archive.create_from_file('test_data/test_submissions/unsafe.tar.gz') as arch:
        ...  arch.check_files('/tmp/out')
        Traceback (most recent call last):
        ...
        psef.archive.UnsafeArchive: Archive member destination is outside the target directory

        :param to_path: The path were the archive should be extracted to.
        :returns: Nothing
        """
        target_path = _safe_join(to_path)

        for member in self.get_members():
            # Don't use `_safe_join` here as we detect unsafe joins here to
            # raise an `UnsafeArchive` exception.
            extract_path = path.normpath(
                path.realpath(path.join(target_path, member.name))
            )

            if not extract_path.startswith(target_path):
                raise UnsafeArchive(
                    'Archive member destination is outside the target'
                    ' directory', member
                )

        if self.__archive.has_unsafe_filetypes():
            raise UnsafeArchive('The archive contains unsafe filetypes')


class _BaseArchive(abc.ABC, t.Generic[TT]):
    def __init__(self, filename: str) -> None:
        self.filename = filename

    @abc.abstractmethod
    def extract_member(
        self, member: ArchiveMemberInfo[TT], to_path: str, size_left: FileSize
    ) -> None:
        """Extract the given filename to the given path.

        :param to_path: The base path to which the member should be
            extracted. This will be example ``'/tmp/tmpdir/``' for the file
            `'dir/file``', not ``'/tmp/tmpdir/dir/``'.
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

    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self._archive = tarfile.open(name=self.filename)

    def extract_member(
        self, member: ArchiveMemberInfo[tarfile.TarInfo], to_path: str,
        _: FileSize
    ) -> None:
        """Extract the given member.

        :param member: The member to extract.
        :param to_path: The location to which it should be extracted.
        """
        # Make sure archives can be deleted later by fixing permissions
        if not member.orig_file.isdir():
            member.orig_file.mode = 0o600

        # We don't need to use ``size_left`` as our tar impl. will never read
        # more than tarinfo object specifies as its size.
        self._archive.extract(member.orig_file, to_path)

    def get_members(self) -> t.Iterable[ArchiveMemberInfo[tarfile.TarInfo]]:
        """Get all members from this tar archive.

        .. note::

            Only members returned by this function will be extracted. This
            function can therefore be used to filter out some files, like
            sparse files. Files that are symlinks should be kept, as special
            error handling is in place for such files.

        >>> from pprint import pprint
        >>> zp = _TarArchive('test_data/test_submissions/multiple_dir_archive.tar.gz')
        >>> print([dataclasses.astuple(i) for i in sorted(zp.get_members())])
        [('dir/', True, ..., ...), \
('dir/single_file_work', False, ..., ...), \
('dir/single_file_work_copy', False, ..., ...), \
('dir2/', True, ..., ...), \
('dir2/single_file_work', False, ..., ...), \
('dir2/single_file_work_copy', False, ..., ...)]
        >>> zp = _TarArchive('test_data/test_submissions/deheading_dir_archive.tar.gz')
        >>> print([dataclasses.astuple(i) for i in sorted(zp.get_members())])
        [('dir/', True, ..., ...), \
('dir/dir2/', True, ..., ...), \
('dir/dir2/single_file_work', False, ..., ...), \
('dir/dir2/single_file_work_copy', False, ..., ...)]
        """
        for member in self._archive.getmembers():
            if not self._member_is_safe(member):
                continue

            name = member.name
            if member.isdir():
                name += '/'
            yield ArchiveMemberInfo(
                name=name,
                is_dir=member.isdir(),
                size=FileSize(member.size),
                orig_file=member,
            )

    @staticmethod
    def _member_is_safe(member: tarfile.TarInfo) -> bool:
        return (
            member.isfile() or member.isdir() or member.issym() or
            member.islnk()
        )

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
    seen_dirs: t.Set[str] = set()
    for member in archive_files:
        name = member.filename
        cur_is_dir = name[-1] == '/'
        name.rstrip('/')

        while name and name not in seen_dirs:
            name, tail = path.split(name)
            if name:
                cur_path = '{}/{}'.format(name, tail)
            else:
                cur_path = tail

            seen_dirs.add(cur_path)

            if cur_is_dir:
                cur_path += '/'

            if cur_is_dir:
                yield ArchiveMemberInfo(
                    name=cur_path,
                    is_dir=cur_is_dir,
                    orig_file=member,
                    size=FileSize(0),
                )
            elif isinstance(member, zipfile.ZipInfo):
                yield ArchiveMemberInfo(
                    name=cur_path,
                    is_dir=False,
                    orig_file=member,
                    size=FileSize(member.file_size),
                )
            elif isinstance(member, py7zlib.ArchiveFile):
                yield ArchiveMemberInfo(
                    name=cur_path,
                    is_dir=False,
                    orig_file=member,
                    size=FileSize(member.size),
                )
            cur_is_dir = True


@_archive_handlers.register('.zip')
class _ZipArchive(_BaseArchive[zipfile.ZipInfo]):  # pylint: disable=unsubscriptable-object
    def close(self) -> None:
        self._archive.close()

    def has_unsafe_filetypes(self) -> bool:  # pylint: disable=no-self-use
        return False

    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self._archive = zipfile.ZipFile(self.filename)

    def extract_member(
        self, member: ArchiveMemberInfo[zipfile.ZipInfo], to_path: str,
        size_left: FileSize
    ) -> None:
        """Extract the given member.

        :param member: The member to extract.
        :param to_path: The location to which it should be extracted.
        """
        dst_path = _safe_join(to_path, member.name)

        with open(dst_path,
                  'wb') as dst, self._archive.open(member.orig_file) as src:
            limited_copy(src, dst, size_left)

    def get_members(self) -> t.Iterable[ArchiveMemberInfo[zipfile.ZipInfo]]:
        """Get all members from this zip archive.

        >>> zp = _ZipArchive('test_data/test_submissions/multiple_dir_archive.zip')
        >>> print([dataclasses.astuple(i) for i in sorted(zp.get_members())])
        [('dir/', True, ..., ...), \
('dir/single_file_work', False, ..., ...), \
('dir/single_file_work_copy', False, ..., ...), \
('dir2/', True, ..., ...), \
('dir2/single_file_work', False, ..., ...), \
('dir2/single_file_work_copy', False, ..., ...)]
        >>> zp = _ZipArchive('test_data/test_submissions/deheading_dir_archive.zip')
        >>> print([dataclasses.astuple(i) for i in sorted(zp.get_members())])
        [('dir/', True, ..., ...), \
('dir/dir2/', True, ..., ...), \
('dir/dir2/single_file_work', False, ..., ...), \
('dir/dir2/single_file_work_copy', False, ..., ...)]
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
        self._fp.close()

    def has_unsafe_filetypes(self) -> bool:  # pylint: disable=no-self-use
        return False

    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self._fp = open(filename, 'rb')
        self._archive = py7zlib.Archive7z(self._fp)

    def extract_member(  # pylint: disable=no-self-use
        self, member: ArchiveMemberInfo[py7zlib.ArchiveFile], to_path: str,
        _: FileSize
    ) -> None:
        """Extract the given member.

        :param member: The member to extract.
        :param to_path: The location to which it should be extracted.
        """
        with open(_safe_join(to_path, member.name), 'wb') as f:
            # We cannot provide a maximum to read to this method...
            f.write(member.orig_file.read())

    def get_members(self
                    ) -> t.Iterable[ArchiveMemberInfo[py7zlib.ArchiveFile]]:
        """Get all members from this 7zip archive.

        >>> zp = _7ZipArchive('test_data/test_submissions/multiple_dir_archive.7z')
        >>> print([(i.name, i.is_dir) for i in sorted(zp.get_members())])
        [('dir/', True), \
('dir/single_file_work', False), \
('dir/single_file_work_copy', False), \
('dir2/', True), \
('dir2/single_file_work', False), \
('dir2/single_file_work_copy', False)]
        >>> zp = _7ZipArchive('test_data/test_submissions/deheading_dir_archive.7z')
        >>> print([(i.name, i.is_dir) for i in sorted(zp.get_members())])
        [('dir/', True), \
('dir/dir2/', True), \
('dir/dir2/single_file_work', False), \
('dir/dir2/single_file_work_copy', False)]
        """
        yield from _get_members_of_archives(self._archive.getmembers())

    def has_less_items_than(self, max_items: int) -> bool:
        """Check if this archive has less than a given amount of members.

        :param max_items: The amount to check for.
        """
        # It is not possible to get the number of items in the zipfile without
        # reading them all, which is done on the ``__init__`` function.
        return len(self._archive.getmembers()) < max_items
