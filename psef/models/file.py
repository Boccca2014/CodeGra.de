"""This module defines a File.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import enum
import uuid
import typing as t
from abc import abstractmethod
from collections import defaultdict

import structlog
from sqlalchemy import event
from sqlalchemy_utils import UUIDType
from typing_extensions import Literal

import psef
import cg_maybe
import cg_flask_helpers
import cg_object_storage
from cg_enum import CGEnum
from cg_dt_utils import DatetimeWithTimezone
from cg_sqlalchemy_helpers import expression, hybrid_property
from cg_sqlalchemy_helpers.types import (
    MyQuery, ColumnProxy, FilterColumn, ImmutableColumnProxy
)
from cg_sqlalchemy_helpers.mixins import TimestampMixin

from . import Base, db
from . import work as work_models
from .. import auth, helpers, current_app
from ..exceptions import APICodes, APIException
from ..permissions import CoursePermission

logger = structlog.get_logger()
T = t.TypeVar('T', covariant=True)


@enum.unique
class FileOwner(CGEnum):
    """Describes to which version of a submission (student's submission or
    teacher's revision) a file belongs. When a student adds or changes a file
    after the deadline for the assignment has passed, the original file's owner
    is set `teacher` and the new file's to `student`.

    :param student: The file is in the student's submission, but changed in the
        teacher's revision.
    :param teacher: The inverse of `student`. The file is added or changed in
        the teacher's revision.
    :param both: The file is not changed in the teacher's revision and belongs
        to both versions.
    """

    student = 1
    teacher = 2
    both = 3


class FileMixin(t.Generic[T]):
    """A mixin for representing a file in the database.
    """

    @t.overload
    def __init__(
        self,
        name: str,
        *,
        is_directory: Literal[True],
        backing_file: None = None,
        **extra_opts: object,
    ) -> None:
        ...

    @t.overload
    def __init__(
        self,
        name: str,
        backing_file: cg_object_storage.File,
        *,
        is_directory: Literal[False] = False,
        **extra_opts: object,
    ) -> None:
        ...

    def __init__(
        self,
        name: str,
        backing_file: t.Optional[cg_object_storage.File] = None,
        **kwargs: t.Any,
    ) -> None:
        filename = None
        if backing_file is not None:
            filename = backing_file.name

        super().__init__(  # type: ignore
            name=name,
            _filename=filename,
            **kwargs,
        )

    # The given name of the file.
    name = db.Column('name', db.Unicode, nullable=False)

    # This is the filename for the actual file on the disk. This is probably a
    # randomly generated uuid.
    _filename = db.Column('filename', db.Unicode, nullable=True)

    @abstractmethod
    def get_id(self) -> T:
        """Get the id of this file.
        """
        raise NotImplementedError

    is_directory: ImmutableColumnProxy[bool]

    @property
    def backing_file(self) -> cg_maybe.Maybe[cg_object_storage.File]:
        """Maybe get the backing file for this file.

        This will return ``Nothing`` for directories.
        """
        if self._filename is None or self.is_directory:
            return cg_maybe.Nothing
        return current_app.file_storage.get(self._filename)

    @property
    def unwrapped_backing_file(self) -> cg_object_storage.File:
        """Get the backing file, or raise an exception if it cannot be found.

        :raises APIException: If the ``backing_file`` is ``Nothing`` or if it
            no longer exists.
        """
        backing_file = self.backing_file
        if backing_file.is_nothing:
            raise APIException(
                'Cannot display this file as it is a directory.',
                f'The selected file with id {self.get_id()} is a directory.',
                APICodes.OBJECT_WRONG_TYPE, 400
            )

        return backing_file.value

    def update_backing_file(
        self, new_file: cg_object_storage.File, *, delete: bool = False
    ) -> None:
        """Replace the backing file of this ``File``.

        :param new_file: The new backing file for this row.
        :param delete: If ``True`` we will delete the old file at the end of
            the request.
        :raises AssertionError: When called on a directory.
        """
        if self.is_directory:  # pragma: no cover
            raise AssertionError('Cannot set file of directory')
        if delete:
            cg_flask_helpers.callback_after_this_request(self._get_deleter())

        self._filename = new_file.name

    def open(self) -> t.IO[bytes]:
        """Open this file.

        This file checks if this file can be opened.

        :returns: The contents of the file with newlines.
        """
        backing_file = self.unwrapped_backing_file

        return backing_file.open()

    def _get_deleter(self) -> t.Callable[[], None]:
        backing = self.backing_file

        def make_deleter(backing: cg_object_storage.File
                         ) -> t.Callable[[], None]:
            def callback() -> None:
                try:
                    backing.delete()
                except (AssertionError, FileNotFoundError):  # pragma: no cover
                    pass

            return callback

        return backing.map(make_deleter).or_default(lambda: None)

    def delete_from_disk(self) -> None:
        """Delete the file from disk if it is not a directory.

        :returns: Nothing.
        """
        self._get_deleter()()

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': str(self.get_id()),
            'name': self.name,
        }

    def _inner_list_contents(
        self,
        cache: t.Mapping[t.Optional[T], t.Sequence['FileMixin[T]']],
    ) -> 'psef.files.FileTree[T]':
        entries = None
        if self.is_directory:
            entries = [
                c._inner_list_contents(cache)  # pylint: disable=protected-access
                for c in cache[self.get_id()]
            ]
        return psef.files.FileTree(
            name=self.name, id=self.get_id(), entries=entries
        )


NFM_T = t.TypeVar('NFM_T', bound='NestedFileMixin')  # pylint: disable=invalid-name

LiteralTrue: Literal[True] = True
LiteralFalse: Literal[False] = False


class NestedFileMixin(FileMixin[T]):
    """A mixin representing nested files, i.e. a structure of directories where
    the children can be either normal files or directories again.

    This mixin should be used by database tables, not for intermediate
    representation of a directory.
    """
    modification_date = db.Column(
        'modification_date',
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False,
    )

    @abstractmethod
    def get_id(self) -> T:
        """Get the id of this file.
        """
        raise NotImplementedError

    @t.overload
    def __init__(
        self,
        name: str,
        parent: t.Optional['NestedFileMixin[T]'],
        is_directory: Literal[True],
        backing_file: None,
        **extra_opts: object,
    ) -> None:
        ...

    @t.overload
    def __init__(
        self: NFM_T,
        name: str,
        parent: NFM_T,
        is_directory: Literal[False],
        backing_file: cg_object_storage.File,
        **extra_opts: object,
    ) -> None:
        ...

    def __init__(
        self,
        name: str,
        parent: t.Any,
        is_directory: t.Any,
        backing_file: t.Any,
        **extra_opts: object,
    ) -> None:
        super().__init__(
            name=name,
            parent=parent,
            is_directory=is_directory,
            backing_file=backing_file,
            **extra_opts,
        )

    # The id of the parent.
    parent_id: ImmutableColumnProxy[t.Optional[T]]

    # The parent of this file. If ``None`` this file has no parent, i.e. it is
    # a toplevel directory/file.
    parent: ImmutableColumnProxy[t.Optional['NestedFileMixin[T]']]

    @classmethod
    def create_from_extract_directory(
        cls: 't.Type[NFM_T]',
        tree: 'psef.files.ExtractFileTreeDirectory',
        top: t.Optional['NFM_T'],
        creation_opts: t.Dict[str, t.Any],
    ) -> 'NFM_T':
        """Add the given tree to the session with top as parent.

        :param tree: The file tree as described by
                          :py:func:`psef.files.rename_directory_structure`
        :param top: The parent file
        :returns: Nothing
        """
        new_top: NFM_T = cls(  # type: ignore[abstract]
            name=tree.name,
            parent=top,
            is_directory=LiteralTrue,
            backing_file=None,
            **creation_opts,
        )

        for child in tree.values:
            if isinstance(child, psef.files.ExtractFileTreeDirectory):
                cls.create_from_extract_directory(
                    child, new_top, creation_opts
                )
            elif isinstance(child, psef.files.ExtractFileTreeFile):
                cls(  # type: ignore[abstract]
                    name=child.name,
                    backing_file=child.backing_file,
                    is_directory=LiteralFalse,
                    parent=new_top,
                    **creation_opts,
                )
            else:
                # The above checks are exhaustive, so this cannot happen
                assert False
        return new_top

    @classmethod
    def _make_cache(cls: t.Type['NFM_T'], query_filter: FilterColumn
                    ) -> t.Mapping[t.Optional[t.Any], t.Sequence['NFM_T']]:
        cache = defaultdict(list)
        query: MyQuery[NFM_T] = cls.query  # type: ignore[attr-defined]
        all_files = query.filter(query_filter).order_by(cls.name).all()
        # We sort in Python as this increases consistency between different
        # server platforms, Python also has better defaults.
        # TODO: Investigate if sorting in the database first and sorting in
        # Python after is faster, as sorting in the database should be faster
        # overal and sorting an already sorted list in Python is really fast.
        all_files.sort(key=lambda el: el.name.lower())
        for f in all_files:
            cache[f.parent_id].append(f)

        return cache

    @classmethod
    def restore_directory_structure(
        cls: t.Type['NestedFileMixin[T]'],
        parent: str,
        cache: t.Mapping[t.Optional[T], t.Sequence['NestedFileMixin[T]']],
    ) -> 'psef.files.FileTree[T]':
        """Restore the directory structure for this class.
        """
        return cache[None][0]._restore_directory_structure(parent, cache)  # pylint: disable=protected-access

    def _restore_directory_structure(
        self: 'NestedFileMixin[T]',
        parent: str,
        cache: t.Mapping[t.Optional[T], t.Sequence['NestedFileMixin[T]']],
    ) -> 'psef.files.FileTree[T]':
        FileTree = psef.files.FileTree

        out = psef.files.safe_join(parent, self.name)
        backing_file = self.backing_file
        if backing_file.is_nothing:
            assert self.is_directory
            os.mkdir(out)

            subtree = [
                child._restore_directory_structure(out, cache)  # pylint: disable=protected-access
                for child in cache[self.get_id()]
            ]
            return FileTree(name=self.name, id=self.get_id(), entries=subtree)
        else:  # this is a file
            backing_file.value.save_to_disk(out)
            return FileTree(name=self.name, id=self.get_id(), entries=None)


class File(NestedFileMixin[int], Base):
    """
    This object describes a file or directory that stored is stored on the
    server.

    Files are always connected to :class:`.work_models.Work` objects. A
    directory file does not physically exist but is stored only in the database
    to preserve the submitted work structure. Each submission should have a
    single top level file. Each other file in a submission should be directly
    or indirectly connected to this file via the parent attribute.
    """
    __tablename__ = "File"

    id = db.Column('id', db.Integer, primary_key=True)

    _deleted = db.Column(
        'deleted',
        db.Boolean,
        default=False,
        nullable=False,
        server_default='false'
    )

    def get_id(self) -> int:
        return self.id

    work_id = db.Column(
        'Work_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
    )

    fileowner = db.Column(
        'fileowner',
        db.Enum(FileOwner),
        default=FileOwner.both,
        nullable=False
    )

    is_directory = db.Column('is_directory', db.Boolean, nullable=False)
    parent_id = db.Column('parent_id', db.Integer, db.ForeignKey('File.id'))

    # This variable is generated from the backref from the parent
    children: MyQuery["File"]

    parent = db.relationship(
        lambda: File,
        remote_side=[id],
        backref=db.backref('children', lazy='dynamic'),
    )

    work = db.relationship(
        lambda: work_models.Work,
        foreign_keys=work_id,
    )

    @property
    def deleted(self) -> bool:
        """Should this file be considered deleted.

        :returns: ``True`` if either this file is deleted, or if the
            :class:`.work_models.Work` of this file should be considered
            deleted.
        """
        return self._deleted or self.work.deleted

    @hybrid_property
    def self_deleted(self) -> bool:
        """Is this file deleted.

        .. warning::

            This only checks if this file is deleted, to check if the file
            should be considered as deleted, use the ``deleted`` property,
            which also checks if the :class:`.work_models.Work` of this file is
            deleted. Really you should only use this property in queries.
        """
        return self._deleted

    def delete(self) -> None:
        self._deleted = True

    @staticmethod
    def get_exclude_owner(owner: t.Optional[str], course_id: int) -> FileOwner:
        """Get the :class:`.FileOwner` the current user does not want to see
        files for.

        The result will be decided like this, if the given str is not
        `student`, `teacher` or `auto` the result will be `FileOwner.teacher`.
        If the str is `student`, the result will be `FileOwner.teacher`, vica
        versa for `teacher` as input. If the input is auto `student` will be
        returned if the currently logged in user is a teacher, otherwise it
        will be `student`.

        :param owner: The owner that was given in the `GET` paramater.
        :param course_id: The course for which the files are requested.
        :returns: The object determined as described above.
        """
        auth.ensure_logged_in()

        teacher, student = FileOwner.teacher, FileOwner.student
        if owner == 'student':
            return teacher
        elif owner == 'teacher':
            return student
        elif owner == 'auto':
            if psef.current_user.has_permission(
                CoursePermission.can_edit_others_work, course_id
            ):
                return student
            else:
                return teacher
        else:
            return teacher

    def get_path(self) -> str:
        return '/'.join(self.get_path_list())

    def get_path_list(self) -> t.List[str]:
        """Get the complete path of this file as a list.

        :returns: The path of the file as a list, without the topmost ancestor
            directory.
        """
        if self.parent is None:
            return []
        upper = self.parent.get_path_list()
        upper.append(self.name)
        return upper

    @classmethod
    def make_cache(
        cls,
        work: 'psef.models.Work',
        exclude: FileOwner = FileOwner.teacher,
    ) -> t.Mapping[t.Optional[int], t.Sequence['File']]:
        """Make a file cache object for the given work without files owned by
        ``exclude``.

        :param work: The work for which you want to create a cache object.
        :param exclude: Files with this value as owner will not be included in
            the resulting cache.
        """
        return cls._make_cache(
            expression.and_(
                cls.work == work,
                cls.fileowner != exclude,
                ~cls.self_deleted,
            )
        )

    def list_contents(self, exclude: FileOwner) -> 'psef.files.FileTree[int]':
        """List the basic file info and the info of its children.

        :param exclude: The file owner to exclude from the tree.

        :returns: A :class:`psef.files.FileTree` object where this file is the
                  root object.
        """
        cache = self.make_cache(self.work, exclude)
        return self._inner_list_contents(cache)

    def rename_code(
        self,
        new_name: str,
        new_parent: 'File',
        exclude_owner: FileOwner,
    ) -> None:
        """Rename the this file to the given new name.

        :param new_name: The new name to be given to the given file.
        :param new_parent: The new parent of this file.
        :param exclude_owner: The owner to exclude while searching for
            collisions.
        :returns: Nothing.

        :raises APIException: If renaming would result in a naming collision
            (INVALID_STATE).
        """
        if db.session.query(
            new_parent.children.filter_by(name=new_name).filter(
                File.fileowner != exclude_owner,
                ~File.self_deleted,
            ).exists(),
        ).scalar():
            raise APIException(
                'This file already exists within this directory',
                f'The file "{new_parent.id}" has '
                f'a child with the name "{new_name}"', APICodes.INVALID_STATE,
                400
            )

        self.name = new_name

    def __to_json__(self) -> t.Mapping[str, object]:
        """Creates a JSON serializable representation of this object.


        This object will look like this:

        .. code:: python

            {
                'name': str, # The name of the file or directory.
                'id': str, # The id of this file.
                'is_directory': bool, # Is this file a directory.
            }

        :returns: A object as described above.
        """
        return {
            **super().__to_json__(),
            'is_directory': self.is_directory,
        }


class AutoTestFixture(FileMixin[int], TimestampMixin, Base):
    """This class represents a single fixture for an AutoTest configuration.
    """
    __tablename__ = 'AutoTestFixture'

    id = db.Column('id', db.Integer, primary_key=True)

    def get_id(self) -> int:
        return self.id

    auto_test_id = db.Column(
        'auto_test_id',
        db.Integer,
        db.ForeignKey('AutoTest.id', ondelete='CASCADE'),
        nullable=False,
    )

    def delete_fixture(self) -> None:
        """Delete the this fixture.

        This function deletes the fixture from the database and after the
        request the saved file is also deleted.
        """
        db.session.delete(self)
        psef.helpers.callback_after_this_request(self.delete_from_disk)

    @hybrid_property
    def is_directory(self) -> bool:  # pylint: disable=no-self-use
        """An AutoTest fixture is never a directory, as we only allow file
            uploads.
        """
        return False

    hidden = db.Column('hidden', db.Boolean, nullable=False, default=True)

    auto_test = db.relationship(
        lambda: psef.models.AutoTest,
        foreign_keys=auto_test_id,
        back_populates='fixtures',
        lazy='joined',
        innerjoin=True,
    )

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            **super().__to_json__(),
            'hidden': self.hidden,
        }

    def copy(self, putter: cg_object_storage.Putter) -> 'AutoTestFixture':
        """Copy this AutoTest fixture.

        :param putter: The putter used to copy the underlying file.
        :returns: The copied AutoTest fixture.
        """
        new_file = self.unwrapped_backing_file.copy(putter)

        return AutoTestFixture(
            hidden=self.hidden,
            name=self.name,
            backing_file=new_file,
        )


class AutoTestOutputFile(NestedFileMixin[uuid.UUID], TimestampMixin, Base):
    """This class represents an output file from an AutoTest run.

    The output files are connected to both a
    :class:`.psef.models.AutoTestResult` and a
    :class:`.psef.models.AutoTestSuite`.
    """

    id = db.Column('id', UUIDType, primary_key=True, default=uuid.uuid4)

    def get_id(self) -> T:
        return self.id

    is_directory = db.Column('is_directory', db.Boolean, nullable=False)
    parent_id: ColumnProxy[t.Optional[uuid.UUID]] = db.Column(
        'parent_id', UUIDType, db.ForeignKey('auto_test_output_file.id')
    )

    auto_test_result_id = db.Column(
        'auto_test_result_id',
        db.Integer,
        db.ForeignKey('AutoTestResult.id'),
        nullable=False,
    )

    result = db.relationship(
        lambda: psef.models.AutoTestResult,
        foreign_keys=auto_test_result_id,
        innerjoin=True,
        backref=db.backref('files', lazy='dynamic', cascade='all,delete')
    )

    auto_test_suite_id = db.Column(
        'auto_test_suite_id',
        db.Integer,
        db.ForeignKey('AutoTestSuite.id'),
        nullable=False
    )

    suite = db.relationship(
        lambda: psef.models.AutoTestSuite,
        foreign_keys=auto_test_suite_id,
        innerjoin=True,
    )

    # This variable is generated from the backref from the parent
    children: MyQuery["AutoTestOutputFile"]

    parent = db.relationship(
        lambda: psef.models.AutoTestOutputFile,
        remote_side=[id],
        backref=db.backref('children', lazy='dynamic')
    )

    def list_contents(self) -> 'psef.files.FileTree[uuid.UUID]':
        """List the basic file info and the info of its children.
        """
        cls = type(self)
        cache = self._make_cache(
            expression.and_(
                cls.auto_test_result_id == self.auto_test_result_id,
                cls.auto_test_suite_id == self.auto_test_suite_id
            )
        )

        return self._inner_list_contents(cache)


@event.listens_for(AutoTestOutputFile, 'after_delete')
def _receive_after_delete(
    _: object, __: object, target: AutoTestOutputFile
) -> None:
    """Listen for the 'after_delete' event"""
    helpers.callback_after_this_request(target.delete_from_disk)


class PlagiarismBaseCodeFile(NestedFileMixin[uuid.UUID], Base, TimestampMixin):
    """This object describes a file or directory that stored is stored as base
    code for a plagiarism run.
    """
    id = db.Column('id', UUIDType, primary_key=True, default=uuid.uuid4)

    def get_id(self) -> uuid.UUID:
        return self.id

    plagiarism_run_id = db.Column(
        'plagiarism_run_id',
        db.Integer,
        db.ForeignKey('PlagiarismRun.id', ondelete='CASCADE'),
        nullable=False,
    )

    is_directory = db.Column('is_directory', db.Boolean, nullable=False)
    parent_id = db.Column(
        'parent_id', UUIDType, db.ForeignKey('plagiarism_base_code_file.id')
    )

    # This variable is generated from the backref from the parent
    children: MyQuery["File"]

    parent = db.relationship(
        lambda: PlagiarismBaseCodeFile,
        remote_side=[id],
        backref=db.backref('children', lazy='dynamic'),
    )

    plagiarism_run = db.relationship(
        lambda: psef.models.PlagiarismRun,
        foreign_keys=plagiarism_run_id,
    )

    @classmethod
    def make_cache(cls, plagiarism_run: 'psef.models.PlagiarismRun'
                   ) -> t.Mapping[t.Optional[uuid.UUID], t.
                                  Sequence['PlagiarismBaseCodeFile']]:
        """Make a file cache object for the given plagiarism run.

        :param plagiarism_run: The run for which you want to get the cache.
        """
        return cls._make_cache(cls.plagiarism_run == plagiarism_run)
