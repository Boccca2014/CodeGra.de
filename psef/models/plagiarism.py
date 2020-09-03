"""This module defines a PlagiarismCase.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import json
import typing as t

from typing_extensions import Literal, TypedDict

import psef
import cg_enum
from cg_dt_utils import DatetimeWithTimezone
from cg_sqlalchemy_helpers.types import ColumnProxy

from . import Base, db
from .. import auth, helpers
from .assignment import Assignment


class PlagiarismMatch(Base):
    """Describes a possible plagiarism match between two files.

    :ivar ~.PlagiarismMatch.file1_id: The id of the first file associated with
        this match.
    :ivar ~.PlagiarismMatch.file1_start: The start position of the first file
        associated with this match. This position can be (and probably is) a
        line but it could also be a byte offset.
    :ivar ~.PlagiarismMatch.file1_end: The end position of the first file
        associated with this match. This position can be (and probably is) a
        line but it could also be a byte offset.
    :ivar ~.PlagiarismMatch.file2_id: Same as ``file1_id`` but of the second
        file.
    :ivar ~.PlagiarismMatch.file2_start: Same as ``file1_start`` but for the
        second file.
    :ivar ~.PlagiarismMatch.file2_end: Same as ``file1_end`` but for the second
        file.
    """
    __tablename__ = 'PlagiarismMatch'

    id = db.Column('id', db.Integer, primary_key=True)

    file1_id = db.Column(
        'file1_id',
        db.Integer,
        db.ForeignKey('File.id', ondelete='CASCADE'),
        nullable=False,
    )

    file2_id = db.Column(
        'file2_id',
        db.Integer,
        db.ForeignKey('File.id', ondelete='CASCADE'),
        nullable=False,
    )

    file1_start = db.Column('file1_start', db.Integer, nullable=False)
    file1_end = db.Column('file1_end', db.Integer, nullable=False)
    file2_start = db.Column('file2_start', db.Integer, nullable=False)
    file2_end = db.Column('file2_end', db.Integer, nullable=False)

    plagiarism_case_id = db.Column(
        'plagiarism_case_id',
        db.Integer,
        db.ForeignKey('PlagiarismCase.id', ondelete='CASCADE'),
    )

    plagiarism_case = db.relationship(
        lambda: PlagiarismCase,
        back_populates="matches",
        uselist=False,
    )

    file1 = db.relationship(
        lambda: psef.models.File,
        foreign_keys=file1_id,
        lazy='joined',
        innerjoin=True,
    )
    file2 = db.relationship(
        lambda: psef.models.File,
        foreign_keys=file2_id,
        lazy='joined',
        innerjoin=True,
    )

    def __to_json__(self) -> t.Mapping[str, object]:
        """Creates a JSON serializable representation of this object.


        This object will look like this:

        .. code:: python

            {
                'id': int, # The id of this match.
                'files': t.List[File], # The files of this match
                'lines': t.List[t.Tuple[int]], # The tuple of ``(start, end)``
                                               # for both files that are
                                               # present this match.
            }

        :returns: A object as described above.
        """
        return {
            'id': self.id,
            'files': [self.file1, self.file2],
            'lines':
                [
                    (self.file1_start, self.file1_end),
                    (self.file2_start, self.file2_end)
                ],
        }


class PlagiarismWorks(t.NamedTuple):
    """The works connected to a plagiarism case.
    """
    #: For this work is guaranteed that it was submitted to the assignment on
    #: which the plagiarism run was done.
    own_work: 'psef.models.Work'
    #: The assignment for this work might be different.
    other_work: 'psef.models.Work'

    @staticmethod
    def get_other_index() -> Literal[1]:
        """Get the index for the work that might not have been submitted to the
        assignment on which the run was done.
        """
        return 1


class PlagiarismCase(Base):
    """Describe a case of possible plagiarism.

    :ivar ~.PlagiarismCase.work1_id: The id of the first work to be associated
        with this possible case of plagiarism.
    :ivar ~.PlagiarismCase.work2_id: The id of the second work to be associated
        with this possible case of plagiarism.
    :ivar ~.PlagiarismCase.created_at: When was this case created.
    :ivar ~.PlagiarismCase.plagiarism_run_id: The :class:`.PlagiarismRun` in
        which this case was discovered.
    :ivar ~.PlagiarismCase.match_avg: The average similarity between the two
        matches. What the value exactly means differs per provider.
    :ivar ~.PlagiarismCase.match_max: The maximum similarity between the two
        matches. What the value exactly means differs per provider.
    """
    __tablename__ = 'PlagiarismCase'
    id = db.Column('id', db.Integer, primary_key=True)

    work1_id = db.Column(
        'work1_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
    )
    work2_id = db.Column(
        'work2_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False
    )
    plagiarism_run_id = db.Column(
        'plagiarism_run_id',
        db.Integer,
        db.ForeignKey('PlagiarismRun.id', ondelete='CASCADE'),
        nullable=False,
    )

    match_avg = db.Column('match_avg', db.Float, nullable=False)
    match_max = db.Column('match_max', db.Float, nullable=False)

    work1 = db.relationship(
        lambda: psef.models.Work,
        foreign_keys=work1_id,
        lazy='joined',
        innerjoin=True,
        backref=db.backref(
            '_plagiarism_cases1',
            lazy='select',
            uselist=True,
            cascade='all,delete'
        ),
    )
    work2 = db.relationship(
        lambda: psef.models.Work,
        foreign_keys=work2_id,
        lazy='joined',
        innerjoin=True,
        backref=db.backref(
            '_plagiarism_cases2',
            lazy='select',
            uselist=True,
            cascade='all,delete'
        ),
    )

    plagiarism_run: ColumnProxy['PlagiarismRun']

    matches = db.relationship(
        lambda: PlagiarismMatch,
        back_populates="plagiarism_case",
        cascade='all,delete',
        order_by=lambda: PlagiarismMatch.file1_id,
        uselist=True,
    )

    @property
    def works(self) -> PlagiarismWorks:
        """Get the works connected to this case.
        """
        if self.work2.assignment_id == self.plagiarism_run.assignment_id:
            return PlagiarismWorks(own_work=self.work2, other_work=self.work1)
        return PlagiarismWorks(own_work=self.work1, other_work=self.work2)

    @property
    def any_work_deleted(self) -> bool:
        """Is any of the works connected to this case deleted.
        """
        return self.work1.deleted or self.work2.deleted

    def __to_json__(self) -> t.Mapping[str, object]:
        """Creates a JSON serializable representation of this object.


        This object will look like this:

        The ``submissions`` field may be ``None`` and the assignments field may
        contain only partial information because of permissions issues.

        .. code:: python

            {
                'id': int, # The id of this case.
                'users': t.List[User], # The users of this plagiarism case.
                'match_avg': float, # The average similarity of this case.
                'match_max': float, # The maximum similarity of this case.
                'assignments': t.List[Assignment], # The two assignments of
                                                   # this case. These can
                                                   # differ!
                'submissions': t.List[work_models.Work], # The two submissions
                                                         # of this case.
            }

        :returns: A object as described above.
        """
        works = self.works
        perm_checker = auth.PlagiarismCasePermissions(self)
        can_see_all = perm_checker.ensure_may_see_other_assignment.and_(
            perm_checker.ensure_may_see_other_submission
        ).as_bool()
        data: t.MutableMapping[str, t.Any] = {
            'id': self.id,
            'users': [w.user for w in works],
            'match_avg': self.match_avg,
            'match_max': self.match_max,
            'submissions': list(works),
            'can_see_details': can_see_all,
            'assignment_ids': [w.assignment_id for w in works],
        }
        if not helpers.request_arg_true('no_assignment_in_case'):
            data['assignments'] = [w.assignment for w in works]
            assig = works.other_work.assignment
            if perm_checker.ensure_may_see_other_assignment.as_bool():
                data['assignments'][PlagiarismWorks.get_other_index()] = {
                    'name': assig.name,
                    'course': {
                        'name': assig.course.name,
                    },
                }

        # Make sure we may actually see this file.
        if not perm_checker.ensure_may_see_other_submission.as_bool():
            data['submissions'] = None

        return data

    def __extended_to_json__(self) -> t.Mapping[str, object]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'matches': t.List[PlagiarismMatch], # The list of matches that
                                                    # are part of this case.
                **self.__to_json__(),
            }

        :returns: A object as described above.
        """
        return {
            'matches': self.matches,
            **self.__to_json__(),
        }


