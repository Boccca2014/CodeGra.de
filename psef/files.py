"""
This module is used for file IO and handling and provides functions for
extracting and abstracting the structures of directories and archives.

SPDX-License-Identifier: AGPL-3.0-only
"""
import io
import os
import re
import sys
import copy
import typing as t
import tarfile
import zipfile
import dataclasses
from collections import Counter, defaultdict

import structlog
from werkzeug.utils import secure_filename
from typing_extensions import Protocol, TypedDict
from werkzeug.datastructures import FileStorage

import psef
import cg_helpers
import psef.models as models
import cg_object_storage
from cg_object_storage import FileSize

from . import app, archive, helpers, blackboard
from .ignore import (
    DeletionType, FileDeletion, IgnoreHandling, SubmissionFilter,
    EmptySubmissionFilter
)
from .exceptions import APICodes, APIWarnings, APIException
from .extract_tree import (
    ExtractFileTree, ExtractFileTreeBase, ExtractFileTreeFile,
    ExtractFileTreeDirectory, ExtractFileTreeSpecialFile
)

if t.TYPE_CHECKING:
    import psef

logger = structlog.get_logger()

# Gestolen van Erik Kooistra
_BB_TXT_FORMAT = re.compile(
    r"(?P<assignment_name>.+)_(?P<student_id>.+?)_attempt_"
    r"(?P<datetime>\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}).txt"
)

SPECIAL_FILES = {
    '.cg-grade',
    '.cg-rubric.md',
    '.cg-feedback',
    '.cg-submission-id',
    '.cg-edit-rubric.md',
    '.cg-edit-rubric.help',
    '.cg-assignment-settings.ini',
    '.cg-assignment-id',
    '.api-socket',
    '.cg-mode',
    '.cg-members',
    '.cg-test-output',
    '.cg-assignee',
    '.cg-linter-feedback',
    '.cg-line-feedback',
    '.cg-overview.csv',
    '.cg-plagiarism',
    '.cg-diff',
    '.cg-student-diff',
    '.cg-teacher-diff',
    '.cg-grade-history',
    '.cg-review',
    '.cg-peer-review',
    '.cg-allesreiniger',
    'cg-size-limit-exceeded',
}

SPECIAL_FILENAMES = {
    '..',
    '.',
    *SPECIAL_FILES,
}


def init_app(_: t.Any) -> None:
    pass


def get_file_size(f: str) -> FileSize:
    return FileSize(max(1, os.path.getsize(f)))


def safe_join(parent: str, *children: str) -> str:
    """Safely join the children to the parent.

    This function makes sure the resulting directory is the parent or a
    subdirectory of the parent.
    """
    res = os.path.normpath(os.path.realpath(os.path.join(parent, *children)))
    assert res.startswith(parent)
    return res


class FileLike(Protocol):
    """This protocol represents some FileLike object with a name.
    """

    @property
    def name(self) -> str:
        """The name of the file.
        """
        raise NotImplementedError

    @name.setter
    def name(self, new_val: str) -> None:
        raise NotImplementedError


def fix_duplicate_filenames(
    files: t.Union[t.Sequence[FileLike], t.Sequence['models.FileMixin[T]']]
) -> t.List[t.Dict[str, str]]:
    """Fix duplicate files in a list of files.

    :param files: The files to check for.
    :returns: A list of renames, each rename is a dictionary with two keys:
        ``old_name``, indicating the old name of the file and ``new_name`` the
        new name of the file. The name property of the renamed file is also
        mutated in-place.
    """
    file_occurrence_lookup: t.Dict[str, t.Dict[str, int]] = defaultdict(
        lambda: {
            'amount': 0,
            'fixed': 0
        },
    )

    for f in files:
        file_occurrence_lookup[f.name]['amount'] += 1

    res = []

    if any(v['amount'] > 1 for v in file_occurrence_lookup.values()):
        for f in files:
            if file_occurrence_lookup[f.name]['fixed'] > 0:
                num = file_occurrence_lookup[f.name]['fixed']
                while f'{f.name} ({num})' in file_occurrence_lookup:
                    num += 1
                file_occurrence_lookup[f.name]['fixed'] = num
                old_name = f.name
                f.name = f'{f.name} ({num})'
                res.append({
                    'old_name': old_name,
                    'new_name': f.name,
                })
                # This isn't really needed (as num always is incremented
                # after this block). However, this is simply an extra
                # safety check.
                file_occurrence_lookup[f.name]['amount'] += 1
            file_occurrence_lookup[f.name]['fixed'] += 1

    return res


