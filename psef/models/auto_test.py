"""This module defines all models needed for auto tests.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import enum
import uuid
import typing as t
import numbers
import datetime

from sqlalchemy import orm
from sqlalchemy.types import JSON
from sqlalchemy_utils import UUIDType

import psef

from . import Base, DbColumn, db
from . import file as file_models
from . import work as work_models
from . import rubric as rubric_models
from . import _MyQuery
from . import assignment as assignment_models
from .. import auto_test as auto_test_module
from .mixins import IdMixin, UUIDMixin, TimestampMixin
from ..exceptions import APICodes, APIException

if t.TYPE_CHECKING:
    from . import user as user_models


class AutoTestStep(Base, TimestampMixin, IdMixin):
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AutoTestStep']]
    __tablename__ = 'AutoTestStep'
    id: int = db.Column('id', db.Integer, primary_key=True)

    order = db.Column('order', db.Integer, nullable=False)

    name: str = db.Column('name', db.Unicode, nullable=False)
    weight: float = db.Column('weight', db.Float, nullable=False)

    hidden: bool = db.Column('hidden', db.Boolean, nullable=False)

    auto_test_suite_id: int = db.Column(
        'auto_test_suite_id',
        db.Integer,
        db.ForeignKey('AutoTestSuite.id'),
        nullable=False
    )

    auto_test_suite: 'AutoTestSuite' = db.relationship(
        'AutoTestSuite',
        foreign_keys=auto_test_suite_id,
        back_populates='steps',
        lazy='joined',
        innerjoin=True,
    )

    _test_type: str = db.Column(
        'test_type',
        db.Enum(
            *auto_test_module.auto_test_handlers.keys(), native_enum=False
        ),
        nullable=False,
    )

    _data: 'psef.helpers.JSONType' = db.Column(
        'data', JSON, nullable=False, default={}
    )

    @property
    def test_type(self) -> t.Type[auto_test_module.TestStep]:
        return auto_test_module.auto_test_handlers[self._test_type]

    @test_type.setter
    def test_type(self, test_type: t.Type[auto_test_module.TestStep]) -> None:
        typ = auto_test_module.auto_test_handlers.find(test_type, None)
        assert typ is not None
        self._test_type = typ

    @property
    def data(self) -> 'psef.helpers.JSONType':
        return self._data

    @data.setter
    def data(self, data: 'psef.helpers.JSONType') -> None:
        self.test_type.validate_data(data)
        self._data = data

    @property
    def step(self) -> auto_test_module.TestStep:
        return self.test_type(self.data)

    def update_from_json(
        self, json: t.Dict[str, 'psef.helpers.JSONType']
    ) -> None:
        self.test_type.validate_data(json)
        self.data = json

    def get_instructions(self) -> auto_test_module.StepInstructions:
        return {
            'id': self.id,
            'weight': self.weight,
            'test_type_name': self._test_type,
            'data': self.data,
        }

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': self.id,
            'name': self.name,
            'type': self._test_type,
            'weight': self.weight,
            'data': self.data,
            'hidden': self.hidden
        }


class AutoTestSuite(Base, TimestampMixin, IdMixin):
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AutoTestSuite']]
    __tablename__ = 'AutoTestSuite'
    id: int = db.Column('id', db.Integer, primary_key=True)

    rubric_row_id: int = db.Column(
        'rubric_row_id',
        db.Integer,
        db.ForeignKey('RubricRow.id'),
        nullable=False
    )
    rubric_row: 'rubric_models.RubricRow' = db.relationship(
        'RubricRow',
        foreign_keys=rubric_row_id,
        innerjoin=True,
    )

    auto_test_set_id: int = db.Column(
        'auto_test_set_id',
        db.Integer,
        db.ForeignKey('AutoTestSet.id'),
        nullable=False
    )

    auto_test_set: 'AutoTestSet' = db.relationship(
        'AutoTestSet',
        foreign_keys=auto_test_set_id,
        back_populates='suites',
        lazy='joined',
        innerjoin=True,
    )

    steps = db.relationship(
        "AutoTestStep",
        back_populates="auto_test_suite",
        cascade='all,delete',
        order_by='AutoTestStep.order'
    )  # type: t.MutableSequence[AutoTestStep]

    def get_instructions(self) -> auto_test_module.SuiteInstructions:
        return {
            'id': self.id,
            'steps': [s.get_instructions() for s in self.steps],
        }

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': self.id,
            'steps': self.steps,
            'rubric_row': self.rubric_row,
        }


class AutoTestStepResultState(enum.Enum):
    not_started = enum.auto()
    running = enum.auto()
    passed = enum.auto()
    failed = enum.auto()
    timed_out = enum.auto()


class AutoTestStepResult(Base, TimestampMixin, IdMixin):
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AutoTestStepResult']]

    auto_test_step_id: int = db.Column(
        'auto_test_step_id',
        db.Integer,
        db.ForeignKey('AutoTestStep.id'),
        nullable=False
    )

    auto_test_step: AutoTestStep = db.relationship(
        'AutoTestStep',
        foreign_keys=auto_test_step_id,
        lazy='joined',
        innerjoin=True,
    )

    auto_test_result_id = db.Column(
        'auto_test_result_id',
        db.Integer,
        db.ForeignKey('AutoTestResult.id'),
    )

    auto_test_result: 'AutoTestResult' = db.relationship(
        'AutoTestResult',
        foreign_keys=auto_test_result_id,
        innerjoin=True,
        back_populates='step_results',
    )

    state = db.Column(
        'state',
        db.Enum(AutoTestStepResultState),
        default=AutoTestStepResultState.not_started,
        nullable=False,
    )

    log: 'psef.helpers.JSONType' = db.Column(
        'log',
        JSON,
        nullable=True,
        default=None,
    )

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': self.id,
            'auto_test_step': self.auto_test_step,
            'state': self.state.name,
            'log': self.log,
        }


class AutoTestSet(Base, TimestampMixin, IdMixin):
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AutoTestSet']]
    __tablename__ = 'AutoTestSet'

    id: int = db.Column('id', db.Integer, primary_key=True)
    stop_points: float = db.Column(
        'stop_points', db.Float, nullable=False, default=0
    )
    auto_test_id: int = db.Column(
        'auto_test_id',
        db.Integer,
        db.ForeignKey('AutoTest.id'),
        nullable=False
    )

    auto_test: 'AutoTest' = db.relationship(
        'AutoTest',
        foreign_keys=auto_test_id,
        back_populates='sets',
        lazy='joined',
        innerjoin=True,
    )

    suites = db.relationship(
        "AutoTestSuite", back_populates="auto_test_set", cascade='all,delete'
    )  # type: t.MutableSequence[AutoTestSuite]

    def get_instructions(self) -> auto_test_module.SetInstructions:
        return {
            'id': self.id,
            'suites': [s.get_instructions() for s in self.suites],
            'stop_points': self.stop_points,
        }

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': self.id,
            'suites': self.suites,
            'stop_points': self.stop_points,
        }


class AutoTestResult(Base, TimestampMixin, IdMixin):
    __tablename__ = 'AutoTestResult'

    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AutoTestResult']]

    auto_test_run_id: int = db.Column(
        'auto_test_run_id',
        db.Integer,
        db.ForeignKey('AutoTestRun.id'),
        nullable=False
    )

    run: 'AutoTestRun' = db.relationship(
        'AutoTestRun',
        foreign_keys=auto_test_run_id,
        back_populates='results',
        lazy='joined',
        innerjoin=True,
    )

    setup_stdout: t.Optional[str] = orm.deferred(
        db.Column(
            'setup_stdout',
            db.Unicode,
            default=None,
        )
    )

    setup_stderr: t.Optional[str] = orm.deferred(
        db.Column(
            'setup_stderr',
            db.Unicode,
            default=None,
        )
    )

    step_results = db.relationship(
        'AutoTestStepResult',
        back_populates='auto_test_result',
        cascade='all,delete',
        order_by='AutoTestStepResult.created_at'
    )  # type: t.MutableSequence[AutoTestStepResult]

    points_achieved: float = db.Column(
        'points_achieved', db.Float, nullable=True, default=None
    )

    state = db.Column(
        'state',
        db.Enum(AutoTestStepResultState),
        default=AutoTestStepResultState.not_started,
        nullable=False,
    )

    work_id: int = db.Column(
        'work_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
    )
    work = db.relationship(
        'Work', foreign_keys=work_id
    )  # type: work_models.Work

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'work': self.work,
            'state': self.state.name,
            'points_achieved': self.points_achieved,
        }

    def __extended_to_json__(self) -> t.Mapping[str, object]:
        return {
            **self.__to_json__(),
            'step_results': self.step_results,
        }


class AutoTestRunState(enum.Enum):
    not_started = enum.auto()
    running = enum.auto()
    done = enum.auto()
    timed_out = enum.auto()


class AutoTestRunner(Base, TimestampMixin, UUIDMixin):
    __tablename__ = 'AutoTestRunner'

    _type: str = db.Column(
        'type',
        db.Enum(*auto_test_module.auto_test_runners.keys(), native_enum=False),
        nullable=False
    )

    _ipaddr: str = db.Column('ipaddr', db.Unicode, nullable=False)

    run: 'AutoTestRun' = db.relationship(
        "AutoTestRun",
        back_populates="runner",
        cascade='all,delete',
        order_by='AutoTestRun.created_at',
        uselist=False
    )

    def after_run(self) -> None:
        self.runner_type.after_run(self)

    @property
    def ipaddr(self) -> str:
        return self._ipaddr

    @property
    def runner_type(self) -> t.Type['auto_test_module.AutoTestRunner']:
        return auto_test_module.auto_test_runners[self._type]

    @classmethod
    def create(
        cls,
        typ: t.Type[auto_test_module.AutoTestRunner],
        ipaddr: str,
    ) -> 'AutoTestRunner':
        _type_name = auto_test_module.auto_test_runners.find(typ, None)
        assert _type_name is not None

        return cls(
            _type=_type_name,
            _ipaddr=ipaddr,
        )


class AutoTestRun(Base, TimestampMixin, IdMixin):
    __tablename__ = 'AutoTestRun'

    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AutoTestRun']]

    auto_test_id: int = db.Column(
        'auto_test_id',
        db.Integer,
        db.ForeignKey('AutoTest.id'),
        nullable=False
    )

    runner_id: uuid.UUID = db.Column(
        'runner_id',
        UUIDType,
        db.ForeignKey('AutoTestRunner.id'),
        nullable=True,
        default=None,
    )

    runner: 'AutoTestRunner' = db.relationship(
        'AutoTestRunner',
        foreign_keys=runner_id,
        back_populates='run',
    )

    auto_test: 'AutoTest' = db.relationship(
        'AutoTest',
        foreign_keys=auto_test_id,
        back_populates='runs',
        lazy='joined',
        innerjoin=True,
    )

    results = db.relationship(
        'AutoTestResult',
        back_populates='run',
        cascade='all,delete',
        order_by='AutoTestResult.created_at'
    )  # type: t.MutableSequence[AutoTestResult]

    state = db.Column(
        'state',
        db.Enum(AutoTestRunState, native_enum=False),
        default=AutoTestRunState.not_started,
        nullable=False,
    )
    started_date: t.Optional[datetime.datetime] = db.Column(
        'started_date', db.DateTime, nullable=True, default=None
    )
    kill_date: t.Optional[datetime.datetime] = db.Column(
        'kill_date', db.DateTime, nullable=True, default=None
    )

    def start(
        self,
        runner_type: t.Type['auto_test_module.AutoTestRunner'],
        runner_ipaddr: str,
    ) -> None:
        assert self.started_date is None
        self.started_date = datetime.datetime.utcnow()
        max_duration = datetime.timedelta(
            minutes=psef.app.config['AUTO_TEST_MAX_TIME_TOTAL_RUN'],
        )
        now = datetime.datetime.utcnow()
        self.kill_date = now + max_duration
        self.runner = AutoTestRunner.create(runner_type, runner_ipaddr)
        psef.tasks.notify_slow_auto_test_run(
            (self.id, ), eta=now + (max_duration / 2)
        )
        psef.tasks.stop_auto_test_run((self.id, ), eta=self.kill_date)

    def get_instructions(self) -> auto_test_module.RunnerInstructions:
        return {
            'runner_id':
                str(self.runner.id),
            'run_id':
                self.id,
            'auto_test_id':
                self.auto_test_id,
            'result_ids': [r.id for r in self.results],
            'sets': [s.get_instructions() for s in self.auto_test.sets],
            'base_systems':
                t.cast(t.List[t.Dict[str, str]], self.auto_test.base_systems),
            'fixtures': [(f.name, f.id) for f in self.auto_test.fixtures],
            'setup_script':
                self.auto_test.setup_script,
        }

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
        }

    def __extended_to_json__(self) -> t.Mapping[str, object]:
        return {
            **self.__to_json__(),
            'results': self.results,
        }


class AutoTest(Base, TimestampMixin, IdMixin):
    """This class represents a auto test.

    A group set is a single wrapper over all groups. Every group is part of a
    group set. The group set itself is connected to a single course and zero or
    more assignments in this course.

    :ivar minimum_size: The minimum size of that group should have before it
        can be used to submit a submission.
    :ivar maximum_size: The maximum amount of members a group can ever have.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AutoTest']]
    __tablename__ = 'AutoTest'

    id: int = db.Column('id', db.Integer, primary_key=True)

    base_systems: 'psef.helpers.JSONType' = db.Column(
        'base_systems', JSON, nullable=False, default=[]
    )

    assignment: 'assignment_models.Assignment' = db.relationship(
        'Assignment',
        back_populates='auto_test',
        innerjoin=True,
        uselist=False
    )
    sets = db.relationship(
        "AutoTestSet",
        back_populates="auto_test",
        cascade='all,delete',
        order_by='AutoTestSet.created_at'
    )  # type: t.MutableSequence[AutoTestSet]

    runs = db.relationship(
        "AutoTestRun",
        back_populates="auto_test",
        cascade='all,delete',
        order_by='AutoTestRun.created_at'
    )  # type: t.MutableSequence[AutoTestRun]

    fixtures = db.relationship(
        'AutoTestFixture',
        back_populates="auto_test",
        cascade='all,delete',
        order_by="AutoTestFixture.name"
    )  # type: t.MutableSequence[file_models.AutoTestFixture]

    setup_script: str = db.Column('setup_script', db.Unicode, nullable=False)
    finalize_script: str = db.Column(
        'finalize_script', db.Unicode, nullable=False
    )

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': self.id,
            'fixtures': self.fixtures,
            'setup_script': self.setup_script,
            'finalize_script': self.finalize_script,
            'sets': self.sets,
            'assignment_id': self.assignment.id,
            'base_systems': self.base_systems,
            'runs': self.runs,
        }
