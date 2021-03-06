"""This module defines all models needed for auto tests.

SPDX-License-Identifier: AGPL-3.0-only
"""
import math
import uuid
import typing as t
import itertools

import structlog
from sqlalchemy import orm, distinct
from typing_extensions import Literal, TypedDict
from sqlalchemy.sql.expression import or_, and_, case, nullsfirst

import psef
import cg_helpers
import cg_object_storage
from cg_dt_utils import DatetimeWithTimezone
from cg_flask_helpers import callback_after_this_request
from cg_typing_extensions import make_typed_dict_extender
from cg_sqlalchemy_helpers import UUIDType
from cg_sqlalchemy_helpers import func as sql_func
from cg_sqlalchemy_helpers import deferred, hybrid_property
from cg_sqlalchemy_helpers.mixins import IdMixin, UUIDMixin, TimestampMixin

from . import Base, MyQuery, DbColumn, db
from . import work as work_models
from . import auto_test_step as auto_test_step_models
from .. import auth, signals
from .. import auto_test as auto_test_module
from .. import site_settings
from ..helpers import NotEqualMixin
from ..registry import auto_test_handlers, auto_test_grade_calculators
from ..exceptions import APICodes, APIException, InvalidStateException
from ..permissions import CoursePermission as CPerm

logger = structlog.get_logger()

GradeCalculator = t.Callable[[t.Sequence['psef.models.RubricItem'], float],
                             'psef.models.RubricItem']


class AutoTestSuite(Base, TimestampMixin, IdMixin):
    """This class represents a Suite (also known as category) in an AutoTest.
    """
    __tablename__ = 'AutoTestSuite'
    id = db.Column('id', db.Integer, primary_key=True)

    rubric_row_id = db.Column(
        'rubric_row_id',
        db.Integer,
        db.ForeignKey('RubricRow.id'),
        nullable=False
    )
    rubric_row = db.relationship(
        lambda: psef.models.RubricRow,
        foreign_keys=rubric_row_id,
        innerjoin=True,
    )

    network_disabled = db.Column(
        'network_disabled',
        db.Boolean,
        nullable=False,
        default=True,
        server_default='FALSE',
    )

    submission_info = db.Column(
        'submission_info',
        db.Boolean,
        nullable=False,
        default=False,
        server_default='FALSE',
    )

    auto_test_set_id = db.Column(
        'auto_test_set_id',
        db.Integer,
        db.ForeignKey('AutoTestSet.id', ondelete='CASCADE'),
        nullable=False
    )

    auto_test_set = db.relationship(
        lambda: AutoTestSet,
        foreign_keys=auto_test_set_id,
        back_populates='suites',
        lazy='joined',
        innerjoin=True,
    )

    steps = db.relationship(
        lambda: auto_test_step_models.AutoTestStepBase,
        back_populates="suite",
        cascade='all,delete,delete-orphan',
        order_by=lambda: auto_test_step_models.AutoTestStepBase.order,
        uselist=True,
    )

    command_time_limit = db.Column(
        'command_time_limit', db.Float, nullable=True, default=None
    )

    def get_instructions(
        self, run: 'AutoTestRun'
    ) -> auto_test_module.SuiteInstructions:
        """Get the instructions to run this suite.
        """
        show_hidden = run.run_hidden_steps
        steps = [s for s in self.steps if show_hidden or not s.hidden]
        return {
            'id': self.id,
            'steps': [s.get_instructions() for s in steps],
            'network_disabled': self.network_disabled,
            'submission_info': self.submission_info,
        }

    class AsJSON(TypedDict):
        """The set as JSON.
        """
        #: The id of this suite (or "category")
        id: int
        #: The steps that will be executed in this suite.
        steps: t.Sequence['psef.models.AutoTestStepBase']
        #: The rubric row this category is connected to.
        rubric_row: 'psef.models.RubricRow'
        #: Is the network disabled while running this category.
        network_disabled: bool
        #: Will submission info be available while running this step.
        submission_info: bool
        #: The maximum amount of time in seconds a step (or substep) may
        #: take. If ``null`` the instance default will be used.
        command_time_limit: t.Optional[float]

    def __to_json__(self) -> AsJSON:
        return {
            'id': self.id,
            'steps': self.steps,
            'rubric_row': self.rubric_row,
            'network_disabled': self.network_disabled,
            'submission_info': self.submission_info,
            'command_time_limit': self.command_time_limit,
        }

    def set_steps(
        self,
        steps: t.Sequence['auto_test_step_models.AutoTestStepBase.InputAsJSON',
                          ],
    ) -> None:
        """Set the steps of this suite.

        :param steps: The new steps of this suite.
        :returns: Nothing
        """
        new_steps = []
        for idx, step_data in enumerate(steps):
            try:
                step_type = auto_test_handlers[step_data['type']]
            except KeyError as exc:
                raise APIException(
                    'The given test type is not valid',
                    f'The given test type "{step_data["type"]}" is not known',
                    APICodes.INVALID_PARAM, 400
                ) from exc

            if step_data.get('id') is None:
                step = step_type()
                db.session.add(step)
            else:
                step = psef.helpers.get_or_404(step_type, step_data['id'])
                assert isinstance(step, step_type)

            step.hidden = step_data['hidden']
            step.order = idx
            step.name = step_data['name']
            step.weight = step_data['weight']

            step.update_data_from_json(step_data['data'])
            new_steps.append(step)

        self.steps = new_steps

    def copy(self) -> 'AutoTestSuite':
        return AutoTestSuite(
            rubric_row=self.rubric_row,
            network_disabled=self.network_disabled,
            submission_info=self.submission_info,
            steps=[s.copy() for s in self.steps],
            command_time_limit=self.command_time_limit,
        )