def escape_logical_filename(name: str) -> str:
    """Escape a logical filename

    If the name is a special file or the literal string '.' or '..' the string
    '-USER_PROVIDED' is appended to the name.

    .. note::

        A logical filename is the filename as stored in the database and
        displayed to the users, called ``name`` in the database. This is
        different from physical filenames which are the names of the files as
        stored on disk, called ``filename`` in the database.

    >>> logger.warning = lambda *_, **__: True
    >>> helpers.add_warning = lambda *_, **__: True
    >>> escape_logical_filename('.')
    '.-USER_PROVIDED'
    >>> escape_logical_filename('.cg-grade')
    '.cg-grade-USER_PROVIDED'
    >>> escape_logical_filename('.cg-grade-USER_PROVIDED')
    '.cg-grade-USER_PROVIDED-USER_PROVIDED'
    >>> escape_logical_filename('normal file')
    'normal file'
    >>> escape_logical_filename('.bashrc')
    '.bashrc'

    :param name: The original logical filename.
    :returns: An escaped logical filename.
    """
    # Use `startswith` to make sure no collisions can occur.
    if name.startswith(tuple(SPECIAL_FILES)) or name in SPECIAL_FILENAMES:
        new_name = name + '-USER_PROVIDED'
        logger.warning('Invalid filename found', original_filename=name)
        helpers.add_warning(
            f'Invalid filename "{name}" was renamed to "{new_name}"',
            APIWarnings.INVALID_FILENAME
        )
        name = new_name

    if '/' in name:
        name = split_path(name)[0][-1]

    return name


T = t.TypeVar('T')


class FileTree(t.Generic[T]):
    """A class representing a file tree as stored in the database.

    :param name: The logicial name of the file, this is not the name of the
        file on disk.
    :param id: The id of the file in the database.
    :param entries: If not ``None`` this file is a directory, and contains
        these files as direct children.
    """
    __slots__ = ('name', 'id', 'entries')

    def __init__(
        self, name: str, id: T, entries: t.Optional[t.Sequence['FileTree[T]']]
    ) -> None:
        self.name = name
        self.id = id
        self.entries = entries

    class _AsJSONFile(TypedDict):
        #: The id of the file, this can be used to retrieve it later on.
        id: str
        #: The name of the file, this does not include the name of any parents.
        name: str

    class AsJSON(_AsJSONFile, total=False):
        #: The entries in this directory. This is a list that will contain all
        #: children of the directory. This key might not be present, in which
        #: case the file is not a directory.
        entries: t.Sequence['psef.files.FileTree']

    AsJSON.__cg_extends__ = _AsJSONFile  # type: ignore

    def __to_json__(self) -> AsJSON:
        if self.entries:
            return {
                'id': str(self.id),
                'name': self.name,
                'entries': self.entries,
            }
        return {
            'id': str(self.id),
            'name': self.name,
        }


class IgnoredFilesException(APIException):
    """The exception used when a permission check fails.
    """

    def __init__(
        self,
        invalid_files: t.List[FileDeletion],
        filter_version: int,
        original_tree: ExtractFileTree,
        missing_files: t.List[t.Mapping[str, str]],
    ) -> None:
        self.invalid_files: t.List[FileDeletion] = invalid_files
        message = 'The archive contains files that are ignored'
        if missing_files:
            message += ' and it misses required files'
        super().__init__(
            message=f'{message}.',
            description='Some files in the archive matched the ignore file',
            api_code=APICodes.INVALID_FILE_IN_ARCHIVE,
            status_code=400,
            invalid_files=[
                [d.deleted_file.get_full_name(), d.reason]
                for d in self.invalid_files
                if d.deletion_type != DeletionType.leading_directory
            ],
            removed_files=self.invalid_files,
            original_tree=original_tree,
            filter_version=filter_version,
            missing_files=missing_files,
        )