@enum.unique
class PlagiarismState(cg_enum.CGEnum):
    """Describes in what state a :class:`.PlagiarismRun` is.

    :param running: The provider is currently running.
    :param done: The provider has finished without crashing.
    :param crashed: The provider has crashed in some way.
    """
    starting: int = 1
    done: int = 2
    crashed: int = 3
    started: int = 4
    parsing: int = 5
    running: int = 6
    finalizing: int = 7
    comparing: int = 8


class PlagiarismRun(Base):
    """Describes a run for a plagiarism provider.

    :ivar ~.PlagiarismRun.state: The state this run is in.
    :ivar ~.PlagiarismRun.log: The log on ``stdout`` and ``stderr`` we got from
        running the plagiarism provider. This is only available if the
        ``state`` is ``done`` or ``crashed``.
    :ivar ~.PlagiarismRun.json_config: The config used for this run saved in a
        sorted association list.
    :ivar ~.PlagiarismRun.assignment_id: The id of the assignment this
        belongs to.
    """
    __tablename__ = 'PlagiarismRun'

    id = db.Column('id', db.Integer, primary_key=True)
    state = db.Column(
        'state',
        db.Enum(PlagiarismState, name='plagiarismtate'),
        default=PlagiarismState.starting,
        nullable=False,
    )
    submissions_total = db.Column(
        'submissions_total', db.Integer, default=0, nullable=True
    )
    submissions_done = db.Column(
        'submissions_done', db.Integer, default=0, nullable=True
    )
    log = db.Column('log', db.Unicode, nullable=True)
    json_config = db.Column('json_config', db.Unicode, nullable=False)
    assignment_id = db.Column(
        'assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id'),
        nullable=False,
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False,
    )

    assignment = db.relationship(
        lambda: Assignment,
        foreign_keys=assignment_id,
        lazy='joined',
        innerjoin=True,
    )

    cases = db.relationship(
        lambda: PlagiarismCase,
        backref=db.backref('plagiarism_run', innerjoin=True),
        order_by=PlagiarismCase.match_avg.desc,
        cascade='all,delete',
        uselist=True,
    )

    class _AssignmentJSON(TypedDict):
        id: int
        course_id: int
        name: str

    class _CourseJSON(TypedDict):
        id: int
        name: str
        virtual: bool

    class AsJSON(TypedDict):
        """The way this class will be represented in JSON.
        """
        #: The id of the run.
        id: int
        #: The state this run is in.
        state: PlagiarismState
        #: The amount of submissions that have finished the current state.
        submissions_done: t.Optional[int]
        #: The total amount of submissions connected to this run.
        submissions_total: t.Optional[int]
        #: Which provider is doing this run.
        provider_name: str
        #: The config used for this run.
        config: object
        #: The time this run was created.
        created_at: DatetimeWithTimezone
        #: The assignment this run was done on.
        assignment: 'Assignment'
        #: The log produced by the provider while running.
        log: t.Optional[str]
        #: A mapping between assignment id and the assignment for each
        # assignment that is connected to this run. These are not (!) full
        # assignment objects, but only contain the ``name`` and ``id``.
        assignments: t.Mapping[int, 'PlagiarismRun._AssignmentJSON']
        #: The mapping between course id and the course for each course that is
        #: connected to this run. These are not (!) full course object, but
        #: contain only the ``name``, ``id`` and if the course is virtual.
        courses: t.Mapping[int, 'PlagiarismRun._CourseJSON']

    def __to_json__(self) -> AsJSON:
        """Creates a JSON serializable representation of this object.

        :returns: A object as described above.
        """
        all_assignments = self.get_connected_assignments()
        courses: t.Mapping[int, 'PlagiarismRun._CourseJSON'] = {
            assig.course_id: {
                'id': assig.course_id,
                'name': assig.course.name,
                'virtual': assig.course.virtual
            }
            for assig in all_assignments
        }
        assignments: t.Mapping[int, 'PlagiarismRun._AssignmentJSON'] = {
            assig.id: {
                'id': assig.id,
                'name': assig.name,
                'course_id': assig.course_id,
            }
            for assig in all_assignments
        }

        return {
            'id': self.id,
            'state': self.state,
            'submissions_done': self.submissions_done,
            'submissions_total': self.submissions_total,
            'provider_name': self.provider_name,
            'config': json.loads(self.json_config),
            'created_at': self.created_at,
            'assignment': self.assignment,
            'log': self.log,
            'assignments': assignments,
            'courses': courses,
        }

    def __extended_to_json__(self) -> t.Mapping[str, object]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'cases': t.List[PlagiarismCase], # The cases of possible
                                                 # plagiarism found during this
                                                 # run.
                'log': str, # The log on stderr and stdout of this run.
                **self.__to_json__(),
            }

        :returns: A object as described above.
        """
        return {
            'cases': [c for c in self.cases if not c.any_work_deleted],
            **self.__to_json__(),
        }

    @property
    def provider_name(self) -> str:
        """
        :returns: The provider name of this plagiarism run.
        """
        for key, val in json.loads(self.json_config):
            if key == 'provider':
                return val
        # This can never happen
        raise KeyError  # pragma: no cover

    @property
    def plagiarism_cls(self) -> t.Type['psef.plagiarism.PlagiarismProvider']:
        """Get the class of the plagiarism provider of this run.

        :returns: The class of this plagiarism provider run.
        """
        return psef.helpers.get_class_by_name(
            psef.plagiarism.PlagiarismProvider,
            self.provider_name,
        )

    def get_connected_assignments(self) -> t.Sequence[Assignment]:
        assigs1 = PlagiarismCase.query.filter(
            PlagiarismCase.plagiarism_run == self,
        ).join(PlagiarismCase.work1).with_entities(
            psef.models.Work.assignment_id
        ).distinct(psef.models.Work.assignment_id)

        assigs2 = PlagiarismCase.query.filter(
            PlagiarismCase.plagiarism_run == self,
        ).join(PlagiarismCase.work2).with_entities(
            psef.models.Work.assignment_id
        ).distinct(psef.models.Work.assignment_id)

        all_assigs = assigs1.union(assigs2)

        return Assignment.query.filter(Assignment.id.in_(all_assigs)).all()