class AutoTestSet(Base, TimestampMixin, IdMixin):
    """This class represents a set (also known as level) of an AutoTest.
    """
    __tablename__ = 'AutoTestSet'

    id = db.Column('id', db.Integer, primary_key=True)
    stop_points = db.Column('stop_points', db.Float, nullable=False, default=0)
    auto_test_id = db.Column(
        'auto_test_id',
        db.Integer,
        db.ForeignKey('AutoTest.id', ondelete='CASCADE'),
        nullable=False
    )

    auto_test = db.relationship(
        lambda: AutoTest,
        foreign_keys=auto_test_id,
        back_populates='sets',
        lazy='joined',
        innerjoin=True,
    )

    suites = db.relationship(
        lambda: AutoTestSuite,
        back_populates="auto_test_set",
        cascade='all,delete,delete-orphan',
        order_by=lambda: AutoTestSuite.created_at,
        uselist=True,
    )

    def get_instructions(
        self, run: 'AutoTestRun'
    ) -> auto_test_module.SetInstructions:
        """Get the instructions to run this set.
        """
        return {
            'id': self.id,
            'suites': [s.get_instructions(run) for s in self.suites],
            'stop_points': self.stop_points,
        }

    class AsJSON(TypedDict):
        """The result as JSON.
        """
        #: The id of this set.
        id: int
        #: The suites connected to this set. In the UI these are called
        #: "categories"
        suites: t.Sequence[AutoTestSuite]
        #: A floating indicating the minimum percentage of points a student
        #: should achieve after this set (or "level"). If this percentage is
        #: not achieved the AutoTest will stop running.
        stop_points: float

    def __to_json__(self) -> AsJSON:
        return {
            'id': self.id,
            'suites': self.suites,
            'stop_points': self.stop_points,
        }

    def copy(self) -> 'AutoTestSet':
        return AutoTestSet(
            suites=[s.copy() for s in self.suites],
            stop_points=self.stop_points,
        )