def get_stat_information(file: models.NestedFileMixin[T]
                         ) -> t.Mapping[str, t.Union[bool, str, int]]:
    """Get stat information for a given :class:`.models.File`

    The resulting object will look like this:

    .. code:: python

        {
            'is_directory': bool, # Is the given file a directory
            'modification_date':  int, # When was the file last modified, as
                                       # unix timestamp in utc time.
            'size': int, # The size on disk of the file or 0 if the file is a
                         # directory.
            'id': str, # The id of the given file.
        }

    :param file: The file to get the stat information for.
    :returns: The information as described above.
    """
    mod_date = file.modification_date
    size = file.backing_file.map(lambda f: f.size).or_default(0)

    return {
        'is_directory': file.is_directory,
        'modification_date': round(mod_date.timestamp()),
        'size': size,
        'id': str(file.get_id()),
    }


def get_file_contents(code: models.FileMixin[T]) -> bytes:
    """Get the contents of the given :class:`.models.File`.

    :param code: The file object to read.
    :returns: The contents of the file with newlines.
    """
    with code.open() as codefile:
        return codefile.read()


def search_path_in_filetree(filetree: FileTree[T], path: str) -> T:
    """Search for a path in a filetree.

    >>> def to_ftree(dct):
    ...    entries = None
    ...    if 'entries' in dct:
    ...        entries = [to_ftree(entry) for entry in dct['entries']]
    ...    return FileTree(**{**dct, 'entries': entries})
    >>> filetree = {
    ...    "id": 1,
    ...    "name": "rootdir",
    ...    "entries": [
    ...        {
    ...            "id": 2,
    ...            "name": "file1.txt"
    ...        },
    ...        {
    ...            "id": 3,
    ...            "name": "subdir",
    ...            "entries": [
    ...                {
    ...                    "id": 4,
    ...                    "name": "file2.txt"
    ...                },
    ...                {
    ...                    "id": 5,
    ...                    "name": "file3.txt"
    ...                }
    ...            ],
    ...        },
    ...    ],
    ... }
    ...
    >>> filetree = to_ftree(filetree)
    >>> search_path_in_filetree(filetree, "file1.txt")
    2
    >>> search_path_in_filetree(filetree, "/subdir/")
    3
    >>> search_path_in_filetree(filetree, "/subdir//file2.txt")
    4
    >>> search_path_in_filetree(filetree, "Non existing/path")
    Traceback (most recent call last):
    ...
    KeyError: 'Path (Non existing/path) not in tree'

    :param filetree: The filetree to search.
    :param path: The path the search for.
    :returns: The id of the file associated with the path in the filetree.
    """
    cur = filetree
    for part in path.split('/'):
        if not part:
            continue
        for entry in (cur.entries or []):
            if entry.name == part:
                cur = entry
                break
        else:
            raise KeyError(f'Path ({path}) not in tree')
    return cur.id


