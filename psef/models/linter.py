"""This module defines a LinterState.

SPDX-License-Identifier: AGPL-3.0-only
"""

import enum
import uuid
import typing as t

from sqlalchemy import orm

from . import UUID_LENGTH, Base, db, _MyQuery

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from . import assignment
    from .file import File
    from . import work as work_models


@enum.unique
class LinterState(enum.IntEnum):
    """Describes in what state a :class:`.LinterInstance` is.

    :param running: The linter is currently running.
    :param done: The linter has finished without crashing.
    :param crashed: The linter has crashed in some way.
    """
    running: int = 1
    done: int = 2
    crashed: int = 3


class LinterComment(Base):
    """Describes a comment created by a :class:`LinterInstance`.

    Like a :class:`Comment` it is attached to a specific line in a
    :class:`File`.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['LinterComment']] = Base.query
    __tablename__ = "LinterComment"  # type: str
    id: int = db.Column('id', db.Integer, primary_key=True)
    file_id: int = db.Column(
        'File_id',
        db.Integer,
        db.ForeignKey('File.id', ondelete='CASCADE'),
        index=True
    )
    linter_id = db.Column(
        'linter_id', db.Unicode, db.ForeignKey('LinterInstance.id')
    )

    line: int = db.Column('line', db.Integer)
    linter_code: str = db.Column('linter_code', db.Unicode)
    comment: str = db.Column('comment', db.Unicode)

    linter = db.relationship(
        "LinterInstance", back_populates="comments"
    )  # type: 'LinterInstance'
    file: 'File' = db.relationship('File', foreign_keys=file_id)

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'code': self.linter_code,
            'line': self.line,
            'msg': self.comment,
        }


class LinterInstance(Base):
    """Describes the connection between a :class:`assignment.AssignmentLinter`
    and a :class:`work_models.Work`.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['LinterInstance']]
    __tablename__ = 'LinterInstance'
    id: str = db.Column(
        'id', db.String(UUID_LENGTH), nullable=False, primary_key=True
    )
    state: LinterState = db.Column(
        'state',
        db.Enum(LinterState),
        default=LinterState.running,
        nullable=False
    )
    work_id: int = db.Column(
        'Work_id', db.Integer, db.ForeignKey('Work.id', ondelete='CASCADE')
    )
    tester_id: str = db.Column(
        'tester_id', db.Unicode, db.ForeignKey('AssignmentLinter.id')
    )
    stdout: t.Optional[str] = orm.deferred(
        db.Column('stdout', db.Unicode, nullable=True)
    )
    stderr: t.Optional[str] = orm.deferred(
        db.Column('stderr', db.Unicode, nullable=True)
    )
    _error_summary: t.Optional[str] = db.Column(
        'error_summary', db.Unicode, nullable=True
    )

    tester: 'assignment.AssignmentLinter' = db.relationship(
        "AssignmentLinter", back_populates="tests"
    )
    work: 'work_models.Work' = db.relationship('Work', foreign_keys=work_id)

    comments: LinterComment = db.relationship(
        "LinterComment", back_populates="linter", cascade='all,delete'
    )

    @property
    def error_summary(self) -> str:
        """The summary of the error the linter encountered.

        :returns: A summary of the error the linter encountered. This will
            probably be empty when the state is not ``crashed``.
        """
        if self._error_summary:
            return self._error_summary
        elif self.state == LinterState.crashed:
            return 'The linter crashed for some unknown reason.'
        else:
            return ''

    @error_summary.setter
    def error_summary(self, new_value: str) -> None:
        self._error_summary = new_value

    def __init__(
        self, work: 'work_models.Work', tester: 'assignment.AssignmentLinter'
    ) -> None:
        super().__init__(work=work, tester=tester)

        # Find a unique id
        new_id = str(uuid.uuid4())
        while db.session.query(
            LinterInstance.query.filter(LinterInstance.id == new_id).exists()
        ).scalar():  # pragma: no cover
            new_id = str(uuid.uuid4())

        self.id = new_id

    def __extended_to_json__(self) -> t.Mapping[str, object]:
        """Creates an extended JSON serializable representation of this linter
        instance.

        This object will look like this:

        .. code:: python

            {
                'stdout': str, # The stdout produced by the linter.
                'stderr': str, # The stderr produced by the linter.
                **self.__to_json__(), # Other keys are the same as the normal
                                      # json serialization.
            }

        :returns: An object as described above.
        """
        return {
            **self.__to_json__(),
            'stdout': self.stdout,
            'stderr': self.stderr,
        }

    def __to_json__(self) -> t.Mapping[str, object]:
        """Creates a JSON serializable representation of this linter instance.

        This object will look like this:

        .. code:: python

            {
                'id': str, # The id of this linter instance.
                'state': str, # The state of this linter instance.
                'work': Work, # The submission this instance has linted.
                'error_summary': str, # The summary of the error this linter
                                      # has encountered. This will be an empty
                                      # string if no error has occurred.
            }

        :returns: An object as described above.
        """
        return {
            'id': self.id,
            'state': self.state.name,
            'work': self.work,
            'error_summary': self.error_summary,
        }

    def add_comments(
        self,
        feedbacks: t.Mapping[int, t.Mapping[int, t.Sequence[t.
                                                            Tuple[str, str]]]],
    ) -> t.Iterable[LinterComment]:
        """Add comments written by this instance.

        :param feedbacks: The feedback to add, it should be in form as
            described below.
        :returns: A iterable with comments that have not been added or commited
            to the database yet.

        .. code:: python

            {
                file_id: {
                    line_number: [(linter_code, msg), ...]
                }
            }
        """
        for file_id, feedback in feedbacks.items():
            for line_number, msgs in feedback.items():
                for linter_code, msg in msgs:
                    yield LinterComment(
                        file_id=file_id,
                        line=line_number,
                        linter_code=linter_code,
                        linter_id=self.id,
                        comment=msg,
                    )