class AutoTestResult(Base, TimestampMixin, IdMixin, NotEqualMixin):
    """The result for a single submission (:class:`.work_models.Work`) of a
    :class:`.AutoTestRun`.
    """
    __tablename__ = 'AutoTestResult'

    auto_test_run_id = db.Column(
        'auto_test_run_id',
        db.Integer,
        db.ForeignKey('AutoTestRun.id', ondelete='CASCADE'),
        nullable=False
    )

    run = db.relationship(
        lambda: AutoTestRun,
        foreign_keys=auto_test_run_id,
        back_populates='results',
        lazy='select',
        innerjoin=True,
    )

    auto_test_runner_id = db.Column(
        'auto_test_runner_id',
        UUIDType,
        db.ForeignKey('AutoTestRunner.id', ondelete='CASCADE'),
        nullable=True,
    )

    runner = db.relationship(
        lambda: AutoTestRunner,
        foreign_keys=auto_test_runner_id,
        lazy='selectin',
    )

    setup_stdout = deferred(
        db.Column(
            'setup_stdout',
            db.Unicode,
            default=None,
        )
    )

    started_at = db.Column(
        'started_at', db.TIMESTAMP(timezone=True), default=None, nullable=True
    )

    setup_stderr = deferred(
        db.Column(
            'setup_stderr',
            db.Unicode,
            default=None,
        )
    )

    step_results = db.relationship(
        lambda: auto_test_step_models.AutoTestStepResult,
        back_populates='result',
        cascade='all,delete,delete-orphan',
        order_by=lambda: auto_test_step_models.AutoTestStepResult.created_at,
        lazy='selectin',
        uselist=True,
        passive_deletes=True,
    )

    _state = db.Column(
        'state',
        db.Enum(auto_test_step_models.AutoTestStepResultState),
        default=auto_test_step_models.AutoTestStepResultState.not_started,
        nullable=False,
    )

    work_id = db.Column(
        'work_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
    )
    work = db.relationship(
        lambda: work_models.Work,
        foreign_keys=work_id,
        lazy='selectin',
    )

    final_result = db.Column('final_result', db.Boolean, nullable=False)

    # This variable is generated from the backref from all files
    files: MyQuery["psef.models.AutoTestOutputFile"]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AutoTestResult):
            return other.id == self.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def _get_state(self) -> auto_test_step_models.AutoTestStepResultState:
        """Get the state of this result

        >>> from datetime import datetime, timezone
        >>> called = False
        >>> def fun(_):
        ...  global called
        ...  called = True
        >>> psef.tasks.adjust_amount_runners = fun
        >>> r = AutoTestResult(run=AutoTestRun())
        >>> not_set = object()
        >>> r.started_at = not_set
        >>> r.state = auto_test_step_models.AutoTestStepResultState.running
        >>> isinstance(r.started_at, datetime)
        True
        >>> r.started_at.tzinfo == timezone.utc
        True
        >>> called
        True
        >>> r.state = 6
        >>> r.started_at is None
        True
        >>> r.started_at = not_set
        >>> r.state = 6
        >>> r.started_at is not_set
        True
        """
        return self._state

    def _set_state(
        self, new_state: auto_test_step_models.AutoTestStepResultState
    ) -> None:
        if new_state == self._state:
            return

        self._state = new_state
        if new_state == auto_test_step_models.AutoTestStepResultState.running:
            self.started_at = DatetimeWithTimezone.utcnow()
            psef.tasks.adjust_amount_runners(self.run.id)
        elif (
            new_state in
            auto_test_step_models.AutoTestStepResultState.get_finished_states()
        ):
            if self.final_result:
                self.update_rubric()
        else:
            self.started_at = None

    state = hybrid_property(fget=_get_state, fset=_set_state)

    @hybrid_property
    def is_finished(self) -> bool:
        """Has this state passed?
        """
        return (
            self.state in
            auto_test_step_models.AutoTestStepResultState.get_finished_states()
        )

    def clear(self) -> None:
        """Clear this result and set it state back to ``not_started``.

        .. note:: This also clears the rubric
        """
        self.step_results = []
        self.state = auto_test_step_models.AutoTestStepResultState.not_started
        self.setup_stderr = None
        self.setup_stdout = None
        self.runner = None

        if self.final_result:
            self.clear_rubric()

        self.files.delete()

    def get_locked_work(self) -> 'work_models.Work':
        return work_models.Work.query.filter_by(
            id=self.work_id,
        ).with_for_update(of=work_models.Work).one()

    def clear_rubric(self) -> None:
        """Clear all the rubric categories connected to this AutoTest for this
        result.

        :returns: Nothing
        """
        work = self.get_locked_work()
        own_rubric_rows = set(
            suite.rubric_row_id for suite in self.run.auto_test.all_suites
        )

        work.selected_items = [
            i for i in work.selected_items
            if i.rubric_item.rubricrow_id not in own_rubric_rows
        ]
        work.set_grade(grade_origin=work_models.GradeOrigin.auto_test)

    def update_rubric(self) -> None:
        """Update the rubric of the connected submission according to this
        AutoTest result.

        .. note:: This might pass back the grade to the LMS if required.
        """
        # Lock the work we want to update,
        work = self.get_locked_work()
        old_selected_items = set(work.selected_items)
        new_items = {
            i.rubric_item.rubricrow_id: i
            for i in work.selected_items
        }
        changed_item = False

        for suite in self.run.auto_test.all_suites:
            got, possible = self.get_amount_points_in_suites(suite)
            percentage = got / possible
            assert self.run.auto_test.grade_calculator is not None

            new_item = suite.rubric_row.make_work_rubric_item_for_auto_test(
                work, percentage, self.run.auto_test.grade_calculator
            )

            if new_item not in old_selected_items:
                new_items[suite.rubric_row_id] = new_item
                changed_item = True

        if not changed_item:
            return

        work.selected_items = list(new_items.values())
        work.set_grade(grade_origin=work_models.GradeOrigin.auto_test)

    def get_amount_points_in_suites(self, *suites: 'AutoTestSuite'
                                    ) -> t.Tuple[float, float]:
        """Get the amount of points in the given suites, and how many points
        where achieved.

        :param suites: The suites to calculate the amount of points for.
        :returns: A tuple where the first value is the amount of points
            achieved in the given suites, and the second value is the amount of
            points possible in the given suites.
        """
        steps = list(
            itertools.chain.from_iterable(suite.steps for suite in suites)
        )

        step_ids = set(step.id for step in steps)
        possible = sum(step.weight for step in steps)
        achieved = sum(
            step_result.achieved_points for step_result in self.step_results
            if step_result.auto_test_step_id in step_ids
        )

        return achieved, possible

    class AsJSON(TypedDict):
        """The JSON representation of a result.
        """
        #: The id of this result
        id: int
        #: The time this result was created
        created_at: DatetimeWithTimezone
        #: The moment this result was started. If this is ``null`` the result
        #: has not yet started.
        started_at: t.Optional[DatetimeWithTimezone]
        #: The id of the submission (work) that was tested in this result.
        work_id: int
        #: The state the result is in.
        state: 'psef.models.AutoTestStepResultState'
        #: The amount of points achieved in this step by the student.
        points_achieved: float

    class AsExtendedJSON(AsJSON):
        """The extended JSON representation of a result.
        """
        #: The stdout produced in the student setup script.
        setup_stdout: t.Optional[str]
        #: The stderr produced in the student setup script.
        setup_stderr: t.Optional[str]
        #: The results for each step in this AutoTest. The ordering of this
        #: list is arbitrary, and the results for entire suites and or sets
        #: might be missing.
        step_results: t.List['psef.models.AutoTestStepResult']
        #: If the result has not started this will contain the amount of
        #: students we expect we still need to run before this result is
        #: next. This might be incorrect and should only be used as a rough
        #: estimate.
        approx_waiting_before: t.Optional[int]
        #: If ``true`` this is the final result for the student, meaning that
        #: without teacher interaction (e.g. restarting the AutoTest) this
        #: result will not change and will be used as is to calculate the grade
        #: of the student. Reasons why this may not be the case include but are
        #: not limited to the test containing hidden steps that will only be
        #: run after the deadline.
        final_result: bool
        #: A mapping between suite id and the files written to the AutoTest
        #: output folder in that suite.
        suite_files: t.Mapping[int,
                               t.Sequence['psef.files.FileTree[uuid.UUID]'],
                               ]

    def __to_json__(self) -> AsJSON:
        """Convert this result to a json object.
        """
        points_achieved, _ = self.get_amount_points_in_suites(
            *self.run.auto_test.all_suites
        )

        return {
            'id': self.id,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'work_id': self.work_id,
            'state': self.state,
            'points_achieved': points_achieved,
        }

    def __extended_to_json__(self) -> AsExtendedJSON:
        approx_before: t.Optional[int] = None
        if (
            self.state ==
            auto_test_step_models.AutoTestStepResultState.not_started
        ):
            approx_before = self.run.get_results_to_run().filter(
                AutoTestResult.created_at < self.created_at
            ).count()

        step_results = self.step_results
        if auth.WorkPermissions(self.work).ensure_may_see_grade.as_bool():
            final_result = self.final_result
        else:
            step_results = [s for s in step_results if not s.step.hidden]
            final_result = False

        suite_files = {}
        assig = self.run.auto_test.assignment
        if assig.is_done or psef.current_user.has_permission(
            CPerm.can_view_autotest_output_files_before_done, assig.course_id
        ):
            for f in self.files.filter_by(parent_id=None):
                entries = f.list_contents().entries
                if entries:
                    suite_files[f.auto_test_suite_id] = entries

        return make_typed_dict_extender(
            self.__to_json__(), self.AsExtendedJSON
        )(
            setup_stdout=self.setup_stdout,
            setup_stderr=self.setup_stderr,
            step_results=step_results,
            approx_waiting_before=approx_before,
            final_result=final_result,
            suite_files=suite_files,
        )

    @classmethod
    def get_results_by_user(cls, student_id: int) -> 'MyQuery[AutoTestResult]':
        """Get the :class:`.AutoTestResult` s for the given student.

        :returns: A query that gets all results by the given user. Notice that
            these results are for all :class:`.AutoTestRun` s.
        """
        work_ids = db.session.query(
            work_models.Work.id,
        ).filter(work_models.Work.user_id == student_id)
        return cls.query.filter(cls.work_id.in_(work_ids))