def rename_directory_structure(
    rootdir: str,
    putter: cg_object_storage.Putter,
    disk_limit: t.Optional[FileSize] = None,
) -> ExtractFileTreeDirectory:
    """Creates a nested dictionary that represents the folder structure of
    rootdir.

    :param str rootdir: The root directory to rename, files will not be removed

    :returns: An extract filetree that where ``rootdir`` is the root directory.
    """
    directory: t.MutableMapping[str, t.Any] = {}

    rootdir = rootdir.rstrip(os.sep)
    start = rootdir.rfind(os.sep) + 1
    size_left: int = sys.maxsize if disk_limit is None else disk_limit

    for path, _, files in os.walk(rootdir):
        folders = path[start:].split(os.sep)
        subdir = dict.fromkeys(files)

        parent: t.MutableMapping[str, t.Any] = directory
        for folder in folders[:-1]:
            parent = parent[folder]
        parent[folders[-1]] = subdir

    def __to_lists(
        name: str,
        dirs: t.Mapping[str, t.Any],
    ) -> t.List[ExtractFileTreeBase]:
        nonlocal size_left
        res: t.List[ExtractFileTreeBase] = []

        # Sort to make sure we always process items in the same order, so we
        # always error at the same file.
        for key, value in sorted(dirs.items()):
            if value is None:
                path = safe_join(name, key)
                size = get_file_size(path)
                size_left -= size
                if size_left < 0:
                    logger.warning(
                        'File size exceeded',
                        size_left=size_left,
                        exceeding_path=path,
                        size_current_file=size,
                    )
                    break

                copied_file = putter.from_file(path, move=True)
                res.append(
                    ExtractFileTreeFile(name=key, backing_file=copied_file)
                )
            else:
                new_dir = ExtractFileTreeDirectory(name=key)
                for child in __to_lists(safe_join(name, key), value):
                    new_dir.add_child(child)
                res.append(new_dir)

                if size_left < 0:
                    break
        return res

    result_lists = __to_lists(rootdir[:start], directory)
    assert len(result_lists) == 1
    assert isinstance(result_lists[0], ExtractFileTreeDirectory)
    if size_left < 0:
        exceeded_file = putter.from_string(
            'Size limit was exceeded, so some files were not copied\n',
        )
        result_lists[0].add_child(
            ExtractFileTreeSpecialFile(
                name='cg-size-limit-exceeded', backing_file=exceeded_file
            )
        )
    return result_lists[0]


def extract(
    fileobj: FileStorage, filename: str, max_size: FileSize,
    putter: cg_object_storage.Putter
) -> ExtractFileTree:
    """Extracts all files in archive with random name to uploads folder.

    .. warning::

        The returned ExtractFileTree may be empty, i.e. contain only
        directories and no files.

    :param file: The file to extract.
    :param max_size: The maximum size of the extracted archive.
    :returns: A file tree as generated by
        :py:func:`rename_directory_structure`.
    """
    try:
        # Werkzeug implements a fix for
        # https://github.com/python/cpython/pull/3249 which we need.
        with archive.Archive.create_from_fileobj(
            escape_logical_filename(filename), t.cast(t.IO[bytes], fileobj)
        ) as arch:
            result = arch.extract(max_size=max_size, putter=putter)
        return result
    except (
        tarfile.ReadError, zipfile.BadZipFile,
        archive.UnrecognizedArchiveFormat
    ) as exc:
        raise APIException(
            f'The given {filename} could not be extracted',
            "The given archive doesn't seem to be an archive",
            APICodes.INVALID_ARCHIVE,
            400,
        ) from exc
    except (archive.ArchiveTooLarge, archive.FileTooLarge) as exc:
        raise psef.helpers.make_file_too_big_exception(
            max_size,
            single_file=isinstance(exc, archive.FileTooLarge),
        ) from exc
    except archive.UnsafeArchive as e:
        logger.warning('Unsafe archive submitted', exc_info=True)
        raise APIException(
            'The given archive contains invalid or too many files', str(e),
            APICodes.UNSAFE_ARCHIVE, 400
        ) from e


def process_files(
    files: t.Sequence[FileStorage],
    max_size: FileSize,
    force_txt: bool = False,
    ignore_filter: t.Optional[SubmissionFilter] = None,
    handle_ignore: IgnoreHandling = IgnoreHandling.keep,
    putter: cg_object_storage.Putter = None
) -> ExtractFileTree:
    """Process the given files by extracting, moving and saving their tree
    structure.

    :param files: The files to move and extract
    :param max_size: The maximum combined size of all extracted files.
    :param force_txt: Do not extract archive and force all files to be
        considered to be plain text.
    :param ignore_filter: The files and directories that should be ignored.
    :param handle_ignore: Determines how ignored files should be handled.
    :returns: The tree of the files as is described by
        :py:func:`rename_directory_structure`
    """

    def cont(_putter: cg_object_storage.Putter) -> ExtractFileTree:
        return _process_files(
            files=files,
            max_size=max_size,
            force_txt=force_txt,
            ignore_filter=ignore_filter,
            handle_ignore=handle_ignore,
            putter=_putter,
        )

    if putter is None:
        with app.file_storage.putter() as _putter:
            return cont(_putter)
    else:
        return cont(putter)


