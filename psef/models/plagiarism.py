"""This module defines a PlagiarismCase.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import enum
import json
import uuid
import typing as t
import tempfile
import itertools

import structlog
from typing_extensions import Literal, TypedDict
from werkzeug.datastructures import FileStorage

import psef
import cg_enum
import cg_flask_helpers
import cg_object_storage
from cg_dt_utils import DatetimeWithTimezone
from cg_object_storage import Putter
from cg_cache.intra_request import cached_property
from cg_sqlalchemy_helpers.types import ColumnProxy

from . import Base, db
from .. import auth, files, archive, helpers, current_app
from .course import Course
from .assignment import Assignment
from ..exceptions import APICodes, APIException

logger = structlog.get_logger()


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
        nullable=False,
    )

    plagiarism_case = db.relationship(
        lambda: PlagiarismCase,
        back_populates="matches",
        foreign_keys=plagiarism_case_id,
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
        connected_files = [self.file1, self.file2]
        lines = [
            (self.file1_start, self.file1_end),
            (self.file2_start, self.file2_end)
        ]
        if self.plagiarism_case.works.own_work.id != self.file1.work_id:
            connected_files.reverse()
            lines.reverse()

        return {
            'id': self.id,
            'files': connected_files,
            'lines': lines,
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
            helpers.add_deprecate_warning(
                'Getting the assignments connected to a single case is'
                ' deprecated, and will be removed in the next major release of'
                ' CodeGrade. Please use the lookup table in the plagiarism'
                ' run.'
            )
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


_PlagiarismRunOldAssignment = db.Table(
    'plagiarism_run_old_assignment',
    db.Column(
        'old_assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id'),
        nullable=False,
        primary_key=True,
    ),
    db.Column(
        'plagiarism_run_id',
        db.Integer,
        db.ForeignKey('PlagiarismRun.id'),
        nullable=False,
        primary_key=True,
    )
)


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

    old_assignments = db.relationship(
        lambda: Assignment,
        secondary=_PlagiarismRunOldAssignment,
        cascade='all,delete',
        order_by=lambda: Assignment.created_at,
        uselist=True,
    )

    def __init__(
        self,
        json_config: str,
        assignment: Assignment,
        old_assignments: t.Sequence[Assignment],
    ) -> None:
        super().__init__(
            json_config=json_config,
            assignment=assignment,
            old_assignments=old_assignments,
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
        all_assignments = self._get_connected_assignments()
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
            'provider_name': self.provider.get_name(),
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

    @cached_property
    def provider(self) -> 'psef.plagiarism.PlagiarismProvider':
        """The provider that did (/is doing/will be doing) this run.
        """
        loaded_json = dict(json.loads(self.json_config))
        cls = helpers.get_class_by_name(
            psef.plagiarism.PlagiarismProvider, loaded_json['provider']
        )
        # provider_cls is a subclass of PlagiarismProvider and that can be
        # instantiated
        provider: psef.plagiarism.PlagiarismProvider = t.cast(t.Any, cls)()
        provider.set_options(loaded_json)
        return provider

    def _get_connected_assignments(self) -> t.Sequence[Assignment]:
        """Get a sequence of all assignments that have a case connected to this
        plagiarism run.
        """
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

        return Assignment.query.filter(
            Assignment.id.in_(all_assigs) |
            (Assignment.id == self.assignment_id),
        ).all()

    def _do_run(
        self, result_dir: str, restored_dir: str, archive_dir: str,
        base_code_dir: str
    ) -> None:
        self._set_and_commit_state(PlagiarismState.started)

        provider = self.provider

        file_lookup_tree: t.Dict[int, files.FileTree[int]] = {}
        submission_lookup: t.Dict[str, int] = {}
        old_subs: t.Set[int] = set()

        direct_subs = self.assignment.get_all_latest_submissions().all()
        self.submissions_total = len(direct_subs)
        db.session.commit()

        for sub in itertools.chain(
            direct_subs,
            *(a.get_all_latest_submissions() for a in self.old_assignments)
        ):
            dir_name = self._make_dir_name(sub)
            submission_lookup[dir_name] = sub.id

            if sub.assignment_id == self.assignment_id:
                parent = files.safe_join(restored_dir, dir_name)
            else:
                parent = os.path.join(archive_dir, dir_name)
                old_subs.add(sub.id)

            os.mkdir(parent)
            file_lookup_tree[sub.id] = files.FileTree(
                name=dir_name,
                id=-1,
                entries=[
                    psef.models.File.restore_directory_structure(
                        parent,
                        psef.models.File.make_cache(sub),
                    )
                ],
            )

        if provider.supports_progress():
            self._set_and_commit_state(PlagiarismState.parsing)
        else:  # pragma: no cover
            # We don't have any providers not supporting progress
            self._set_and_commit_state(PlagiarismState.running)

        progress_prefix = str(uuid.uuid4())
        try:
            ok, self.log = helpers.call_external(
                helpers.format_list(
                    provider.get_program_call(),
                    restored_dir=restored_dir,
                    result_dir=result_dir,
                    archive_dir=archive_dir,
                    base_code_dir=base_code_dir,
                    progress_prefix=progress_prefix,
                ),
                lambda line: self._update_state_from_output(
                    line,
                    progress_prefix=progress_prefix,
                    provider=provider,
                ),
                nice_level=10,
            )
        # pylint: disable=broad-except
        except Exception:  # pragma: no cover
            self._set_and_commit_state(PlagiarismState.crashed)
            raise

        logger.info(
            'Plagiarism call finished',
            finished_successfully=ok,
            captured_stdout=self.log
        )

        self._set_and_commit_state(PlagiarismState.finalizing)

        if ok:
            self._process_matches(
                result_dir, old_subs, file_lookup_tree, submission_lookup
            )
            self._set_and_commit_state(PlagiarismState.done)
        else:
            self._set_and_commit_state(PlagiarismState.crashed)

    @staticmethod
    def _make_dir_name(sub: 'psef.models.Work') -> str:
        return (
            f'{sub.user.name.replace("/", "_")} || {sub.assignment_id}'
            f'-{sub.id}-{sub.user_id}'
        )

    def _process_matches(
        self,
        result_dir: str,
        old_subs: t.Container[int],
        file_lookup_tree: t.Mapping[int, 'files.FileTree[int]'],
        submission_lookup: t.Mapping[str, int],
    ) -> None:
        csv_file = os.path.join(result_dir, self.provider.matches_output)
        csv_file = self.provider.transform_csv(csv_file)
        self.cases.extend(
            psef.plagiarism.process_output_csv(
                submission_lookup, old_subs, file_lookup_tree, csv_file
            )
        )

    def _set_and_commit_state(self, state: PlagiarismState) -> None:
        self.state = state
        db.session.commit()

    def _update_state_from_output(
        self,
        line: str,
        *,
        progress_prefix: str,
        provider: 'psef.plagiarism.PlagiarismProvider',
    ) -> bool:
        if not provider.supports_progress():  # pragma: no cover
            return False

        new_val = provider.get_progress_from_line(progress_prefix, line)
        if new_val is not None:
            cur, tot = new_val
            if cur == tot and self.state == PlagiarismState.parsing:
                self.submissions_done = 0
                self._set_and_commit_state(PlagiarismState.comparing)
            else:
                val = cur + (self.submissions_total or 0) - tot
                self.submissions_done = val
                db.session.commit()

            return True

        return False

    def do_run(self) -> None:
        """Execute the plagiarism checker.
        """
        with tempfile.TemporaryDirectory() as tempdir:

            def make_dir(name: str) -> str:
                new_dir = os.path.join(tempdir, f'{name}_{uuid.uuid4()}')
                os.mkdir(new_dir)
                return new_dir

            PBCF = psef.models.PlagiarismBaseCodeFile
            base_code_dir = make_dir('base_code')
            cache = PBCF.make_cache(self)
            if cache:
                restored = PBCF.restore_directory_structure(
                    base_code_dir, cache
                )
                base_code_dir = os.path.join(base_code_dir, restored.name)

            self._do_run(
                result_dir=make_dir('result_dir'),
                restored_dir=make_dir('restored_dir'),
                archive_dir=make_dir('archive_dir'),
                base_code_dir=base_code_dir,
            )

    def schedule_delete_base_code(self) -> None:
        """Delete the base code from disk for this plagiarism run after the
        current request has finished.
        """
        to_delete: t.List[cg_object_storage.File] = []
        for sub_files in psef.models.PlagiarismBaseCodeFile.make_cache(
            self
        ).values():
            for sub in sub_files:
                sub.backing_file.if_just(to_delete.append)

        def do_delete() -> None:
            for f in to_delete:
                try:
                    f.delete()
                # pylint: disable=broad-except
                except Exception:  # pragma: no cover
                    pass

        cg_flask_helpers.callback_after_this_request(do_delete)

    def add_base_code(self, base_code: FileStorage, putter: Putter) -> None:
        """Add base code to this plagiarism run.

        :param base_code: The file to use as base code, it will be extracted.
        :param putter: The putter to use to add new files to storage.
        """
        # We do not have any provider yet that doesn't support this, so we
        # don't check the coverage.
        if not self.provider.supports_base_code():  # pragma: no cover
            raise APIException(
                'This provider does not support base code',
                f'"{self.provider.get_name()}" does not support base code',
                APICodes.INVALID_PARAM, 400
            )
        elif (
            not base_code.filename or
            not psef.archive.Archive.is_archive(base_code.filename)
        ):
            raise APIException(
                'You can currently only provide an archive of base code',
                'The uploaded file was not an archive', APICodes.INVALID_PARAM,
                400
            )

        tree = psef.files.extract(
            base_code,
            base_code.filename,
            max_size=current_app.max_large_file_size,
            putter=putter,
        )
        BaseCode = psef.models.PlagiarismBaseCodeFile
        base_code_file = BaseCode.create_from_extract_directory(
            tree, top=None, creation_opts={'plagiarism_run': self}
        )
        db.session.add(base_code_file)

    def add_old_submissions(
        self,
        old_subs: t.Sequence[FileStorage],
        putter: cg_object_storage.Putter,
    ) -> None:
        """Add old submissions to this plagiarism run.

        :param old_subs: A sequence of files that will be converted into
            submissions.
        :param putter: The putter to use to add new files to storage.
        """
        max_size = current_app.max_file_size
        tree = psef.files.process_files(
            old_subs, max_size=max_size, putter=putter
        )
        # Normally we don't extract archives in archives, however for the
        # plagiarism we do this. So after extracting this directory we now
        # loop over all the children to check if they are directories in
        # which case we extract them.
        for old_child in tree.values:
            if not (
                isinstance(
                    old_child,
                    psef.files.ExtractFileTreeFile,
                ) and archive.Archive.is_archive(old_child.name)
            ):
                continue

            with old_child.backing_file.open() as old_child_stream:
                tree.forget_child(old_child)

                new_child = psef.files.extract(
                    FileStorage(
                        stream=old_child_stream, filename=old_child.name
                    ),
                    old_child.name,
                    putter=putter,
                    max_size=max_size,
                )
                # This is to create a name for the author that resembles
                # the name of the archive.
                new_child.name = old_child.name.split('.', 1)[0]
                tree.add_child(new_child)

            old_child.backing_file.delete()

        virtual_course = Course.create_virtual_course(tree)
        db.session.add(virtual_course)
        self.old_assignments.append(virtual_course.assignments[0])