class AutoTestRunner(Base, TimestampMixin, UUIDMixin, NotEqualMixin):
    """This class represents the runner of a :class:`.AutoTestRun`.

    A single run might have multiple runners, as a runner might crash and in
    this case it is replaced by a new runner.
    """

    __tablename__ = 'AutoTestRunner'

    _ipaddr = db.Column('ipaddr', db.Unicode, nullable=False)

    last_heartbeat = db.Column(
        'last_heartbeat',
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False,
    )

    _job_id = db.Column('job_id', db.Unicode)

    run_id = db.Column(
        'run_id',
        db.Integer,
        db.ForeignKey('AutoTestRun.id', ondelete='CASCADE'),
        nullable=True,
        default=None,
    )

    run = db.relationship(
        lambda: AutoTestRun,
        foreign_keys=run_id,
        back_populates='runners',
    )

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        """Check if two AutoTestRunners are equal.

        >>> first = AutoTestRunner(id=1)
        >>> second = AutoTestRunner(id=1)
        >>> third = AutoTestRunner(id=2)
        >>> first == first
        True
        >>> first == second
        True
        >>> first == third
        False
        >>> first == object()
        False
        """
        if not isinstance(other, AutoTestRunner):
            return NotImplemented
        return self.id == other.id

    @property
    def job_id(self) -> str:
        """Get the job id of this runner.

        >>> AutoTestRunner().job_id.startswith('INVALID-')
        True
        >>> AutoTestRunner(_job_id='hello').job_id
        'hello'
        """
        return self._job_id or f'INVALID-{uuid.uuid4().hex}'

    @hybrid_property
    def ipaddr(self) -> str:
        """The ip address of this runner."""
        return self._ipaddr

    @classmethod
    def create(
        cls,
        ipaddr: str,
        run: 'AutoTestRun',
    ) -> 'AutoTestRunner':
        """Create an :class:`.AutoTestRunner`.

        :param ipdaddr: The ip address of this runner.
        :param run: The run of this runner.
        """
        return cls(_ipaddr=ipaddr, _job_id=run.get_job_id(), run=run)