def _process_files(
    files: t.Sequence[FileStorage],
    max_size: FileSize,
    force_txt: bool,
    ignore_filter: t.Optional[SubmissionFilter],
    handle_ignore: IgnoreHandling,
    putter: cg_object_storage.Putter,
) -> ExtractFileTree:
    if ignore_filter is None:
        ignore_filter = EmptySubmissionFilter()

    if (
        handle_ignore == IgnoreHandling.keep and
        not ignore_filter.can_override_ignore_filter
    ):
        raise APIException(
            'Overriding the ignore filter is not possible for this assignment',
            'The filter disallows overriding it', APICodes.INVALID_PARAM, 400
        )

    def consider_archive(f: FileStorage) -> bool:
        assert f.filename is not None
        return not force_txt and archive.Archive.is_archive(f.filename)

    if len(files) > 1 or not consider_archive(files[0]):
        tree = ExtractFileTree(name='top')
        filename_counter: t.Counter[str] = Counter()
        # We reverse sort on length so that in the case we have two files named
        # `a` and one name `a (1)` the resulting file `a (1)` will be the
        # origin `a (1)`.
        for file in sorted(
            files,
            key=lambda f: len(f.filename or ''),
            reverse=True,
        ):
            assert file.filename is not None
            filename = file.filename

            idx = 0
            while filename_counter[filename] > 0:
                idx += 1
                parts = file.filename.split('.')
                parts[0] += f' ({idx})'
                filename = '.'.join(parts)
            filename_counter[filename] += 1

            if consider_archive(file):
                tree.add_child(
                    extract(file, filename, max_size=max_size, putter=putter)
                )
            else:
                saved_file = putter.from_stream(
                    file.stream, max_size=app.max_single_file_size
                )
                if saved_file.is_nothing:
                    raise helpers.make_file_too_big_exception(
                        app.max_single_file_size, single_file=True
                    )
                tree.add_child(
                    ExtractFileTreeFile(
                        name=filename, backing_file=saved_file.value
                    )
                )

    else:
        tree = extract(
            files[0],
            cg_helpers.handle_none(files[0].filename, 'archive'),
            max_size=max_size,
            putter=putter,
        )

    if not tree.contains_file:
        raise APIException(
            'No files found in archive',
            'No files were in the given archive.',
            APICodes.NO_FILES_SUBMITTED,
            400,
        )

    original_tree = copy.deepcopy(tree)
    tree, total_changes, missing_files = ignore_filter.process_submission(
        tree, handle_ignore
    )
    actual_file_changes = any(
        c.deletion_type != DeletionType.leading_directory
        for c in total_changes
    )
    if missing_files or (
        handle_ignore == IgnoreHandling.error and actual_file_changes
    ):
        raise IgnoredFilesException(
            total_changes,
            ignore_filter.CGIGNORE_VERSION,
            original_tree=original_tree,
            missing_files=missing_files,
        )

    logger.info('Removing files', removed_files=total_changes)

    # It did contain files before deleting, so the deletion caused the tree to
    # be empty.
    if not tree.contains_file:
        raise APIException(
            (
                "All files are ignored by a rule in the assignment's"
                ' ignore file'
            ),
            'No files were in the given archive after filtering.',
            APICodes.NO_FILES_SUBMITTED,
            400,
        )

    tree_size = tree.get_size()
    logger.info('Total size', total_size=tree_size, size=max_size)
    if tree_size > max_size:
        tree.delete()
        raise helpers.make_file_too_big_exception(max_size, single_file=False)

    return tree


