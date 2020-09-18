"""This module defines a File.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import enum
import uuid
import shutil
import typing as t
from abc import abstractmethod
from collections import defaultdict

import structlog
from flask import current_app
from sqlalchemy import event
from sqlalchemy_utils import UUIDType
from typing_extensions import TypedDict

import psef
from cg_enum import CGEnum
from cg_dt_utils import DatetimeWithTimezone
from cg_typing_extensions import make_typed_dict_extender
from cg_sqlalchemy_helpers import hybrid_property
from cg_sqlalchemy_helpers.types import (
    MyQuery, ColumnProxy, ImmutableColumnProxy
)
from cg_sqlalchemy_helpers.mixins import TimestampMixin

from . import Base, db
from . import work as work_models
from .. import auth, helpers
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

    # The given name of the file.
    name = db.Column('name', db.Unicode, nullable=False)

    # This is the filename for the actual file on the disk. This is probably a
    # randomly generated uuid.
    filename = db.Column('filename', db.Unicode, nullable=True)

    @abstractmethod
    def get_id(self) -> T:
        """Get the id of this file.
        """
        raise NotImplementedError

    is_directory: ImmutableColumnProxy[bool]

    def open(self) -> t.BinaryIO:
        """Open this file.

        This file checks if this file can be opened.

        :returns: The contents of the file with newlines.
        """
        if self.is_directory:
            raise APIException(
                'Cannot display this file as it is a directory.',
                f'The selected file with id {self.get_id()} is a directory.',
                APICodes.OBJECT_WRONG_TYPE, 400
            )

        filename = self.get_diskname()
        if os.path.islink(filename):  # pragma: no cover
            # This should not be possible as we replace symlinks with regular
            # files on submission.
            logger.error(
                'Symlink found in uploads directory',
                filename=filename,
            )
            raise APIException(
                f'This file is a symlink to `{os.readlink(filename)}`.',
                f'The file {self.get_id()} is a symlink',
                APICodes.INVALID_STATE, 410
            )
        return open(filename, 'rb')

    def delete_from_disk(self) -> None:
        """Delete the file from disk if it is not a directory.

        >>> import os
        >>> f = FileMixin()
        >>> f.filename = 'NON_EXISTING'
        >>> f.get_diskname = lambda: f.filename
        >>> f.delete_from_disk() is None
        True
        >>> open('new_file_name', 'w').close()
        >>> f.filename = 'new_file_name'
        >>> os.path.isfile(f.filename)
        True
        >>> f.delete_from_disk()
        >>> os.path.isfile(f.filename)
        False

        :returns: Nothing.
        """
        try:
            os.remove(self.get_diskname())
        except (AssertionError, FileNotFoundError):
            pass

    def get_diskname(self) -> str:
        """Get the absolute path on the disk for this file.

        :returns: The absolute path.
        """
        assert self.filename
        assert not self.is_directory

        return psef.files.safe_join(
            current_app.config['UPLOAD_DIR'], self.filename
        )

    class AsJSON(TypedDict):
        #: The id of this file
        id: str
        #: The local name of this file, this does **not** include any parent
        #: directory names, nor does it include trailing slashes for directories.
        name: str

    def __to_json__(self) -> AsJSON:
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

    if t.TYPE_CHECKING:  # pragma: no cover
        # pylint: disable=unused-argument
        def __init__(
            self,
            name: str,
            parent: t.Optional['NestedFileMixin[T]'],
            is_directory: bool,
            filename: t.Optional[str] = None,
            **extra_opts: object,
        ) -> None:
            ...

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
        new_top = cls(
            is_directory=True,
            name=tree.name,
            parent=top,
            **creation_opts,
        )

        for child in tree.values:
            if isinstance(child, psef.files.ExtractFileTreeDirectory):
                cls.create_from_extract_directory(
                    child, new_top, creation_opts
                )
            elif isinstance(child, psef.files.ExtractFileTreeFile):
                cls(
                    name=child.name,
                    filename=child.disk_name,
                    is_directory=False,
                    parent=new_top,
                    **creation_opts,
                )
            else:
                # The above checks are exhaustive, so this cannot happen
                assert False
        return new_top


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

    def get_diskname(self) -> str:
        """Get the absolute path on the disk for this file.

        :returns: The absolute path.
        :raises AssertionError: If this file is deleted.
        """
        assert not self._deleted
        return super().get_diskname()

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

    def list_contents(
        self,
        exclude: FileOwner,
    ) -> 'psef.files.FileTree[int]':
        """List the basic file info and the info of its children.

        :param exclude: The file owner to exclude from the tree.

        :returns: A :class:`psef.files.FileTree` object where the given file is
            the root object.
        """
        cache = self.work.get_file_children_mapping(exclude)
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

    class AsJSON(FileMixin.AsJSON, TypedDict):
        #: Is this file a directory or a normal file.
        is_directory: bool

    AsJSON.__cg_extends__ = FileMixin.AsJSON  # type: ignore

    def __to_json__(self) -> AsJSON:
        """Creates a JSON serializable representation of this object.
        :returns: A object as described above.
        """
        return make_typed_dict_extender(super().__to_json__(), File.AsJSON)(
            is_directory=self.is_directory,
        )


class AutoTestFixture(Base, FileMixin[int], TimestampMixin):
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

    class AsJSON(FileMixin.AsJSON, TypedDict):
        #: Is this fixture hidden.
        hidden: bool

    AsJSON.__cg_extends__ = FileMixin.AsJSON  # type: ignore

    def __to_json__(self) -> AsJSON:
        return make_typed_dict_extender(
            super().__to_json__(), AutoTestFixture.AsJSON
        )(hidden=self.hidden)

    def copy(self) -> 'AutoTestFixture':
        """Copy this AutoTest fixture.

        :returns: The copied AutoTest fixture.

        .. note::

            The connected file is only copied after this request has finished,
            so there is a very small period of time where this fixture is
            committed to the database, but where it does not have an underlying
            file yet.
        """
        path, filename = psef.files.random_file_path()
        old_path = self.get_diskname()
        helpers.callback_after_this_request(
            lambda: shutil.copy(old_path, path)
        )

        return AutoTestFixture(
            hidden=self.hidden,
            name=self.name,
            filename=filename,
        )


class AutoTestOutputFile(Base, NestedFileMixin[uuid.UUID], TimestampMixin):
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
        cache: t.Mapping[t.Optional[uuid.UUID], t.
                         List[AutoTestOutputFile]] = defaultdict(list)

        for f in AutoTestOutputFile.query.filter_by(
            auto_test_result_id=self.auto_test_result_id,
            auto_test_suite_id=self.auto_test_suite_id
        ).order_by(AutoTestOutputFile.name):
            cache[f.parent_id].append(f)

        return self._inner_list_contents(cache)


@event.listens_for(AutoTestOutputFile, 'after_delete')
def _receive_after_delete(
    _: object, __: object, target: AutoTestOutputFile
) -> None:
    """Listen for the 'after_delete' event"""
    helpers.callback_after_this_request(target.delete_from_disk)