class AutoTestRun(Base, TimestampMixin, IdMixin):
    """This class represents a single run of an AutoTest configuration.

    At the moment each AutoTest will always only have one AutoTestRun.
    """
    __tablename__ = 'AutoTestRun'

    auto_test_id = db.Column(
        'auto_test_id',
        db.Integer,
        db.ForeignKey('AutoTest.id', ondelete='CASCADE'),
        nullable=False
    )

    setup_stdout = deferred(
        db.Column(
            'setup_stdout',
            db.Unicode,
            default=None,
        )
    )

    setup_stderr = deferred(
        db.Column(
            'setup_stderr',
            db.Unicode,
            default=None,
        )
    )

    runners = db.relationship(
        lambda: AutoTestRunner,
        back_populates='run',
        uselist=True,
        passive_deletes=True,
    )

    auto_test = db.relationship(
        lambda: AutoTest,
        foreign_keys=auto_test_id,
        back_populates='_runs',
        lazy='joined',
        innerjoin=True,
    )

    results = db.relationship(
        lambda: AutoTestResult,
        back_populates='run',
        cascade='all,delete',
        order_by=lambda: AutoTestResult.created_at,
        uselist=True,
        passive_deletes=True,
    )

    started_date = db.Column(
        'started_date',
        db.TIMESTAMP(timezone=True),
        nullable=True,
        default=None
    )

    kill_date = db.Column(
        'kill_date', db.TIMESTAMP(timezone=True), nullable=True, default=None
    )

    _job_number = db.Column('job_number', db.Integer, default=0)
    _job_id = db.Column('job_id', UUIDType, default=uuid.uuid4, nullable=False)

    runners_requested = db.Column(
        'runners_requested',
        db.Integer,
        default=0,
        server_default='0',
        nullable=False,
    )

    batch_run_done = db.Column(
        'batch_run_done',
        db.Boolean,
        nullable=False,
    )

    @property
    def run_hidden_steps(self) -> bool:
        """Should we run the hidden steps of this run.
        """
        # If the batch run is done we must make sure that all future runners
        # will execute the hidden steps, as otherwise they might not get
        # executed. See the method `make_result` for more explanation.
        return (
            self.batch_run_done or self.auto_test.assignment.deadline_expired
        )

    def increment_job_id(self) -> None:
        """Increment the job id of this runner.

        This should be done when creating a new runner for this run, so we can
        track each runner by this id. This is different from creating a
        completely new job id, as this will make sure we keep the same base job
        id.
        """
        cur_number = self._job_number or 0
        self._job_number = cur_number + 1

    def get_job_id(self) -> str:
        return f'{self._job_id.hex}-{self._job_number or 0}'

    def stop_runners(self, runners: t.List[AutoTestRunner]) -> bool:
        """Stop the given runners of this run.

        This function also stops the entire job at the broker if needed, or
        adjust the amount of runners requested at the broker, if needed.
        """
        assert all(runner in self.runners for runner in runners)
        all_deleted = len(runners) == len(self.runners)
        any_cleared = False

        for runner in runners:
            self.runners.remove(runner)
            runner.run_id = None
            # This function has side effects so make sure short circuiting
            # doesn't cause the function not to be called.
            cleared = self._clear_non_passed_results(runner)
            any_cleared = cleared or any_cleared

        db.session.flush()
        any_results_left = any_cleared or db.session.query(
            self.get_results_to_run().exists()
        ).scalar()

        logger.info(
            'Killed runners',
            all_deleted=all_deleted,
            any_results_left=any_results_left
        )

        if all_deleted:
            # We don't need to kill each individual runner, as the end of job
            # will kill all associated runners.
            old_job_id = self.get_job_id()

            self.runners_requested = 0
            self.increment_job_id()
            db.session.flush()
            run_id = self.id

            def after_req() -> None:
                psef.tasks.notify_broker_end_of_job(old_job_id)
                if any_results_left:
                    psef.tasks.notify_broker_of_new_job(run_id, None)

            callback_after_this_request(after_req)
        else:
            to_kill = [r.id.hex for r in runners]
            run_id = self.id
            callback_after_this_request(
                lambda: psef.tasks.kill_runners_and_adjust(run_id, to_kill)
            )

        return any_results_left

    def get_broker_result_metadata(self) -> t.Mapping[str, t.Optional[str]]:
        """Get the ``results`` metadata key for the broker.

        :returns: A mapping that should be send to the broker in the metadata
            under the ``results`` key.
        """
        ATStepResultState = auto_test_step_models.AutoTestStepResultState

        query = db.session.query(AutoTestResult).filter(
            AutoTestResult.run == self,
            AutoTestResult.work_id.in_(
                self.auto_test.assignment.get_from_latest_submissions(
                    work_models.Work.id
                )
            ),
        ).with_entities(
            sql_func.min(AutoTestResult.updated_at).filter(
                AutoTestResult.state == ATStepResultState.not_started,
            ),
            sql_func.min(AutoTestResult.started_at).filter(
                AutoTestResult.state == ATStepResultState.running,
            ),
            sql_func.max(AutoTestResult.updated_at).filter(
                AutoTestResult.state == ATStepResultState.passed,
            ),
        )

        def maybe_format(date: t.Optional[DatetimeWithTimezone]
                         ) -> t.Optional[str]:
            return cg_helpers.on_not_none(date, lambda d: d.isoformat())

        not_started, running, passed = query.one()
        return {
            'not_started': maybe_format(not_started),
            'running': maybe_format(running),
            'passed': maybe_format(passed),
        }

    def get_broker_metadata(self) -> t.Mapping[str, object]:
        """Get metadata that is useful for the broker of this run.
        """
        assig = self.auto_test.assignment

        return {
            'course': {
                'id': assig.course.id,
                'name': assig.course.name,
            },
            'assignment': {
                'id': assig.id,
                'name': assig.name,
            },
            'created_at': self.created_at.isoformat(),
            'id': self.id,
            'results': self.get_broker_result_metadata(),
            'type': 'NS',  # NS=NewStyle
        }

    def _clear_non_passed_results(self, runner: AutoTestRunner) -> bool:
        """Clear all results of the given ``runner`` that are not yet finished.

        :param runner: The runner to clear the non finished results of.
        :returns: ``True`` if any results where cleared, ``False`` otherwise.
        """
        any_cleared = False

        for result in self.results:
            if result.runner == runner and not result.is_finished:
                result.clear()
                any_cleared = True

        return any_cleared

    def get_amount_needed_runners(self) -> int:
        """Get the amount of runners this run needs.
        """
        amount_not_done = self.get_results_to_run().count()
        max_per = site_settings.Opt.AUTO_TEST_MAX_JOBS_PER_RUNNER.value
        return math.ceil(amount_not_done / max_per)

    @classmethod
    def get_runs_that_need_runners(cls) -> t.List['AutoTestRun']:
        """Get all runs that need more runners.

        This function gets all runs that have fewer runners than they should,
        which is calculated using the amount of results that have not yet
        started.
        """
        ARR = AutoTestRunner
        ARS = AutoTestResult

        amount_results = sql_func.count(distinct(ARS.id))
        amount_runners = sql_func.count(distinct(ARR.id))

        runs = db.session.query(cls).join(
            ARS,
            and_(
                ARS.auto_test_run_id == cls.id,
                (
                    ARS._state ==  # pylint: disable=protected-access
                    auto_test_step_models.AutoTestStepResultState.not_started
                ),
            ),
        ).join(
            ARR,
            ARR.run_id == cls.id,
            isouter=True,
        ).having(
            or_(
                amount_runners == 0,
                (
                    amount_results / amount_runners >
                    site_settings.Opt.AUTO_TEST_MAX_JOBS_PER_RUNNER.value
                ),
            )
        ).group_by(cls.id).order_by(
            nullsfirst(
                (
                    amount_results / case(
                        [(amount_runners == 0, None)],
                        else_=amount_runners,
                    )
                ).desc()
            )
        ).options(orm.noload(cls.auto_test))

        return runs.all()

    def get_results_latest_submissions(self) -> MyQuery[AutoTestResult]:
        """Get the results for the latest submissions.

        :returns: A query that returns the results for the latest submissions
            of the connected assignment.
        """
        latest_ids = self.auto_test.assignment.get_from_latest_submissions(
            work_models.Work.id
        )

        return db.session.query(AutoTestResult).filter_by(
            auto_test_run_id=self.id,
        ).filter(
            t.cast(DbColumn[int], AutoTestResult.work_id).in_(latest_ids)
        ).order_by(AutoTestResult.created_at)

    def get_results_to_run(self) -> MyQuery[AutoTestResult]:
        """Get a query to get the :py:class:`.AutoTestResult` items that still
            need to be run.
        """
        return self.get_results_latest_submissions().filter_by(
            _state=auto_test_step_models.AutoTestStepResultState.not_started,
        )

    def add_active_runner(
        self,
        runner_ipaddr: str,
    ) -> AutoTestRunner:
        """Start this run.

        This means setting the ``started_date``, creating a runner object for
        this run, and scheduling some tasks that will kill the runner after
        some period of time.

        .. note::

            To start an entire run you should use :meth:`.AutoTest.start_run`.

        :param runner_ipaddr: The ip address of the runner that will perform
            this run. This is used for authentication purposes.
        """
        # This run was not started before this runner, so set all the auxiliary
        # data.
        if self.started_date is None:
            self.started_date = DatetimeWithTimezone.utcnow()
            # Continuous feedback runs don't get killed because of time, so
            # don't set this data.
        runner = AutoTestRunner.create(runner_ipaddr, run=self)
        db.session.add(runner)
        db.session.flush()
        runner_hex_id = runner.id.hex

        @psef.helpers.callback_after_this_request
        def __start_tasks() -> None:
            psef.tasks.check_heartbeat_auto_test_run((runner_hex_id, ))

        return runner

    def get_instructions(
        self, for_runner: AutoTestRunner
    ) -> auto_test_module.RunnerInstructions:
        """Get the instructions to run this AutoTestRun.
        """
        results = self.get_results_to_run().all()
        heartbeat_interval = (
            site_settings.Opt.AUTO_TEST_HEARTBEAT_INTERVAL.value
        )

        return {
            'runner_id': str(for_runner.id),
            'run_id': self.id,
            'auto_test_id': self.auto_test_id,
            'result_ids': [r.id for r in results],
            'student_ids': [r.work.user_id for r in results],
            'student_infos': [self._get_student_info(r) for r in results],
            'assignment_info': self._get_assignment_info(),
            'sets': [s.get_instructions(self) for s in self.auto_test.sets],
            'fixtures': [(f.name, f.id) for f in self.auto_test.fixtures],
            'setup_script': self.auto_test.setup_script,
            'heartbeat_interval': round(heartbeat_interval.total_seconds()),
            'run_setup_script': self.auto_test.run_setup_script,
            # TODO: Set this in a more intelligent way
            'poll_after_done': True,
        }

    def _get_assignment_info(self) -> auto_test_module.AssignmentInformation:
        """Get information about the assignment that should be available in the
        AutoTest environment.
        """
        deadline = self.auto_test.assignment.deadline

        if deadline is None:
            return {'deadline': None}
        else:
            return {'deadline': deadline.isoformat()}

    @staticmethod
    def _get_student_info(
        result: AutoTestResult
    ) -> auto_test_module.StudentInformation:
        """Get information about the submission that should be available in the
        AutoTest environment.

        :param result: The result to get the information for.
        """
        return {
            'result_id': result.id,
            'student_id': result.work.user_id,
            'created_at': result.work.created_at.isoformat(),
        }

    class AsJSON(TypedDict):
        """The run as JSON.
        """
        #: The id of this run.
        id: int
        #: The moment the run was created.
        created_at: DatetimeWithTimezone
        #: The state it is in. This is only kept for backwards compatibility
        #: reasons, it will always be "running".
        state: Literal['running']
        #: Also not used anymore, will always be ``false``.
        is_continuous: bool

    class AsExtendedJSON(AsJSON, TypedDict):
        """The run as extended JSON.
        """
        #: The results in this run. This will only contain the result for the
        #: latest submissions.
        results: t.List[AutoTestResult]
        #: The stdout output of the ``run_setup_script``
        setup_stdout: str
        #: The stderr output of the ``run_setup_script``
        setup_stderr: str

    def __to_json__(self) -> AsJSON:
        return {
            'id': self.id,
            'created_at': self.created_at,
            'state': 'running',
            'is_continuous': False,
        }

    def __extended_to_json__(self) -> AsExtendedJSON:
        all_results: t.Iterable[AutoTestResult]
        if psef.helpers.jsonify_options.get_options().latest_only:
            all_results = self.get_results_latest_submissions()
        else:
            all_results = [r for r in self.results if not r.work.deleted]

        results = [
            result for result in all_results
            if auth.AutoTestResultPermissions(result).ensure_may_see.as_bool()
        ]

        # TODO: Check permissions for setup_stdout/setup_stderr
        return make_typed_dict_extender(
            self.__to_json__(), self.AsExtendedJSON
        )(
            results=results,
            setup_stdout=self.setup_stdout or '',
            setup_stderr=self.setup_stderr or '',
        )

    def delete_and_clear_rubric(self) -> None:
        """Delete this AutoTestRun and clear all the results and rubrics.

        This method will also delete all the existing attachments for step
        results.
        """
        for result in self.results:
            result.clear_rubric()

        ATResult = auto_test_step_models.AutoTestStepResult  # pylint: disable=invalid-name

        results_with_attachment = ATResult.query.filter(
            ATResult.has_attachment,
            ATResult.auto_test_result_id.in_(
                [result.id for result in self.results]
            )
        ).all()

        if results_with_attachment:
            attachments = [r.attachment for r in results_with_attachment]

            def after_req() -> None:
                for attachment in attachments:
                    try:
                        attachment.if_just(lambda a: a.delete())
                    # pylint: disable=broad-except
                    except BaseException:  # pragma: no cover
                        pass

            callback_after_this_request(after_req)

        db.session.delete(self)

    @property
    def new_results_should_be_final(self) -> bool:
        """Should new results (or newly clear results) be final results.

        :returns: The result should the value of ``final_result`` of the
            :class:`.AutoTestResult`.
        """
        return self.batch_run_done or not self.auto_test.has_hidden_steps

    def make_result(
        self, work_id: t.Union[int, 'work_models.Work']
    ) -> AutoTestResult:
        """Make a result for this run.

        :param work_id: The work, or its id, for which we should make a result.
        :returns: The created result.
        """
        # Setting `final_result` here is a bit tricky. We know we can start
        # making final results when the deadline expired. However, there might
        # be a runner active that was started **before** the deadline, so this
        # runner didn't receive the hidden steps. This runner might run this
        # final result before it is stopped (as there can be quite a
        # significant delay before the _run_autotest_batch_runs_1 celery task
        # is executed), and the result would be the hidden steps are not yet
        # run. So for the moment we simply set it to the value of
        # `batch_run_done`, as we know that all runners have the hidden steps
        # if this value is `True`. Finally, if a test does not have hidden
        # steps, we always execute the complete test, so we can simply
        # `final_result` to `True`.

        if isinstance(work_id, work_models.Work):
            return AutoTestResult(
                work=work_id,
                auto_test_run_id=self.id,
                final_result=self.new_results_should_be_final
            )
        return AutoTestResult(
            work_id=work_id,
            auto_test_run_id=self.id,
            final_result=(
                self.batch_run_done or not self.auto_test.has_hidden_steps
            )
        )

    def do_batch_run(self) -> None:
        """Do the batch run for this run.
        """
        hidden = self.auto_test.has_hidden_steps
        logger.info('Doing batch run', run_id=self.id, has_hidden_steps=hidden)
        # We do not need to clear if the config has no hidden steps, are
        # already run in this case.
        if hidden:
            for result in self.get_results_latest_submissions():
                result.clear()
                result.final_result = True

            db.session.flush()
            # This also starts new runners if needed
            self.stop_runners(self.runners)

        self.batch_run_done = True