def process_blackboard_zip(
    blackboard_zip: FileStorage,
    max_size: FileSize,
) -> t.MutableSequence[t.Tuple[blackboard.SubmissionInfo, ExtractFileTree]]:
    """Process the given :py:mod:`.blackboard` zip file.

    This is done by extracting, moving and saving the tree structure of each
    submission.

    :param file: The blackboard gradebook to import
    :returns: List of tuples (BBInfo, tree)
    """

    def __get_files(info: blackboard.SubmissionInfo) -> t.List[FileStorage]:
        files = []
        for blackboard_file in info.files:
            if isinstance(blackboard_file, blackboard.FileInfo):
                name = blackboard_file.original_name
                bb_file = bb_tree.lookup_direct_child(blackboard_file.name)
                if not isinstance(bb_file, ExtractFileTreeFile):
                    raise AssertionError(
                        'File {} was not a file but instead was {}'.format(
                            blackboard_file.name, bb_file
                        )
                    )
                stream = bb_file.backing_file.open()
            else:
                name = blackboard_file[0]
                stream = io.BytesIO(blackboard_file[1])

            if name == '__WARNING__':
                name = '__WARNING__ (User)'

            files.append(FileStorage(stream=stream, filename=name))
        return files

    with app.file_storage.putter() as putter:
        bb_tree = extract(
            blackboard_zip,
            cg_helpers.handle_none(blackboard_zip.filename, 'bb_zip'),
            max_size=app.max_large_file_size,
            putter=putter,
        )
        info_files = (
            f for f in bb_tree.values if _BB_TXT_FORMAT.match(f.name)
        )
        submissions = []
        for info_file in info_files:
            assert isinstance(info_file, ExtractFileTreeFile)
            with info_file.backing_file.open() as info_fileobj:
                info = blackboard.parse_info_file(info_fileobj)

            try:
                tree = process_files(
                    files=__get_files(info),
                    max_size=max_size,
                    putter=putter,
                )
            # TODO: We catch all exceptions, this should probably be
            # narrowed down, however finding all exception types is
            # difficult.
            except Exception:  # pylint: disable=broad-except
                logger.info('Could not extract files', exc_info=True)
                files = __get_files(info)
                files.append(
                    FileStorage(
                        stream=io.BytesIO(
                            b'Some files could not be extracted!',
                        ),
                        filename='__WARNING__'
                    )
                )
                tree = process_files(
                    files=files,
                    max_size=max_size,
                    force_txt=True,
                    putter=putter
                )

            submissions.append((info, tree))

        if not submissions:
            raise ValueError

    return submissions


def split_path(path: str) -> t.Tuple[t.List[str], bool]:
    """Split a path into an array of parts of a path.

    This functions splits a forward slash separated path into an sequence of
    the directories of this path. If the given path ends with a '/' it returns
    that the given path ends with an directory, otherwise the last part is a
    file, this information is returned as the last part of the returned tuple.

    The given path may contain multiple consecutive forward slashes, these are
    interpreted as a single slash. A leading forward slash is also optional.

    :param path: The forward slash separated path to split.
    :returns: A tuple where the first item is the splitted path and the second
        item is a boolean indicating if the last item of the given path was a
        directory.
    """
    is_dir = path[-1] == '/'

    patharr = [item for item in path.split('/') if item]

    return patharr, is_dir


def replace_symlinks(to_path: str) -> None:
    """Replace symlinks in the given directory with regular files
    containing a notice that the symlink was replaced.

    :param to_path: Directory to scan for symlinks.
    :returns: Nothing
    """
    for parent, _, files in os.walk(to_path):
        for f in files:
            file_path = os.path.join(parent, f)

            if not os.path.islink(file_path):
                assert os.path.isfile(file_path) or os.path.isdir(file_path)
                # This cannot be covered, see:
                # https://bitbucket.org/ned/coveragepy/issues/198/continue-marked-as-not-covered
                continue  # pragma: no cover

            rel_path = os.path.relpath(file_path, to_path)
            link_target = os.readlink(file_path)
            os.unlink(file_path)

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
