"""This module defines all models needed for a step of an AutoTest.

This module also contains the code needed to execute each step.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import abc
import copy
import enum
import uuid
import typing as t
import numbers
import tempfile

import regex as re
import structlog
from sqlalchemy import event
from sqlalchemy.types import JSON
from typing_extensions import TypedDict
from werkzeug.datastructures import FileStorage

import psef
import cg_enum
import cg_junit
import cg_logger
import cg_object_storage
from cg_maybe import Maybe, Nothing
from cg_dt_utils import DatetimeWithTimezone
from cg_flask_helpers import callback_after_this_request
from cg_sqlalchemy_helpers import hybrid_property, hybrid_expression
from cg_sqlalchemy_helpers.types import DbType, DbColumn, ColumnProxy
from cg_sqlalchemy_helpers.mixins import IdMixin, TimestampMixin

from . import Base, db
from . import file as file_models
from .. import auth, helpers, exceptions, current_app, site_settings
from ..helpers import (
    JSONType, between, safe_div, ensure_json_dict, get_from_map_transaction
)
from ..registry import auto_test_handlers
from ..auto_test.code_quality_wrappers import CodeQualityWrapper
from ..exceptions import (
    APICodes, APIWarnings, APIException, StopRunningStepsException
)

logger = structlog.get_logger()

T = t.TypeVar('T', bound=t.Type['AutoTestStepBase'])
TT = t.TypeVar('TT', bound='AutoTestStepBase')

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    # pylint: disable=unused-import
    from .. import auto_test as auto_test_module

_ALL_AUTO_TEST_HANDLERS = sorted(
    [
        'io_test',
        'run_program',
        'custom_output',
        'check_points',
        'junit_test',
        'code_quality',
    ]
)
_registered_test_handlers: t.Set[str] = set()


def _register(cls: T) -> T:
    name = cls.__mapper_args__['polymorphic_identity']

    assert isinstance(name, str)
    assert name in _ALL_AUTO_TEST_HANDLERS
    assert name not in _registered_test_handlers
    _registered_test_handlers.add(name)

    auto_test_handlers.register(name)(cls)
    return cls


def _ensure_program(program: str) -> None:
    if not program:
        raise APIException(
            'The program may to execute may not be empty',
            "The program to execute was empty, however it shouldn't be",
            APICodes.INVALID_PARAM, 400
        )


def _ensure_between(name: str, value: float, lower: float, upper: float) -> None:
    if value < lower or value > upper:
        raise APIException(
            f'The "{name}" has to be between 0 and 1',
            f'The "{name}" was {value} which is not >={lower} and <={upper}',
            APICodes.INVALID_PARAM, 400
        )


class AutoTestStepResultState(cg_enum.CGEnum):
    """This enum represents the states the result of a step can be in.

    A single step result will probably be in multiple states during its
    existence.
    """
    #: The step has not yet started running.
    not_started = enum.auto()
    #: The step is currently running
    running = enum.auto()
    #: The step has passed, this does not mean necessarily that the student has
    #: achieved any points.
    passed = enum.auto()
    #: The step has failed, the student will not receive any points.
    failed = enum.auto()
    #: The step has exceeded the time limit.
    timed_out = enum.auto()
    #: The step has been skipped for whatever reason.
    skipped = enum.auto()

    @classmethod
    def get_not_finished_states(cls) -> t.Sequence['AutoTestStepResultState']:
        """Get all states that are not finished.
        """
        return [cls.not_started, cls.running]

    @classmethod
    def get_finished_states(cls) -> t.Collection['AutoTestStepResultState']:
        """Get all states that are considered finished.
        """
        return {cls.skipped, cls.timed_out, cls.failed, cls.passed}


class AutoTestStepBase(Base, TimestampMixin, IdMixin):
    """The base class that every step inherits.

    This class provides represents a single step, and contains the code needed
    to execute it.
    """
    SUPPORTS_ATTACHMENT: t.ClassVar[bool] = False

    __tablename__ = 'AutoTestStep'

    id = db.Column('id', db.Integer, primary_key=True)

    order = db.Column('order', db.Integer, nullable=False)

    name = db.Column('name', db.Unicode, nullable=False)
    _weight = db.Column('weight', db.Float, nullable=False)

    hidden = db.Column('hidden', db.Boolean, nullable=False)

    auto_test_suite_id = db.Column(
        'auto_test_suite_id',
        db.Integer,
        db.ForeignKey('AutoTestSuite.id', ondelete='CASCADE'),
        nullable=False
    )

    suite = db.relationship(
        lambda: psef.models.AutoTestSuite,
        foreign_keys=auto_test_suite_id,
        back_populates='steps',
        lazy='joined',
        innerjoin=True,
    )

    _test_type = db.Column(
        'test_type',
        db.Enum(*_ALL_AUTO_TEST_HANDLERS, name='autoteststeptesttype'),
        nullable=False,
    )

    # TODO: Improve data typing
    _data = db.Column(
        'data',
        t.cast(DbType['psef.helpers.JSONType'], JSON),
        nullable=False,
        default=t.cast('psef.helpers.JSONType', {}),
    )

    __mapper_args__ = {
        'polymorphic_on': _test_type,
        'polymorphic_identity': 'non_existing'
    }

    @property
    def data(self) -> 'psef.helpers.JSONType':
        """Get the data for this step.
        """
        return self._data

    @property
    def weight(self) -> float:
        """Get the weight for this step.
        """
        return self._weight

    @weight.setter
    def weight(self, new_weight: float) -> None:
        self.validate_weight(new_weight)
        self._weight = new_weight

    @staticmethod
    def validate_weight(weight: float) -> None:
        """
        >>> AutoTestStepBase.validate_weight(0) is None
        True
        >>> AutoTestStepBase.validate_weight(-1)
        Traceback (most recent call last):
        ...
        psef.exceptions.APIException
        """
        if weight < 0:
            raise APIException(
                'The weight of a step cannot be negative',
                f'The weight is "{weight}" which is lower than 0',
                APICodes.INVALID_PARAM, 400
            )

    def update_data_from_json(
        self, json: t.Dict[str, 'psef.helpers.JSONType']
    ) -> None:
        """
        >>> t = AutoTestStepBase()
        >>> t.validate_data = lambda _: print('CALLED!')
        >>> d = object()
        >>> t.update_data_from_json(d)
        CALLED!
        >>> t.data is d
        True
        """
        self.validate_data(json)
        self._data = json

    @property
    def command_time_limit(self) -> float:
        """Get the command time limit for this step.
        """
        return (
            self.suite.command_time_limit or
            site_settings.Opt.AUTO_TEST_MAX_TIME_COMMAND.value.total_seconds()
        )

    def get_instructions(self) -> 'auto_test_module.StepInstructions':
        return {
            'id': self.id,
            'weight': self.weight,
            'test_type_name': self._test_type,
            'data': self.data,
            'command_time_limit': self.command_time_limit,
        }

    class AsJSONBase(TypedDict):
        """The base JSON for a step, used for both input and output.
        """
        #: The name of this step.
        name: str
        #: The type of AutoTest step. We constantly add new step types, so
        #: don't try to store this as an enum.
        type: str
        #: The amount of weight this step should have.
        weight: float
        #: Is this step hidden? If ``true`` in most cases students will not be
        #: able to see this step and its details.
        hidden: bool
        #: The data used to run this step. The data shape is dependent on your
        #: permissions and the step type.
        data: t.Any

    class AsJSON(AsJSONBase):
        """The step as JSON.
        """
        #: The id of this step
        id: int

    AsJSON.__cg_extends__ = AsJSONBase  # type: ignore

    class InputAsJSON(AsJSONBase, total=False):
        """The input data needed for a new AutoTest step.
        """
        #: The id of the step. Provide this if you want to edit an existing
        #: step. If not provided a new step will be created.
        id: int

    InputAsJSON.__cg_extends__ = AsJSONBase  # type: ignore

    def __to_json__(self) -> AsJSON:
        try:
            auth.ensure_can_view_autotest_step_details(self)
        except exceptions.PermissionException:
            data = self.remove_data_details()
        else:
            data = self.data

        return {
            'id': self.id,
            'name': self.name,
            'type': self._test_type,
            'weight': self.weight,
            'hidden': self.hidden,
            'data': data,
        }

    @abc.abstractmethod
    def validate_data(self, data: JSONType) -> None:
        """Validate that the given data is valid data for this step.
        """
        raise NotImplementedError

    @classmethod
    def execute_step(
        cls,
        container: 'auto_test_module.StartedContainer',
        opts: 'auto_test_module.ExecuteOptions',
    ) -> float:
        """Execute this step.

        .. danger::

            You should only do this on a test server. This function also checks
            this, but it is important to be sure from the calling code too as
            this function will execute user provided (untrusted) code.

        :param container: The container to execute the code in.
        :param opts: The execute options for executing this step.
        :returns: The amount of points achieved in this step.
        """
        # Make sure we are not on a webserver
        helpers.ensure_on_test_server()

        opts.update_test_result(AutoTestStepResultState.running, {})
        return cls._execute(container, opts)

    @classmethod
    def _execute(
        cls,
        container: 'auto_test_module.StartedContainer',
        opts: 'auto_test_module.ExecuteOptions',
    ) -> float:
        raise NotImplementedError

    def get_amount_achieved_points(  # pylint: disable=no-self-use
        self, result: 'AutoTestStepResult'
    ) -> float:
        """Get the amount of achieved points in this step using the given
        result.
        """
        if result.state == AutoTestStepResultState.passed:
            return result.step.weight
        return 0

    @staticmethod
    def remove_step_details(_: JSONType) -> JSONType:
        """Remove the step details from the result log.

        >>> AutoTestStepBase.remove_step_details(object())
        {}
        >>> AutoTestStepBase.remove_step_details({'secret': 'key'})
        {}
        """
        return t.cast(t.Dict[str, str], {})

    def remove_data_details(self) -> JSONType:  # pylint: disable=no-self-use
        return t.cast(JSONType, {})

    def copy(self: TT) -> TT:
        return self.__class__(
            order=self.order,
            name=self.name,
            _weight=self._weight,
            hidden=self.hidden,
            _data=copy.deepcopy(self.data),
        )


@_register
class _IoTest(AutoTestStepBase):
    __mapper_args__ = {
        'polymorphic_identity': 'io_test',
    }
    data: t.Dict[str, object]

    _ALL_OPTIONS = {
        'case', 'trailing_whitespace', 'substring', 'regex', 'all_whitespace'
    }

    _REQUIRES_MAP = {
        'all_whitespace': 'trailing_whitespace',
        'regex': 'substring',
    }

    _NOT_ALLOWED_MAP = {
        'all_whitespace': 'regex',
    }

    @staticmethod
    def _remove_whitespace(string: str) -> str:
        return "".join(string.split())

    @classmethod
    def _validate_single_input(cls, inp: JSONType) -> t.List[str]:
        errs = []
        with get_from_map_transaction(ensure_json_dict(inp)) as [get, _]:
            name = get('name', str)
            weight: float = get('weight', numbers.Real)  # type: ignore
            get('args', str)
            get('stdin', str)
            get('output', str)
            options = get('options', list)

        if not name:
            errs.append('The name may not be empty')

        if weight < 0:
            errs.append('The weight should not be lower than 0')

        extra_items = set(options) - cls._ALL_OPTIONS
        if extra_items:
            errs.append(f'Unknown items found: "{", ".join(extra_items)}"')
        if len(options) != len(set(options)):
            errs.append('Duplicate options are not allowed')

        for item, required in cls._REQUIRES_MAP.items():
            if item in options and required not in options:
                errs.append(f'The "{item}" option implies "{required}"')

        for item, not_allowed in cls._NOT_ALLOWED_MAP.items():
            if item in options and not_allowed in options:
                errs.append(
                    f'The "{item}" option cannot be combined with the '
                    f'"{not_allowed}" option'
                )

        return errs

    def validate_data(self, data: JSONType) -> None:
        """Validate if the given data is valid for a io test.
        """
        with get_from_map_transaction(
            ensure_json_dict(data), ensure_empty=True
        ) as [get, _]:
            inputs = get('inputs', list)
            program = get('program', str)

        _ensure_program(program)

        if not inputs:
            raise APIException(
                'You have to provide at least one input case',
                'No input cases where provided, however they are required',
                APICodes.INVALID_PARAM, 400
            )

        sum_weight = sum(i['weight'] for i in inputs)
        if sum_weight != self.weight:
            raise APIException(
                (
                    'The sum of the weight of the steps should be equal to the'
                    ' weight'
                ), (
                    f'The sum of the input weights is {sum_weight}, while the '
                    f'step weight is {self.weight}'
                ), APICodes.INVALID_PARAM, 400
            )

        errs: t.List[t.Tuple[int, str]] = []
        for idx, inp in enumerate(inputs):
            errs.extend((idx, err) for err in self._validate_single_input(inp))

        if errs:
            raise APIException(
                'Some input cases were not valid',
                'Some input cases were not valid',
                APICodes.INVALID_PARAM,
                400,
                invalid_cases=errs,
            )

    def get_amount_achieved_points(
        self, result: 'AutoTestStepResult'
    ) -> float:
        passed = AutoTestStepResultState.passed.name
        steps = t.cast(t.List, self.data['inputs'])
        step_results = t.cast(t.Dict[str, t.List], result.log).get('steps', [])
        iterator = zip(steps, step_results)

        return sum(
            s['weight'] if sr['state'] == passed else 0 for s, sr in iterator
        )

    @classmethod
    def match_output(
        cls, stdout: str, expected_output: str, step_options: t.Iterable[str]
    ) -> t.Tuple[bool, t.Optional[int]]:
        """Do the output matching of an IoTest.

        :param stdout: The stdout of the program, so the thing we got.
        :param expected_output: The expected output as provided by the teacher,
            this might be a regex.
        :param step_options: A list of options as given by the students. Valid
            options are 'regex', 'trailing_whitespace', 'case' and 'substring'.
        """
        regex_flags = 0
        to_test = stdout.rstrip('\n')
        step_options = set(step_options)

        if 'all_whitespace' in step_options:
            to_test = cls._remove_whitespace(to_test)
            expected_output = cls._remove_whitespace(expected_output)
        elif 'trailing_whitespace' in step_options:
            to_test = '\n'.join(line.rstrip() for line in to_test.splitlines())
            expected_output = '\n'.join(
                line.rstrip() for line in expected_output.splitlines()
            )

        if 'case' in step_options:
            regex_flags |= re.IGNORECASE
            if 'regex' not in step_options:
                to_test = to_test.lower()
                expected_output = expected_output.lower()

        logger.info(
            'Comparing output and expected output',
            to_test=to_test,
            expected_output=expected_output,
            step_options=step_options,
        )
        if 'regex' in step_options:
            with cg_logger.bound_to_logger(
                output=expected_output,
                to_test=to_test,
                flags=regex_flags,
            ):
                try:
                    match = re.search(
                        expected_output,
                        to_test,
                        flags=regex_flags,
                        timeout=2,
                    )
                except TimeoutError:
                    logger.warning('Regex match timed out', exc_info=True)
                    return False, -2
                logger.info('Done with regex search', match=match)
            return bool(match), None
        elif 'substring' in step_options:
            return expected_output in to_test, None
        else:
            return expected_output == to_test, None

    @classmethod
    def _execute(
        cls,
        container: 'auto_test_module.StartedContainer',
        opts: 'auto_test_module.ExecuteOptions',
    ) -> float:
        def now() -> str:
            return DatetimeWithTimezone.utcnow().isoformat()

        data = opts.test_instructions['data']
        assert isinstance(data, dict)
        inputs = t.cast(t.List[dict], data['inputs'])

        default_result = {
            'state': AutoTestStepResultState.not_started.name,
            'created_at': now(),
        }
        test_result: t.Dict[str, t.Any] = {
            'steps': [copy.deepcopy(default_result) for _ in inputs]
        }
        opts.update_test_result(AutoTestStepResultState.running, test_result)

        prog = t.cast(str, data['program'])
        time_limit = opts.test_instructions['command_time_limit']
        total_state = AutoTestStepResultState.failed
        total_weight = 0

        for idx, step in enumerate(inputs):
            test_result['steps'][idx].update(
                {
                    'state': AutoTestStepResultState.running.name,
                    'started_at': now(),
                }
            )
            opts.update_test_result(
                AutoTestStepResultState.running, test_result
            )

            state: t.Optional[AutoTestStepResultState]
            try:
                res = container.run_student_command(
                    f'{prog} {step["args"]}',
                    time_limit,
                    stdin=step['stdin'].encode('utf-8')
                )
            except psef.auto_test.CommandTimeoutException as e:
                code = e.EXIT_CODE
                stderr = e.stderr
                stdout = e.stdout
                time_spend = e.time_spend
                state = AutoTestStepResultState.timed_out
            else:
                code = res.exit_code
                stdout = res.stdout
                stderr = res.stderr
                time_spend = res.time_spend
                state = None

            if code == 0:
                step_options = t.cast(t.List[str], step['options'])
                expected_output = step['output'].rstrip('\n')

                with cg_logger.bound_to_logger(step=step):
                    success, new_code = cls.match_output(
                        stdout, expected_output, step_options
                    )
                code = code if new_code is None else new_code
            else:
                success = False

            achieved_points = 0
            if success:
                total_state = AutoTestStepResultState.passed
                state = AutoTestStepResultState.passed
                total_weight += step['weight']
                achieved_points = step['weight']
            else:
                state = state or AutoTestStepResultState.failed

            test_result['steps'][idx].update(
                {
                    'stdout': stdout,
                    'stderr': stderr,
                    'state': state.name,
                    'exit_code': code,
                    'time_spend': time_spend,
                    'achieved_points': achieved_points,
                    'started_at': None,
                }
            )
            opts.update_test_result(
                AutoTestStepResultState.running, test_result
            )

            if state == AutoTestStepResultState.timed_out:
                opts.yield_core()

        opts.update_test_result(total_state, test_result)
        return total_weight

    @staticmethod
    def remove_step_details(log: JSONType) -> JSONType:
        """Remove the step details for a IoTest result.

        >>> _IoTest.remove_step_details(None)
        {'steps': []}
        >>> step = {'achieved_points': 5, 'other': 'key'}
        >>> res = _IoTest.remove_step_details({'steps': [step]})
        >>> res
        {'steps': [{'achieved_points': 5}]}
        """
        log_dict = t.cast(t.Dict, log if isinstance(log, dict) else {})
        steps = []
        for step in log_dict.get('steps', []):
            item = {'achieved_points': step.get('achieved_points')}
            state = step.get('state')
            if state is not None:
                item['state'] = state
            steps.append(item)
        return {'steps': steps}

    def remove_data_details(self) -> JSONType:
        return {
            'inputs':
                [
                    self._remove_input_details(inp)
                    for inp in self.data['inputs']  # type: ignore
                ],
        }

    @staticmethod
    def _remove_input_details(inp: JSONType) -> JSONType:
        return {'name': inp['name'], 'weight': inp['weight']}  # type: ignore


@_register
class _RunProgram(AutoTestStepBase):
    __mapper_args__ = {
        'polymorphic_identity': 'run_program',
    }

    def validate_data(self, data: JSONType) -> None:
        with get_from_map_transaction(
            ensure_json_dict(data), ensure_empty=True
        ) as [get, _]:
            program = get('program', str)
        _ensure_program(program)

    @staticmethod
    def _execute(
        container: 'auto_test_module.StartedContainer',
        opts: 'auto_test_module.ExecuteOptions',
    ) -> float:
        data = opts.test_instructions['data']
        assert isinstance(data, dict)

        res = 0.0

        command_res = container.run_student_command(
            t.cast(str, data['program']),
            opts.test_instructions['command_time_limit'],
        )

        if command_res.exit_code == 0:
            state = AutoTestStepResultState.passed
            res = opts.test_instructions['weight']
        else:
            state = AutoTestStepResultState.failed

        opts.update_test_result(
            state, {
                'stdout': command_res.stdout,
                'stderr': command_res.stderr,
                'exit_code': command_res.exit_code,
                'time_spend': command_res.time_spend,
            }
        )

        return res


@_register
class _CustomOutput(AutoTestStepBase):
    __mapper_args__ = {
        'polymorphic_identity': 'custom_output',
    }

    _MATCH_GROUP_NAME = 'amount_of_points'
    _FLOAT_REGEX = r'(?P<{}>-?(?:1\.0*|0\.\d*|\.\d+))'.format(
        _MATCH_GROUP_NAME
    )

    @classmethod
    def _replace_custom_escape_code(cls, regex: str) -> t.Tuple[str, int]:
        r"""
        >>> C = _CustomOutput
        >>> C._FLOAT_REGEX = '<F_REGEX>'
        >>> f = C._replace_custom_escape_code
        >>> f(r'\f')
        ('<F_REGEX>', 1)
        >>> f(r'\\f')
        ('\\\\f', 0)
        >>> f(r'hello: \f')
        ('hello: <F_REGEX>', 1)
        >>> f(r'\f \b \f')
        ('<F_REGEX> \\b <F_REGEX>', 2)
        """
        res = []
        replacements = 0

        prev_back = False
        for char in regex:
            if prev_back and char == 'f':
                res.append(cls._FLOAT_REGEX)
                prev_back = False
                replacements += 1
            elif char == '\\' and prev_back:
                prev_back = False
                res.append('\\\\')
            elif char == '\\':
                assert not prev_back
                prev_back = True
            else:
                if prev_back:
                    res.append('\\')
                    prev_back = False
                res.append(char)

        return ''.join(res), replacements

    def validate_data(self, data: JSONType) -> None:
        """Validate if the given data is valid for a custom output test.
        """
        with get_from_map_transaction(
            ensure_json_dict(data, log_object=False), ensure_empty=True
        ) as [get, _]:
            program = get('program', str)
            regex = get('regex', str)

        _ensure_program(program)

        regex, groups = self._replace_custom_escape_code(regex)

        if groups < 1:
            raise APIException(
                'You have to have at least one \\f special sequence',
                f'The given regex "{regex}" did not contain \\f',
                APICodes.INVALID_PARAM, 400
            )
        elif groups > 1:
            helpers.add_warning(
                (
                    f'You added {groups} \\f in your regex, the behavior in'
                    ' the case that both \\f match is undefined.'
                ), APIWarnings.AMBIGUOUS_COMBINATION
            )

        try:
            re.compile(regex)
        except re.error as e:
            raise APIException(
                f'Compiling the regex failed: {e.msg}',
                'Compiling was not successful', APICodes.INVALID_PARAM, 400
            ) from e

    @classmethod
    def _execute(
        cls,
        container: 'auto_test_module.StartedContainer',
        opts: 'auto_test_module.ExecuteOptions',
    ) -> float:
        points = 0.0

        data = opts.test_instructions['data']
        assert isinstance(data, dict)
        regex, _ = cls._replace_custom_escape_code(t.cast(str, data['regex']))

        res = container.run_student_command(
            t.cast(str, data['program']),
            opts.test_instructions['command_time_limit'],
            keep_stdout_tail=True,
        )
        stderr = res.stderr
        code = res.exit_code
        stdout = res.stdout
        haystack = bytes(res.stdout_tail.data
                         ).decode('utf-8', 'backslashreplace')
        state = AutoTestStepResultState.failed

        if code == 0:
            try:
                match = re.search(regex, haystack, flags=re.REVERSE, timeout=2)
                if match:
                    points = between(
                        0.0, float(match.group(cls._MATCH_GROUP_NAME)), 1.0
                    )
                    state = AutoTestStepResultState.passed
                else:
                    code = -1
            except (ValueError, IndexError, TypeError):
                code = -2
            except TimeoutError:
                code = -3
                stderr += '\nSearching with the regex took too long'

        opts.update_test_result(
            state, {
                'stdout': stdout,
                'stderr': stderr,
                'points': points,
                'exit_code': code,
                'haystack': haystack,
                'time_spend': res.time_spend,
            }
        )

        return points * opts.test_instructions['weight']

    @staticmethod
    def get_amount_achieved_points(result: 'AutoTestStepResult') -> float:
        log: t.Dict = result.log if isinstance(result.log, dict) else {}
        return t.cast(float, log.get('points', 0)) * result.step.weight


@_register
class _CheckPoints(AutoTestStepBase):
    __mapper_args__ = {
        'polymorphic_identity': 'check_points',
    }

    @staticmethod
    def validate_weight(weight: float) -> None:
        """
        >>> c = _CheckPoints()
        >>> c.weight = 0
        >>> c.weight == 0
        True
        >>> c.weight = 1
        Traceback (most recent call last):
        ...
        psef.exceptions.APIException
        """
        if weight != 0:
            raise APIException(
                'The weight of a "check_points" step can only be 0',
                f'The given weight of "{weight}" is invalid',
                APICodes.INVALID_PARAM, 400
            )

    def validate_data(self, data: JSONType) -> None:
        """Validate if the given data is valid for a check_points test.
        """
        with get_from_map_transaction(
            ensure_json_dict(data, log_object=False), ensure_empty=True
        ) as [get, _]:
            min_points = t.cast(
                float,
                get('min_points', numbers.Real)  # type: ignore
            )

        _ensure_between('min_points', min_points, 0, 1)

    @staticmethod
    def _execute(
        _: 'auto_test_module.StartedContainer',
        opts: 'auto_test_module.ExecuteOptions',
    ) -> float:
        data = opts.test_instructions['data']
        assert isinstance(data, dict)
        min_points = t.cast(float, data['min_points'])

        if helpers.FloatHelpers.geq(opts.achieved_percentage, min_points):
            opts.update_test_result(AutoTestStepResultState.passed, {})
            return 0
        else:
            logger.warning(
                "Didn't score enough points",
                achieved_percentage=opts.achieved_percentage
            )
            opts.update_test_result(AutoTestStepResultState.failed, {})
            raise StopRunningStepsException('Not enough points')

    @staticmethod
    def get_amount_achieved_points(_: 'AutoTestStepResult') -> float:
        return 0


@_register
class _JunitTest(AutoTestStepBase):
    SUPPORTS_ATTACHMENT = True

    __mapper_args__ = {
        'polymorphic_identity': 'junit_test',
    }

    def validate_data(self, data: JSONType) -> None:
        with get_from_map_transaction(
            ensure_json_dict(data), ensure_empty=True
        ) as [get, _]:
            program = get('program', str)
        _ensure_program(program)

    @staticmethod
    def _get_points_from_junit(attachment: t.IO[bytes]) -> float:
        junit = cg_junit.CGJunit.parse_file(attachment)
        return safe_div(junit.total_success, junit.total_tests, default=0)

    @classmethod
    def _execute(
        cls,
        container: 'auto_test_module.StartedContainer',
        opts: 'auto_test_module.ExecuteOptions',
    ) -> float:
        data = opts.test_instructions['data']
        assert isinstance(data, dict)

        xml_dir = f'/tmp/.{uuid.uuid4()}'
        xml_location = f'{xml_dir}/{uuid.uuid4()}'

        at_user = psef.auto_test.CODEGRADE_USER
        container.run_command(
            [
                '/bin/bash',
                '-c',
                (
                    f'mkdir "{xml_dir}" && '
                    f'chown -R {at_user}:"$(id -gn {at_user})" "{xml_dir}" && '
                    f'chmod 310 "{xml_dir}"'
                ),
            ]
        )

        with container.extra_env({'CG_JUNIT_XML_LOCATION': xml_location}):
            command_res = container.run_student_command(
                t.cast(str, data['program']),
                opts.test_instructions['command_time_limit'],
            )

        data = {
            'stdout': command_res.stdout,
            'stderr': command_res.stderr,
            'exit_code': command_res.exit_code,
            'time_spend': command_res.time_spend,
            'points': 0.0,
        }

        with tempfile.NamedTemporaryFile() as tfile:
            os.chmod(tfile.name, 0o622)
            copy_cmd = container.run_command(
                ['cat', xml_location], stdout=tfile.name, check=False
            )

            if copy_cmd != 0:
                data['exit_code'] = -1
                opts.update_test_result(AutoTestStepResultState.failed, data)
                return 0.0

            tfile.seek(0, 0)
            try:
                points = cls._get_points_from_junit(tfile)
            except cg_junit.ParseError:
                points = 0.0
                result_state = AutoTestStepResultState.failed
            else:
                result_state = AutoTestStepResultState.passed

            data['points'] = points

            tfile.seek(0, 0)
            opts.update_test_result(result_state, data, attachment=tfile)

        return points

    @staticmethod
    def get_amount_achieved_points(result: 'AutoTestStepResult') -> float:
        log: t.Dict = result.log if isinstance(result.log, dict) else {}
        return t.cast(float, log.get('points', 0)) * result.step.weight


@_register
class _QualityTest(AutoTestStepBase):
    __mapper_args__ = {
        'polymorphic_identity': 'code_quality',
    }

    def validate_data(self, data: JSONType) -> None:
        with get_from_map_transaction(
            ensure_json_dict(data), ensure_empty=True
        ) as [get, _]:
            wrapper = get('wrapper', CodeQualityWrapper)
            program = get('program', str)
            args = get('args', str)
            penalties = get('penalties', dict)

        if wrapper == CodeQualityWrapper.custom:
            _ensure_program(program)

        def ensure_penalty(key: str) -> None:
            if key not in penalties:
                raise APIException(
                    f'Penalty for "{key}" comments not present',
                    f'The penalty for "{key}" comments was not included',
                    APICodes.INVALID_PARAM, 400
                )

            value = penalties[key]
            if not isinstance(value, numbers.Real):
                print(value, type(value))
                raise APIException(
                    f'Penalty for "{key}" comments must be a number',
                    f'The penalty for "{key}" must be a float but it was'
                    f'"{value}"',
                    APICodes.INVALID_PARAM, 400
                )

            _ensure_between(key, t.cast(float, value), 0, 100)

        ensure_penalty('fatal')
        ensure_penalty('error')
        ensure_penalty('warning')
        ensure_penalty('info')

    @classmethod
    def _execute(
        cls,
        container: 'auto_test_module.StartedContainer',
        opts: 'auto_test_module.ExecuteOptions',
    ) -> float:
        data = opts.test_instructions['data']
        assert isinstance(data, dict)

        wrapper = CodeQualityWrapper.__members__[t.cast(str, data['wrapper'])]
        if wrapper == CodeQualityWrapper.custom:
            program = t.cast(str, data['program'])
        else:
            program = f'{wrapper.value} {data["args"]}'

        command_res = container.run_student_command(
            program,
            opts.test_instructions['command_time_limit'],
        )

        points = 1.0
        state = AutoTestStepResultState.passed

        if command_res.exit_code != 0:
            points = 0
            state = AutoTestStepResultState.failed

        # TODO: we do not have access to the quality comments here, so we
        # currently cannot calculate the correct score here.
        data = {
            'stdout': command_res.stdout,
            'stderr': command_res.stderr,
            'exit_code': command_res.exit_code,
            'time_spend': command_res.time_spend,
            'points': points,
        }
        opts.update_test_result(state, data)

        return points

    @classmethod
    def get_amount_achieved_points(cls, result: 'AutoTestStepResult') -> float:
        # TODO: we do not have access to the quality comments in the _execute
        # method, so we currently have to recalculate the score by hand.
        comments = AutoTestQualityComment.query.filter(
            AutoTestQualityComment.auto_test_step_id == result.auto_test_step_id,
            AutoTestQualityComment.auto_test_result_id == result.id,
        ).all()
        penalties = cls._get_penalties(result.step.data)

        score = 100.0

        for comment in comments:
            penalty = penalties[comment.severity]
            score -= penalty

        return result.step.weight * score / 100

    @staticmethod
    def _get_penalties(step_data: JSONType) -> t.Mapping['QualityCommentSeverity', float]:
        assert isinstance(step_data, dict)
        penalties = t.cast(t.Mapping[str, float], step_data['penalties'])
        return {
            QualityCommentSeverity(severity): penalty
            for severity, penalty in penalties.items()
        }


class AutoTestStepResult(Base, TimestampMixin, IdMixin):
    """This class represents the result of a single AutoTest step.
    """
    auto_test_step_id = db.Column(
        'auto_test_step_id',
        db.Integer,
        db.ForeignKey('AutoTestStep.id', ondelete='CASCADE'),
        nullable=False
    )

    step = db.relationship(
        lambda: AutoTestStepBase,
        foreign_keys=auto_test_step_id,
        lazy='joined',
        innerjoin=True,
    )

    auto_test_result_id = db.Column(
        'auto_test_result_id',
        db.Integer,
        db.ForeignKey('AutoTestResult.id', ondelete='CASCADE'),
    )

    result = db.relationship(
        lambda: psef.models.AutoTestResult,
        foreign_keys=auto_test_result_id,
        innerjoin=True,
        back_populates='step_results',
    )

    _state = db.Column(
        'state',
        db.Enum(AutoTestStepResultState),
        default=AutoTestStepResultState.not_started,
        nullable=False,
    )

    started_at = db.Column(
        'started_at', db.TIMESTAMP(timezone=True), default=None, nullable=True
    )

    log: ColumnProxy[JSONType] = db.Column(
        'log', JSON, nullable=True, default=None
    )

    _attachment_filename = db.Column(
        'attachment_filename', db.Unicode, nullable=True, default=None
    )

    def _get_has_attachment(self) -> bool:
        return self.attachment.is_just

    @hybrid_expression
    def _get_has_attachment_expr(cls: t.Type['AutoTestStepResult']
                                 ) -> DbColumn[bool]:
        # pylint: disable=no-self-argument
        return cls._attachment_filename.isnot(None)

    #: Check if this step has an attachment
    has_attachment = hybrid_property(
        _get_has_attachment, expr=_get_has_attachment_expr
    )

    @property
    def state(self) -> AutoTestStepResultState:
        """The state of this result. Setting this might also change the
        ``started_at`` property.
        """
        return self._state

    @state.setter
    def state(self, new_state: AutoTestStepResultState) -> None:
        if self._state == new_state:
            return

        self._state = new_state
        if new_state == AutoTestStepResultState.running:
            self.started_at = DatetimeWithTimezone.utcnow()
        else:
            self.started_at = None

    @property
    def achieved_points(self) -> float:
        """Get the amount of achieved points by this step result.
        """
        return self.step.get_amount_achieved_points(self)

    @property
    def attachment(self) -> Maybe[cg_object_storage.File]:
        """Maybe the attachment of this step.

        The step might not have an attachment in which case ``Nothing`` is
        returned.
        """
        if self._attachment_filename is None:
            return Nothing
        return current_app.file_storage.get(self._attachment_filename)

    def schedule_attachment_deletion(self) -> None:
        """Delete the attachment of this result after the current request.

        The attachment, if present, will be deleted, if not attachment is
        present this function does nothing.

        :returns: Nothing.
        """
        old_attachment = self.attachment
        if old_attachment.is_just:
            deleter = old_attachment.value.delete
            callback_after_this_request(deleter)

    def update_attachment(self, stream: FileStorage) -> None:
        """Update the attachment of this step.

        :param stream: Attachment data.
        """
        if not self.step.SUPPORTS_ATTACHMENT:
            raise APIException(
                'This step type does not support attachment', (
                    f'The step {self.step.id} does not support'
                    ' attachments but step result {self.id}'
                    ' generated one anyway'
                ), APICodes.INVALID_STATE, 400
            )

        self.schedule_attachment_deletion()
        max_size = current_app.max_single_file_size
        with current_app.file_storage.putter() as putter:
            new_file = putter.from_stream(stream.stream, max_size=max_size)
        if new_file.is_nothing:  # pragma: no cover
            raise helpers.make_file_too_big_exception(max_size, True)

        self._attachment_filename = new_file.value.name

    class AsJSON(TypedDict):
        """The step result as JSON.
        """
        #: The id of the result of a step
        id: int
        #: The step this is the result of.
        auto_test_step: AutoTestStepBase
        #: The state this result is in.
        state: AutoTestStepResultState
        #: The amount of points achieved by the student in this step.
        achieved_points: float
        #: The log produced by this result. The format of this log depends on
        #: the step result.
        log: t.Optional[t.Any]
        #: The time this result was started, if ``null`` the result hasn't
        #: started yet.
        started_at: t.Optional[DatetimeWithTimezone]
        #: The id of the attachment produced by this result. If ``null`` no
        #: attachment was produced.
        attachment_id: t.Optional[str]

    def __to_json__(self) -> AsJSON:
        try:
            auth.ensure_can_view_autotest_step_details(self.step)
        except exceptions.PermissionException:
            log = self.step.remove_step_details(self.log)
        else:
            log = self.log

        return {
            'id': self.id,
            'auto_test_step': self.step,
            'state': self.state,
            'achieved_points': self.achieved_points,
            'log': log,
            'started_at': self.started_at,
            'attachment_id': self._attachment_filename,
        }


@event.listens_for(AutoTestStepResult, 'after_delete')
def _receive_after_delete(
    _: object, __: object, target: AutoTestStepResult
) -> None:
    """Listen for the 'after_delete' event"""
    target.schedule_attachment_deletion()


@cg_enum.named_equally
class QualityCommentSeverity(cg_enum.CGEnum):
    info = 'info'
    warning = 'warning'
    error = 'error'
    fatal = 'fatal'


class LineRangeAsJSON(TypedDict):
    start: int
    end: int

class ColumnRangeAsJSON(TypedDict):
    start: int
    end: t.Optional[int]

class AutoTestQualityComment(Base, TimestampMixin, IdMixin):
    auto_test_step_id = db.Column(
        'auto_test_step_id',
        db.Integer,
        db.ForeignKey('AutoTestStep.id', ondelete='CASCADE'),
        nullable=False
    )

    step = db.relationship(
        lambda: AutoTestStepBase,
        foreign_keys=auto_test_step_id,
        innerjoin=True,
    )

    auto_test_result_id = db.Column(
        'auto_test_result_id',
        db.Integer,
        db.ForeignKey('AutoTestResult.id', ondelete='CASCADE'),
        nullable=False,
    )

    result = db.relationship(
        lambda: psef.models.AutoTestResult,
        foreign_keys=auto_test_result_id,
        back_populates='quality_comments',
        innerjoin=True,
    )

    #: The file on which the comment was placed
    file_id = db.Column(
        'File_id',
        db.Integer,
        db.ForeignKey('File.id', ondelete='CASCADE'),
        nullable=False,
    )

    file = db.relationship(lambda: file_models.File, foreign_keys=file_id)

    #: The line (1 indexed) the error begins on, inclusive.
    line_start = db.Column('line_start', db.Integer, nullable=False)

    #: The line (1 indexed) the error ends, inclusive.
    line_end = db.Column('line_end', db.Integer, nullable=False)

    #: The column the error starts on, inclusive, 0 indexed.
    column_start = db.Column('column_start', db.Integer, nullable=False)

    #: The column the error ends on, inclusive, 0 indexed. If ``null`` the
    #: error spans the entire last line.
    column_end = db.Column('column_end', db.Integer, nullable=True)

    #: Which program/linter created this comment?
    origin = db.Column('origin', db.Unicode, nullable=False)

    #: If the linter outputs a error code (e.g. for pylint something like
    #: W1636) it will be stored in this column.
    quality_code = db.Column('quality_code', db.Unicode, nullable=True)

    #: The severity of the comment. This might be used to calculate the score.
    severity = db.Column(
        'severity', db.Enum(QualityCommentSeverity), nullable=False
    )

    #: The comment that was generated by the linter.
    comment = db.Column('comment', db.Unicode, nullable=False)

    class BaseAsJSON(TypedDict):
        severity: QualityCommentSeverity
        code: t.Optional[str]
        origin: str
        msg: str
        line: LineRangeAsJSON
        column: ColumnRangeAsJSON

    class AsJSON(BaseAsJSON):
        step_id: int
        result_id: int
        file_id: str

    class InputAsJSON(BaseAsJSON):
        path: t.List[str]

    def __to_json__(self) -> AsJSON:
        return {
            'step_id': self.auto_test_step_id,
            'result_id': self.auto_test_result_id,
            'file_id': str(self.file_id),
            'origin': self.origin,
            'severity': self.severity,
            'code': self.quality_code,
            'msg': self.comment,
            'line': {
                'start': self.line_start,
                'end': self.line_end,
            },
            'column': {
                'start': self.column_start,
                'end': self.column_end,
            },
        }

    def __init__(
        self, result_id: int, step_id: int, file_id: int, data: BaseAsJSON
    ) -> None:
        super().__init__(
            auto_test_result_id=result_id,
            auto_test_step_id=step_id,
            file_id=file_id,
            origin=data['origin'],
            severity=data['severity'],
            quality_code=data['code'],
            comment=data['msg'],
            line_start=data['line']['start'],
            line_end=data['line']['end'],
            column_start=data['column']['start'],
            column_end=data['column']['end'],
        )