@auto_test_grade_calculators.register('full')
def _full_grade_calculator(
    items: t.Sequence['psef.models.RubricItem'], percentage: float
) -> 'psef.models.RubricItem':
    """Calculate a grade based on the ``full`` policy.

    >>> _full_grade_calculator([0,1,2,3], 0.25)
    0
    >>> _full_grade_calculator([0,1,2,3], 0.5)
    1
    >>> _full_grade_calculator([0,1,2,3], 0.75)
    2
    >>> _full_grade_calculator([0,1,2,3], 1)
    3
    >>> _full_grade_calculator([0,1,2,3], 0.9)
    2
    >>> _full_grade_calculator([0,1,2,3], 0)
    0
    >>> _full_grade_calculator([0,1,2,3], 0.1)
    0
    """
    return items[max(0, int(len(items) * percentage) - 1)]


@auto_test_grade_calculators.register('partial')
def _partial_grade_calculator(
    items: t.Sequence['psef.models.RubricItem'], percentage: float
) -> 'psef.models.RubricItem':
    """Calculate a grade based on the ``partial`` policy.

    >>> _partial_grade_calculator([0,1,2,3], 1)
    3
    >>> _partial_grade_calculator([0,1,2,3], 0.9)
    3
    >>> _partial_grade_calculator([0,1,2,3], 0)
    0
    >>> _partial_grade_calculator([0,1,2,3], 0.1)
    0
    >>> _partial_grade_calculator([0,1,2,3], 0.25)
    1
    """
    return items[min(len(items) - 1, int(len(items) * percentage))]


class AutoTest(Base, TimestampMixin, IdMixin):
    """This class represents a auto test.

    A group set is a single wrapper over all groups. Every group is part of a
    group set. The group set itself is connected to a single course and zero or
    more assignments in this course.

    :ivar minimum_size: The minimum size of that group should have before it
        can be used to submit a submission.
    :ivar maximum_size: The maximum amount of members a group can ever have.
    """
    __tablename__ = 'AutoTest'

    id = db.Column('id', db.Integer, primary_key=True)

    assignment = db.relationship(
        lambda: psef.models.Assignment,
        back_populates='auto_test',
        innerjoin=True,
        uselist=False,
    )
    sets = db.relationship(
        lambda: AutoTestSet,
        back_populates="auto_test",
        cascade='all,delete,delete-orphan',
        order_by=lambda: AutoTestSet.created_at,
        uselist=True,
    )

    _runs = db.relationship(
        lambda: AutoTestRun,
        back_populates="auto_test",
        cascade='all,delete,delete-orphan',
        order_by=lambda: AutoTestRun.created_at,
        uselist=True,
        passive_deletes=True,
    )

    @property
    def run(self) -> t.Optional[AutoTestRun]:
        """The final run of this AutoTest.

        :returns: The final run of this AutoTest or ``None`` if there is none.
        """
        return self._runs[0] if self._runs else None

    def get_all_runs(self) -> t.Sequence[AutoTestRun]:
        return self._runs

    fixtures = db.relationship(
        lambda: psef.models.AutoTestFixture,
        back_populates="auto_test",
        cascade='all,delete',
        order_by=lambda: psef.models.AutoTestFixture.name,
        uselist=True,
    )

    setup_script = db.Column(
        'setup_script', db.Unicode, nullable=False, default=''
    )
    run_setup_script = db.Column(
        'run_setup_script', db.Unicode, nullable=False, default=''
    )
    finalize_script = db.Column(
        'finalize_script', db.Unicode, nullable=False, default=''
    )

    _grade_calculation = db.Column(
        'grade_calculation',
        db.Enum(
            *auto_test_grade_calculators.keys(), name='grade_calculation_enum'
        ),
        nullable=True,
        default=None,
    )

    results_always_visible = db.Column(
        'results_always_visible',
        db.Boolean,
        nullable=True,
        default=None,
    )

    prefer_teacher_revision = db.Column(
        'prefer_teacher_revision',
        db.Boolean,
        nullable=True,
        default=None,
    )

    def ensure_no_runs(self) -> None:
        """Ensure that this AutoTest has no runs.

        :raises APIException: If the AutoTest has one or more runs.
        """
        if self.run is not None:
            raise APIException(
                'You cannot update an AutoTest which has runs',
                f'The given AutoTest "{self.id}" has a run',
                APICodes.INVALID_STATE, 409
            )

    @property
    def grade_calculator(self) -> t.Optional[GradeCalculator]:
        """Get the grade calculator for this AutoTest.

        >>> AutoTest().grade_calculator is None
        True
        """
        if self._grade_calculation is None:
            return None
        return auto_test_grade_calculators.get(self._grade_calculation)

    @grade_calculator.setter
    def grade_calculator(self, new_val: GradeCalculator) -> None:
        """Set the grade calculator for this AutoTest.

        This should be a registered grade calculator.

        :param new_val: The new grade calculator.
        """
        key = auto_test_grade_calculators.find(new_val, None)
        assert key is not None
        self._grade_calculation = key

    def _ensure_can_start_run(self) -> None:
        if self.grade_calculator is None:
            raise InvalidStateException(
                'This AutoTest has no grade_calculation set, but this option'
                ' is required.'
            )
        elif self.results_always_visible is None:
            raise InvalidStateException(
                'This AutoTest does not have a results_always_visible set, but'
                ' this option is required'
            )
        elif self.prefer_teacher_revision is None:
            raise InvalidStateException(
                'This AutoTest does not have prefer_teacher_revision set, but'
                ' this option is required'
            )
        elif not self.sets:
            raise InvalidStateException(
                'This AutoTest has no sets, so it cannot be started'
            )
        elif next(self.all_suites, None) is None:
            raise InvalidStateException(
                'This AutoTest has no suites, so it cannot be started'
            )
        elif any(not s.steps for s in self.all_suites):
            raise InvalidStateException(
                'This AutoTest has no steps in some suites, so it cannot be'
                ' started'
            )
        elif any(
            sum(st.weight for st in s.steps) <= 0 for s in self.all_suites
        ):
            raise InvalidStateException(
                'This AutoTest has zero amount of points possible in some'
                ' suites, so it cannot be started'
            )

    def start_test_run(self) -> AutoTestRun:
        """Start this AutoTest run.

        This function checks if the AutoTest is in a state where a run can be
        started, and if this is the case it starts the run. It also schedules a
        task to notify our broker that we need a runner. The changes to the
        database are not committed!
        """
        self._ensure_can_start_run()

        if self.run is not None:
            raise APIException(
                'You cannot start an AutoTest which has runs',
                f'The given AutoTest "{self.id}" has a run',
                APICodes.INVALID_STATE, 409
            )

        run = AutoTestRun(
            batch_run_done=(
                not self.has_hidden_steps or self.assignment.deadline_expired
            ),
            auto_test=self,
        )
        self._runs.append(run)
        db.session.flush()

        work_ids = self.assignment.get_from_latest_submissions(
            work_models.Work.id
        )
        results = [run.make_result(work_id) for work_id, in work_ids]
        db.session.bulk_save_objects(results)
        if results:
            psef.helpers.callback_after_this_request(
                lambda: psef.tasks.notify_broker_of_new_job(run.id, None)
            )
        return run

    @property
    def has_hidden_steps(self) -> bool:
        """Are there hidden steps in this AutoTest.
        """
        return any(
            any(step.hidden for step in suite.steps)
            for suite in self.all_suites
        )

    @property
    def all_suites(self) -> t.Iterator[AutoTestSuite]:
        """Get all the suites from this AutoTest as an iterator.
        """
        return itertools.chain.from_iterable(s.suites for s in self.sets)

    @staticmethod
    @signals.WORK_CREATED.connect_immediate
    def add_to_run(work: 'work_models.Work') -> bool:
        """Add the given work to the continuous feedback run.

        This function only does something if there is an continuous feedback
        run.

        :param work: The work to add to the continuous feedback run.
        :returns: ``True`` if the work was added to the continuous feedback
            run.

        .. warning::

            This function changes the session if it returns ``True``, so a
            commit is necessary in that case.
        """
        self = work.assignment.auto_test
        if self is None or self.run is None:
            return False

        run = self.run

        run_id = run.id
        AutoTestResult.get_results_by_user(work.user_id).filter(
            AutoTestResult.auto_test_run_id == run.id,
            t.cast(DbColumn[object], AutoTestResult.state).in_(
                auto_test_step_models.AutoTestStepResultState.
                get_not_finished_states()
            ),
        ).update(
            {
                t.cast(DbColumn, AutoTestResult.state):
                    auto_test_step_models.AutoTestStepResultState.skipped,
            }, False
        )

        def callbacks() -> None:
            psef.tasks.adjust_amount_runners(
                run_id, always_update_latest_results=True
            )

        psef.helpers.callback_after_this_request(callbacks)

        result = run.make_result(work)
        db.session.add(result)
        return True

    @staticmethod
    @signals.WORK_DELETED.connect(
        'immediate',
        pre_check=lambda wd: wd.was_latest,
        converter=lambda x: x,
    )
    def _on_work_deletion(work_deletion: signals.WorkDeletedData) -> None:
        self = work_deletion.deleted_work.assignment.auto_test
        if self is None or self.run is None:
            return

        if work_deletion.new_latest:
            self.reset_work(work_deletion.new_latest)

        callback_after_this_request(
            lambda: psef.tasks.update_latest_results_in_broker(self.run.id)
        )

    def reset_work(self, work: 'work_models.Work') -> None:
        """Reset the result beloning to the given work.

        If there is not result for the given result, a result is created.

        :param work: The work for which we should reset the work.
        :returns: Nothing.
        """
        run = self.run
        assert run is not None, 'Cannot reset work on AutoTest without run'

        run_id = run.id
        result = AutoTestResult.get_results_by_user(work.user_id).filter_by(
            auto_test_run_id=run_id, work_id=work.id
        ).one_or_none()

        if result is None:
            self.add_to_run(work)
        else:
            result.clear()
            if not result.final_result:
                result.final_result = run.new_results_should_be_final
            psef.helpers.callback_after_this_request(
                lambda: psef.tasks.adjust_amount_runners(run_id)
            )

    class AsJSON(TypedDict):
        """An AutoTest as JSON.
        """
        #: This id of this AutoTest
        id: int
        #: The fixtures connected to this AutoTest
        fixtures: t.Sequence['psef.models.AutoTestFixture']
        #: The setup script that will be executed before any test starts.
        run_setup_script: str
        #: The setup script that will be executed for each student. In this
        #: script the submission of the student is available.
        setup_script: str
        #: Unused
        finalize_script: str
        #: The way the grade is calculated in this AutoTest. This is ``null``
        #: if the options is still unset. This can be 'full' or 'partial'.
        grade_calculation: t.Optional[str]
        #: The sets in this AutoTest. In the UI these are called levels.
        sets: t.List[AutoTestSet]
        #: The id of the assignment to which this AutoTest belongs.
        assignment_id: int
        #: The runs done with this AutoTest. This is list is always of length 0
        #: or 1
        runs: t.List[AutoTestRun]
        #: If ``true`` the results are visible for students before the
        #: deadline. This is also called "continuous feedback mode". This is
        #: ``null`` if the options is still unset.
        results_always_visible: t.Optional[bool]
        #: If ``true`` the teacher revision will be used for testing if it is
        #: available for a student. This is ``null`` if the options is still
        #: unset.
        prefer_teacher_revision: t.Optional[bool]

    def __to_json__(self) -> AsJSON:
        """Covert this AutoTest to json.
        """
        fixtures = [
            f for f in self.fixtures
            if auth.AutoTestFixturePermissions(f).ensure_may_see.as_bool()
        ]

        return {
            'id': self.id,
            'fixtures': fixtures,
            'setup_script': self.setup_script,
            'run_setup_script': self.run_setup_script,
            'finalize_script': self.finalize_script,
            'grade_calculation': self._grade_calculation,
            'sets': self.sets,
            'assignment_id': self.assignment.id,
            'runs': self._runs,
            'results_always_visible': self.results_always_visible,
            'prefer_teacher_revision': self.prefer_teacher_revision,
        }

    def copy(
        self,
        rubric_mapping: (
            t.Mapping['psef.models.RubricRow', 'psef.models.RubricRow']
        ),
        putter: cg_object_storage.Putter,
    ) -> 'AutoTest':
        """Copy this AutoTest configuration.

        :param rubric_mapping: The mapping how the rubric was copied, if suite
            ``A`` was copied to suite ``B`` then suite ``B`` is connected to
            rubric row ``rubric_mapping[A.rubric_row]``.
        :param putter: The putter used to copy fixtures.
        :returns: The copied AutoTest config.

        .. note::

            The caller still needs to connect the copied config to an
            assignment.
        """
        res = AutoTest(
            sets=[s.copy() for s in self.sets],
            fixtures=[fixture.copy(putter) for fixture in self.fixtures],
            setup_script=self.setup_script,
            run_setup_script=self.run_setup_script,
            finalize_script=self.finalize_script,
            results_always_visible=self.results_always_visible,
            _grade_calculation=self._grade_calculation,
            prefer_teacher_revision=self.prefer_teacher_revision,
        )
        for suite in res.all_suites:
            suite.rubric_row = rubric_mapping[suite.rubric_row]
        return res
