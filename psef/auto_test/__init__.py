"""This module contains all functionality needed to do an actual AutoTest run.

SPDX-License-Identifier: AGPL-3.0-only
"""
import io
import os  # typing: ignore
import abc
import grp
import pwd
import sys
import copy
import json
import time
import uuid
import errno
import queue
import random
import select
import signal
import typing as t
import datetime
import tempfile
import threading
import contextlib
import subprocess
import collections
import dataclasses
import multiprocessing
from pathlib import Path
from multiprocessing import Event, Queue, context, managers

import lxc  # typing: ignore
import furl
import urllib3
import requests
import structlog
from mypy_extensions import TypedDict
from requests.adapters import HTTPAdapter
from typing_extensions import Protocol
from urllib3.util.retry import Retry

import psef
import cg_logger
import cg_worker_pool
import cg_threading_utils
from cg_timers import timed_code, timed_function

from .. import models, helpers
from ..helpers import JSONType, RepeatedTimer, defer
from ..registry import auto_test_handlers
from ..exceptions import APICodes, StopRunningStepsException

logger = structlog.get_logger()

OutputCallback = t.Callable[[bytes], None]
URL = t.NewType('URL', str)

_LXC_START_STOP_LOCK = multiprocessing.Lock()

T = t.TypeVar('T')
Y = t.TypeVar('Y')

Network = t.NewType('Network', t.Tuple[str, t.List[t.Tuple[str, str]]])

NETWORK_EXCEPTIONS = (
    requests.RequestException, ConnectionError, urllib3.exceptions.HTTPError
)
FIXTURES_ROOT = f'/.{uuid.uuid4().hex}'
PRE_STUDENT_FIXTURES_DIR = f'{uuid.uuid4().hex}/'

OUTPUT_DIR = f'/.{uuid.uuid4().hex}/{uuid.uuid4().hex}'

# _Absolute_ path to the bash executable.
BASH_PATH = '/bin/bash'


class UpdateResultFunction(Protocol):
    """A protocol for a function that can update the state of a step.
    """

    def __call__(
        self,
        state: 'models.AutoTestStepResultState',
        log: t.Dict[str, object],
        *,
        attachment: t.Optional[t.IO[bytes]] = None
    ) -> None:
        ...


class YieldCoreCallback(Protocol):
    """A protocol for a function that yields the current core.
    """

    def __call__(self) -> None:
        ...


CODEGRADE_USER = 'codegrade'
_SYSTEMD_WAIT_CMD = [
    'systemd-run',
    '--property=After=basic.target',
    '--wait',
    '/bin/true',
]
_REQUEST_TIMEOUT = 10
_REQUEST_RETRIES = 5
_REQUEST_BACKOFF_FACTOR = 1.2

MaybeQuitRunning = t.Callable[[], None]


class LXCProcessError(Exception):
    pass


class StopRunningStudentException(Exception):
    pass


class StopRunningTestsException(Exception):
    pass


class AttachTimeoutError(StopRunningTestsException):
    pass


class FailedToStartError(StopRunningTestsException):
    pass


class FailedToShutdownError(cg_worker_pool.KillWorkerException):
    pass


@dataclasses.dataclass(frozen=True)
class OutputTail:
    """This class represents the tail of an output stream.

    If ``overflowed`` is ``True`` there was even more data captured, but this
    was thrown away.
    """
    data: t.Sequence[int]
    overflowed: bool


@dataclasses.dataclass(frozen=True)
class StudentCommandResult:
    """The result of a student command.
    """
    exit_code: int
    stdout: str
    stderr: str
    time_spend: float
    stdout_tail: OutputTail


def _get_home_dir(name: str) -> str:
    """Get the home dir of the given user

    >>> _get_home_dir('height')
    '/home/height'
    >>> _get_home_dir(CODEGRADE_USER)
    '/home/codegrade'
    """
    return f'/home/{name}'


def _waitpid_noblock(pid: int) -> t.Optional[int]:
    """Wait for the given pid without blocking.

    :returns: ``None`` if the process has not exited, -1 if the process
        signaled and the exit code (which is > 0) if the process exited
        normally.
    """
    new_pid, status = os.waitpid(pid, os.WNOHANG)

    if new_pid == status == 0:
        return None
    elif os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    elif os.WIFSIGNALED(status):
        logger.warning(
            'Process signaled',
            pid=pid,
            new_pid=new_pid,
            status=status,
            signal=os.WTERMSIG(status),
        )
        return -1
    # This should not be possible, as either the process should either
    # not be exited (new_pid == status == 0), or should exit normally
    # (os.WIFEXITED), or it exited through a signal (os.WIFSIGNALED).
    assert False


def _wait_for_attach(
    pid: int,
    command_started: threading.Event,
    timeout_time: int = 10,
    max_amount_timeouts: int = 3,
) -> t.Optional[int]:
    """Wait on the given pid until it signaled a start.

    This is done by waiting on the given :class:`.threading.Event` and every
    ``timeout_time`` seconds checking if the process has not already stopped.

    :param pid: The pid of the attached container.
    :param command_started: An event to check for if the attach finished.
    :param timeout_time: The amount of time that should be between checks if
        the command exited.
    :param max_amount_timeouts: The maximal amount of times to check if the
        command exited. If exceeded an :py:class:`.AttachTimeoutError` is
        raised.
    :returns: The exit code if the program exited before the attach finished.

    >>> import doctest
    >>> doctest.ELLIPSIS_MARKER = '-etc-'
    >>> from subprocess import Popen
    >>> event = threading.Event()
    >>> p = Popen('exit 1', shell=True)
    >>> assert _wait_for_attach(p.pid, event, 1) == 1
    -etc-
    >>> event.set()
    >>> p = Popen('exit 2', shell=True)
    >>> assert _wait_for_attach(p.pid, event, 1) is None
    -etc-
    >>> p = Popen('sleep 120', shell=True)
    >>> event.clear()
    >>> assert _wait_for_attach(p.pid, event, 1, 1) is None
    Traceback (most recent call last):
    -etc-
    AttachTimeoutError
    """
    with timed_code('waiting_for_attach'):
        for _ in helpers.retry_loop(
            max_amount_timeouts,
            sleep_time=0,
            make_exception=AttachTimeoutError,
        ):
            if command_started.wait(timeout_time):  # pragma: no cover
                return None
            logger.info('Still not attached', pid=pid)

            code = _waitpid_noblock(pid)
            if code is not None:
                code = code if code > -1 else 258
                logger.info('Program exited before attach', code=code)
                return code

    raise RuntimeError  # pragma: no cover


def _wait_for_pid(
    pid: int, timeout: float, maybe_quit_running: MaybeQuitRunning
) -> t.Tuple[int, float]:
    """Wait for ``pid`` at most ``timeout`` amount of seconds.

    >>> from subprocess import Popen
    >>> p = Popen('sleep 5', shell=True)
    >>> _wait_for_pid(p.pid, 0.25, lambda: None)
    Traceback (most recent call last):
    ...
    CommandTimeoutException
    >>> p.poll() is not None
    True

    It also works when SIGTERM is ignored.
    >>> p = Popen("trap 'echo SIGTERM!' 15 ; sleep 5", shell=True)
    >>> _wait_for_pid(p.pid, 0.25, lambda: None)
    Traceback (most recent call last):
    ...
    CommandTimeoutException

    >>> pid = Popen('sleep 0.5 && exit 32', shell=True).pid
    >>> _wait_for_pid(pid, 4, lambda: None)[0]
    32

    >>> _wait_for_pid(Popen('sleep 0.5 && exit 20', shell=True).pid, 4, lambda: None)[0]
    20

    >>> exit, left = _wait_for_pid(Popen(['sleep', '0.25']).pid, 1, lambda: None)
    >>> exit
    0
    >>> abs((1 - left) - 0.25) <= 0.05  # Waiting should be fairly accurate
    True

    >>> import doctest
    >>> doctest.ELLIPSIS_MARKER = '-etc-'
    >>> p = Popen('kill -11 $$', shell=True)  # This segfaults
    >>> _wait_for_pid(p.pid, 1, lambda: None)[0] == -1
    -etc-Process signaled-etc-
    True
    """
    start_time = time.time()

    def get_time_left() -> float:
        time_spend = time.time() - start_time
        return timeout - time_spend

    def timed_out() -> bool:
        return get_time_left() < 0

    # This timeout delay code is very similar to that of the timeout
    # implementation of `subprocess`. It could probably be improved, but I'm
    # pretty happy with it for now.
    delay = 0.0005

    while not timed_out():
        exit_code = _waitpid_noblock(pid)

        if exit_code is None:
            delay = max(min(delay * 2, get_time_left(), 0.05), 0)
            time.sleep(delay)
        else:
            maybe_quit_running()
            return exit_code, get_time_left()

    logger.warning('Process took too long, killing', pid=pid)
    os.kill(pid, signal.SIGTERM)
    for _ in range(10):
        if _waitpid_noblock(pid) is None:
            time.sleep(0.1)
        else:
            break
    else:
        logger.warning(
            'Process did not listen to SIGTERM, killing the hard way', pid=pid
        )
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)

    maybe_quit_running()
    end_time = time.time()
    logger.warning('Killing done', pid=pid)
    raise CommandTimeoutException(end_time - start_time)


class LockableValue(t.Generic[T]):
    """This class essentially contains a lock and a value.

    It forces you to acquire the lock before you can get or set the value.
    """

    class _InnerValue(t.Generic[Y]):
        def __init__(self, value: Y) -> None:
            self.value = value

    def __init__(self, initial_value: T) -> None:
        self.__lock = threading.Lock()
        self.__inner_value: 'LockableValue._InnerValue[T]'
        self.__value = initial_value

    def get(self) -> T:
        """Get the internal value.
        """
        with self.__lock:
            return self.__value

    def set(self, value: T) -> None:
        """Set the internal value.
        """
        with self.__lock:
            self.__value = value

    def __enter__(self) -> 'LockableValue._InnerValue[T]':
        self.__lock.acquire()
        self.__inner_value = LockableValue._InnerValue(self.__value)
        return self.__inner_value

    def __exit__(
        self, exc_type: object, exc_value: object, traceback: object
    ) -> None:
        self.__value = self.__inner_value.value
        del self.__inner_value
        self.__lock.release()


class _Manager(managers.SyncManager):
    pass


_Manager.register('FairLock', cg_threading_utils.FairLock)


class CpuCores:
    """This class contains a reservation system for cpu cores.

    With this class you can make sure only one of the containers is using
    specific core at any specific moment. This also works across multiple
    processes.
    """

    class Core:
        """A class representing the currently reserved core.

        .. note::

            This class is mutable, so :meth:`~Core.get_core_number` might
            change.
        """

        def __init__(self, core_number: int, cores: 'CpuCores') -> None:
            self._core_number = core_number
            self._cores = cores

        def get_core_number(self) -> int:
            """Get the number of the core that is reserved.
            """
            return self._core_number

        def yield_core(self) -> bool:
            """Yield the current core.

            .. warning::

                The core that is reserved might be changed after this call. So
                make sure that you actually lock the container to this core
                after the call.
            """
            new_number = self._cores.yield_core(self._core_number)
            old_number = self._core_number
            self._core_number = new_number
            return new_number != old_number

    def __init__(
        self,
        manager: _Manager,
        number_of_cores: t.Optional[int] = None,
    ) -> None:
        self._number_of_cores = number_of_cores or _get_amount_cpus()
        self._available_cores: 'Queue[int]' = manager.Queue(  # type: ignore
            self._number_of_cores
        )
        self._lock: cg_threading_utils.FairLock = manager.FairLock(  # type: ignore
        )
        for core in range(self._number_of_cores):
            self._available_cores.put(core)

    def yield_core(self, core_number: int) -> int:
        """Yield the given core.

        :returns: The number of the newly reserved core.
        """
        self._available_cores.put(core_number)
        return self._get_core()

    def _get_core(self) -> int:
        self._lock.acquire()
        try:
            return self._available_cores.get()
        finally:
            self._lock.release()

    @contextlib.contextmanager
    def reserved_core(self) -> t.Generator['CpuCores.Core', None, None]:
        """Reserve a core for the duration of the ``with`` block.
        """
        core = self.Core(self._get_core(), self)
        logger.info('Got core number', core=core)

        try:
            yield core
        finally:
            self._available_cores.put(core.get_core_number())


class StopContainerException(Exception):
    """This exception should be raised by each container when they should stop
    running.
    """


class CommandTimeoutException(Exception):
    """This exception is raised when a command takes too much time.
    """
    EXIT_CODE = -2

    def __init__(
        self,
        time_spend: float,
        cmd: str = '',
        stdout: str = '',
        stderr: str = '',
    ) -> None:
        super().__init__()

        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.time_spend = time_spend


def _get_new_container_name() -> str:
    """Get a new unique container name

    >>> a = _get_new_container_name()
    >>> b = _get_new_container_name()
    >>> type(a)
    <class 'str'>
    >>> a != b
    True
    """
    return str(uuid.uuid1())


def _get_amount_cpus() -> int:
    """Get the amount of cpus on this system or 1 if we cannot detect it.

    This will always be higher than 0.

    >>> _get_amount_cpus() > 0
    True
    """
    return os.cpu_count() or 1


def _get_base_container(config: 'psef.FlaskConfig') -> 'AutoTestContainer':
    helpers.ensure_on_test_server()
    template_name = config['AUTO_TEST_TEMPLATE_CONTAINER']
    if template_name is None:
        logger.info('No base template set, creating new container')
        res = AutoTestContainer(
            _get_new_container_name(), config, maybe_quit_running=lambda: None
        )
        res.create()
    else:  # pragma: no cover
        res = AutoTestContainer(
            template_name, config, maybe_quit_running=lambda: None
        ).clone()
    return res


def _stop_container(cont: lxc.Container) -> None:
    if cont.running:
        with timed_code('stop_container'):
            for _ in helpers.retry_loop(
                amount=4, sleep_time=1, make_exception=FailedToShutdownError
            ):
                with _LXC_START_STOP_LOCK:
                    if cont.shutdown(10):
                        break
                logger.warning(
                    'Failed to shutdown container', last_error=cont.last_error
                )
            assert cont.wait('STOPPED', 3)


def _start_container(
    cont: lxc.Container,
    *,
    check_network: bool = True,
    always: bool = False,
    maybe_quit_running: MaybeQuitRunning
) -> None:
    if not always:
        maybe_quit_running()

    if cont.running:
        return

    with timed_code('start_container'):
        with _LXC_START_STOP_LOCK:
            if not cont.start():
                logger.error(
                    'Container failed to start', last_error=cont.last_error
                )
                raise FailedToStartError
        if not cont.wait('RUNNING', 3):  # pragma: no cover
            raise FailedToStartError

        def callback(domain_or_systemd: t.Optional[str]) -> int:
            if domain_or_systemd is None:
                for _ in range(10):
                    try:
                        res = subprocess.run(_SYSTEMD_WAIT_CMD, timeout=1)  # pylint: disable=subprocess-run-check
                    except subprocess.TimeoutExpired:  # pragma: no cover
                        pass
                    else:
                        if res.returncode == 0:
                            break

                    time.sleep(0.25)
                else:  # pragma: no cover
                    os._exit(1)  # pylint: disable=protected-access
                os._exit(0)  # pylint: disable=protected-access
            else:
                os.execvp('ping', ['ping', '-w', '1', '-c', '1', domain])
            assert False

        with timed_code('wait_for_system_start'):
            out_code = cont.attach_wait(callback, None)
            logger.info('Started system', systemd_wait_exit_code=out_code)

        if check_network:
            with timed_code('wait_for_network'):

                for _ in helpers.retry_loop(
                    60,
                    sleep_time=0.5,
                    make_exception=StopRunningStudentException
                ):
                    if not always:
                        maybe_quit_running()

                    if not cont.get_ips():
                        continue

                    for domain in ['codegra.de', 'docs.codegra.de']:
                        if cont.attach_wait(callback, domain) == 0:
                            return


class StepInstructions(TypedDict, total=True):
    """Instructions on how to run a single AutoTest step.

    :ivar ~.StepInstructions.id: The id of the step.
    :ivar weight: The amount of points you can achieve with this step.
    :ivar test_type_name: The type of step this is.
    :ivar data: The data of this step, this contains stuff like which command
        to run and what output to expect.
    :ivar command_time_limit: What is the maximum amount of time a command may
        run in this step.
    """
    id: int
    weight: float
    test_type_name: str
    data: 'psef.helpers.JSONType'
    command_time_limit: float


class SuiteInstructions(TypedDict, total=True):
    """Instructions on how to run a single AutoTest suite.

    :ivar ~.StepInstructions.id: The id of the suite.
    :ivar steps: The steps of this suite.
    :ivar network_disabled: Should this suite be run with networking disabled.
    :ivar submission_info: Should submission information be included in the
        environment.
    """
    id: int
    steps: t.List[StepInstructions]
    network_disabled: bool
    submission_info: bool


class SetInstructions(TypedDict, total=True):
    """Instructions for a single AutoTest set.

    :ivar ~.SetInstructions.id: The id of this set.
    :ivar suites: The suites of this set.
    :ivar stop_points: The minimum amount of points that we should have to be
        able to continue running sets.
    """
    id: int
    suites: t.List[SuiteInstructions]
    stop_points: float


class AssignmentInformation(TypedDict, total=True):
    """Information about the assignment that this AutoTest belongs to.
    """
    #: The deadline of the assignment.
    deadline: t.Optional[str]


class StudentInformation(TypedDict, total=True):
    """Information about the submission that the AutoTest runs on.
    """
    #: The id of the :class:`AutoTestResult` corresponding to this work.
    result_id: int
    #: The id of the :class:`User` who submitted the work.
    student_id: int
    #: The datetime when the work was submitted.
    created_at: str


class RunnerInstructions(TypedDict, total=True):
    """Instructions for a complete auto test run.

    :ivar runner_id: The id of this runner.
    :ivar run_id: The id of this auto test run.
    :ivar auto_test_id: The id of this AutoTest configuration.
    :ivar result_ids: The ids of the results this runner should produce. These
        can be seen as submissions. (Deprecated, use ``student_infos`` instead)
    :ivar student_ids: The ids of the user corresponding to the result with id
        at the same index in the ``result_ids`` list. (Deprecated, use
        ``student_infos`` instead)
    :ivar assignment_info: Assignment information made available to AutoTest
        steps.
    :ivar student_infos: List of information associated to each result.
    :ivar sets: The sets that this AutoTest configuration contain.
    :ivar setup_script: The setup script that should be run for each student.
    :ivar run_setup_script: The setup script that should be run once.
    :ivar heartbeat_interval: The interval in seconds to send heartbeats in.
    :ivar fixtures: A list of tuples where the first item is the name of the
        fixture and the second item is its id.
    """
    runner_id: str
    run_id: int
    auto_test_id: int
    result_ids: t.List[int]
    student_ids: t.List[int]
    student_infos: t.Optional[t.List[StudentInformation]]
    assignment_info: t.Optional[AssignmentInformation]
    sets: t.List[SetInstructions]
    fixtures: t.List[t.Tuple[str, int]]
    setup_script: str
    heartbeat_interval: int
    run_setup_script: str
    poll_after_done: bool


@dataclasses.dataclass(frozen=True)
class ExecuteOptions:
    """Options passed to the steps when executing them.

    :ivar update_test_result: A function that can be used to update the step
        result.
    :ivar test_instructions: The instructions for how to execute this step.
    :ivar achieved_percentage: The percentage of points achieved at this point
        for the current suite.
    :ivar ~ExecuteOptions.yield_core: A callback that shuts the container down,
        yields the reserved core and requests a new one, and starts the
        container back up.
    """
    update_test_result: UpdateResultFunction
    test_instructions: StepInstructions
    achieved_percentage: float
    yield_core: YieldCoreCallback


def init_app(_: 'psef.PsefFlask') -> None:
    pass


# This wrapper function is needed for Python multiprocessing
def _run_student(
    cont: 'AutoTestRunner',
    bc_name: str,
    cores: CpuCores,
    opts: cg_worker_pool.CallbackArguments,
) -> None:
    cont.run_student(bc_name, cores, opts)


def _try_to_run_job(
    broker_session: 'helpers.BrokerSession',
    runner_id: str,
    config: 'psef.FlaskConfig',
    cont: 'StartedContainer',
) -> bool:
    def get_url(url: str) -> URL:
        return URL(config['AUTO_TEST_RUNNER_CONTAINER_URL'] or url)

    with broker_session as ses:
        items = []
        try:
            response = ses.get(
                f'/api/v1/runners/{runner_id}/jobs/', timeout=_REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except:  # pylint: disable=bare-except
            # pragma: no cover
            logger.info('Tried to get jobs from broker', exc_info=True)
        else:
            logger.info('Got jobs from broker', response=response)
            items = response.json()

    for item in items:
        url = item['url']
        headers = {
            'CG-Internal-Api-Password':
                config['AUTO_TEST_RUNNER_INSTANCE_PASS'],
        }
        logger.bind(server=url)
        logger.info('Checking next server')

        try:
            response = requests.get(
                f'{url}/api/v-internal/auto_tests/',
                params={
                    'get': 'tests_to_run',
                },
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.error('Failed to get server', exc_info=True)
            continue

        if response.status_code == 200:
            data = response.json()
            logger.info(
                'Got test',
                response=response,
                auto_test_id=data.get('auto_test_id')
            )

            try:
                AutoTestRunner(
                    URL(get_url(url)),
                    data,
                    config['AUTO_TEST_RUNNER_INSTANCE_PASS'],
                    config,
                ).run_test(cont)
            except:  # pylint: disable=bare-except
                logger.error('Error while running tests', exc_info=True)
            return True
        else:
            logger.info('No tests found', response=response)
    return False


def start_polling(config: 'psef.FlaskConfig') -> None:
    """Start polling the configured CodeGrade instances.

    :param config: The config of this AutoTest runner. This also determines
        what servers will be polled.
    :param repeat: Should we repeat the polling after running a single test.
    """
    sleep_time = config['AUTO_TEST_POLL_TIME']
    broker_url = config['AUTO_TEST_BROKER_URL']

    runner_pass_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', '.runner-pass')
    )
    runner_pass = None
    if os.path.isfile(runner_pass_file):
        with open(runner_pass_file, 'r') as f:
            runner_pass = f.read().strip()
    else:
        logger.error(
            'Could not find runner pass file',
            runner_pass_file=runner_pass_file
        )

    def get_broker_session() -> helpers.BrokerSession:
        return helpers.BrokerSession('', '', broker_url, runner_pass)

    with _get_base_container(config).started_container() as cont:
        if config['AUTO_TEST_TEMPLATE_CONTAINER'] is None:
            cont.run_command(['apt', 'update'])
            cont.run_command(
                ['apt', 'install', '-y', 'wget', 'curl', 'unzip'],
                retry_amount=4,
            )

        for _ in helpers.retry_loop(
            sys.maxsize,
            sleep_time=_REQUEST_TIMEOUT,
            make_exception=AssertionError
        ):
            with get_broker_session() as ses:
                try:
                    response = ses.post(
                        '/api/v1/alive/', timeout=_REQUEST_TIMEOUT
                    )
                    response.raise_for_status()
                except:  # pylint: disable=bare-except
                    logger.info('Did request to broker', exc_info=True)
                    continue
                else:
                    runner_id: str = response.json()['id']
                    break

        while True:
            if _try_to_run_job(get_broker_session(), runner_id, config, cont):
                break
            time.sleep(sleep_time)


class StartedContainer:
    """This class represents a started lxc container. It can be used to execute
    commands.
    """
    _NETWORK_LOCK = threading.Lock()
    _SNAPSHOT_LOCK = threading.Lock()

    def __init__(
        self,
        container: lxc.Container,
        name: str,
        config: 'psef.FlaskConfig',
        maybe_quit_running: MaybeQuitRunning,
    ) -> None:
        self._snapshots: t.List[str] = []
        self._dirty = False
        self._container = container
        self._config = config
        self._name = name
        self._network_is_enabled = True
        self._networks: t.List[Network] = []
        self._fixtures_dir: t.Optional[str] = None
        self._extra_env: t.Dict[str, str] = {}
        self._maybe_quit_running = maybe_quit_running

    def set_maybe_quit_running(self, new_val: MaybeQuitRunning) -> None:
        self._maybe_quit_running = new_val

    def _stop_container(self) -> None:
        _stop_container(self._container)

    def move_fixtures_dir(self, new_dir: str) -> None:
        """Move the fixtures directory to the given new directory.

        :param new_dir: The new directory where the fixtures should be
            located. This directory will be created within ``FIXTURES_ROOT``.
        :returns: Nothing
        """
        new_path = f'{FIXTURES_ROOT}/{new_dir}'
        self.run_command(
            [
                BASH_PATH,
                '-c',
                (
                    'mv "{old_path}" "{new_path}" && '
                    'chown {user}:"$(id -gn {user})" "{new_path}"'
                ).format(
                    user=CODEGRADE_USER,
                    old_path=self.fixtures_dir,
                    new_path=new_path,
                ),
            ],
        )
        self._fixtures_dir = new_dir

    @property
    def fixtures_dir(self) -> str:
        """The directory where the fixtures are located.
        """
        inner_dir = self._fixtures_dir or PRE_STUDENT_FIXTURES_DIR.strip('/')
        return f'{FIXTURES_ROOT}/{inner_dir}/'

    @property
    def output_dir(self) -> str:
        """Get the output dir for this running container.

        For now this is a global variable, but this might change in a future
        version.
        """
        return OUTPUT_DIR

    @contextlib.contextmanager
    def stopped_container(self
                          ) -> t.Generator['AutoTestContainer', None, None]:
        """Temporarily stop the container.

        The container will be stopped for the body of the ``with`` block.
        """
        self._stop_container()
        try:
            yield AutoTestContainer(
                self._name,
                self._config,
                cont=self._container,
                maybe_quit_running=self._maybe_quit_running
            )
        finally:
            _start_container(
                self._container,
                always=True,
                check_network=self._network_is_enabled,
                maybe_quit_running=self._maybe_quit_running,
            )

    def destroy_snapshots(self) -> None:
        """Destroy all snapshots of this container.
        """
        self._stop_container()
        with self._SNAPSHOT_LOCK, timed_code(
            'destroy_snapshots', snapshot_amount=len(self._snapshots)
        ):
            while self._snapshots:
                self._container.snapshot_destroy(self._snapshots.pop())

    def pin_to_core(self, core_number: int) -> None:
        self.set_cgroup_item('cpuset.cpus', str(core_number))

    def set_cgroup_item(self, key: str, value: str) -> None:
        """Set a cgroup option in the given container.

        :param key: The cgroup key to be set.
        :param value: The value to set.
        :raises StopRunningTestsException: When the value could not be set
            successfully.
        """
        with cg_logger.bound_to_logger(cgroup_key=key, cgroup_value=value):
            for _ in helpers.retry_loop(
                5, make_exception=StopRunningTestsException
            ):
                success = self._container.set_cgroup_item(key, value)
                if success:
                    return

    def _create_snapshot(self) -> None:
        with self._SNAPSHOT_LOCK:
            snap = self._container.snapshot()
            assert isinstance(snap, str)
            self._snapshots.append(snap)
            self._dirty = False

    @timed_function
    def disable_network(self) -> None:
        """Disable the network of this container.
        """
        if not self._network_is_enabled:
            return
        self._network_is_enabled = False
        self._stop_container()

        with self._NETWORK_LOCK:

            self._networks = []
            for network in self._container.network:
                net = (
                    network.type,
                    [(attr, getattr(network, attr)) for attr in dir(network)]
                )
                self._networks.append(Network(net))
            for network_idx in range(len(self._container.network)):
                assert self._container.network.remove(network_idx)

        _start_container(
            self._container,
            check_network=False,
            maybe_quit_running=self._maybe_quit_running
        )

    @timed_function
    def enable_network(self) -> None:
        """Enable the network of this container.
        """
        if self._network_is_enabled:
            return
        self._network_is_enabled = True
        self._stop_container()

        with self._NETWORK_LOCK:
            for typ, network in self._networks:
                assert self._container.network.add(typ)

                # -1 index doesn't work, as this isn't a true list
                last_index = len(self._container.network) - 1
                for key, value in network:
                    setattr(self._container.network[last_index], key, value)

        _start_container(
            self._container,
            check_network=True,
            maybe_quit_running=self._maybe_quit_running
        )

    @contextlib.contextmanager
    def as_snapshot(self, disable_network: bool = False
                    ) -> t.Generator['StartedContainer', None, None]:
        """Create a snapshot of the running container.

        .. warning::

          The state of the network of the container will be altered by doing
          this. To also restore the network use
          :meth:`.StartedContainer.enable_network` and
          :meth:`.StartedContainer.disable_network`.
        """
        # NOTE: This code never destroys snapshots, as this logic makes the
        # function way harder to follow. As we keep a dirty flag, only one
        # snapsnot will probably be created.

        self._maybe_quit_running()

        if disable_network:
            self.disable_network()
        else:
            self.enable_network()

        try:

            if self._dirty or not self._snapshots:
                with timed_code(
                    'create_snapshot',
                    container=self._name,
                    amount_of_snapshots=len(self._snapshots)
                ):
                    self._stop_container()
                    self._create_snapshot()
                    _start_container(
                        self._container,
                        check_network=not disable_network,
                        maybe_quit_running=self._maybe_quit_running
                    )
            else:
                logger.info(
                    'Snapshot creation not needed',
                    snapshots=self._snapshots,
                    dirty=self._dirty
                )
            yield self
        finally:
            # Creating the snapshot, so we might not have a snapshot
            if self._snapshots:
                self._stop_container()
                with self._SNAPSHOT_LOCK, timed_code('restore_snapshots'):
                    self._container.snapshot_restore(self._snapshots[-1])
                self._dirty = False
                _start_container(
                    self._container,
                    check_network=not disable_network,
                    maybe_quit_running=self._maybe_quit_running
                )

    @staticmethod
    def _read_fifo(
        files: t.Mapping[str, OutputCallback], stop: LockableValue[bool]
    ) -> None:
        fds = {}

        try:
            for fname, callback in files.items():
                # We use os primitives here to make sure we get a non blocking
                # file descriptor.
                f = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)
                fds[f] = callback

            while fds and not stop.get():
                reads, _, _ = select.select(list(fds.keys()), [], [], 0.5)
                for f in reads:
                    # Read at most 1024, this is a low value as otherwise we
                    # might fill the limited output buffers with only one of
                    # the two file descriptors. (see
                    # ``_make_restricted_append`` for how the shared output
                    # buffers work).
                    data = os.read(f, 1024)
                    if data:
                        # We know that select returns a subset of its
                        # arguments, so ``f`` should always be in ``fds``.
                        fds[f](data)
                    else:
                        # This file descriptor is done, so remove it from our
                        # dictionary. Other fds might still be active so we
                        # don't return here.
                        os.close(f)
                        del fds[f]
        except:  # pylint: disable=bare-except
            # pragma: no cover
            logger.error(
                'Something went wrong when reading output', exc_info=True
            )
            raise
        finally:
            for f in fds:
                os.close(f)

    @staticmethod
    def _change_user(username: str) -> None:  # pragma: no cover
        # We cannot cover this as it is run in another process which will
        # execvp.
        pw_record = pwd.getpwnam(username)
        group_ids = [g.gr_gid for g in grp.getgrall() if username in g.gr_mem]
        user_uid = pw_record.pw_uid
        user_gid = pw_record.pw_gid

        os.setgroups(group_ids)
        os.setgid(user_gid)
        os.setuid(user_uid)

    def _create_env(self, username: str) -> t.Dict:
        """Create the env for within a lxc subprocess call.

        Overrides environment variables set with
        :meth:`StartedContainer.extra_env`.

        >>> import getpass
        >>> cur_user = getpass.getuser()
        >>> env = StartedContainer(None, '', {}, None)._create_env(cur_user)
        >>> env['USER'] == cur_user
        True
        >>> isinstance(env['USER'], str)
        True
        >>> isinstance(env['HOME'], str)
        True
        >>> isinstance(env['FIXTURES'], str)
        True
        >>> isinstance(env['STUDENT'], str)
        True
        """
        env = os.environ

        user = username
        home_dir = _get_home_dir(username)

        extra_path = (
            f'~/bin/:~/.pyenv/bin/:~/.local/bin:{home_dir}/.local/bin/'
            f':{home_dir}/bin/'
        )

        new_env = self._extra_env.copy()
        new_env.update(
            {
                'PATH': f'{extra_path}:/usr/sbin/:/sbin/:{env["PATH"]}',
                'USER': user,
                'LOGUSER': user,
                'HOME': home_dir,
                'DEBIAN_FRONTEND': 'noninteractive',
                'TERM': 'dumb',
                'FIXTURES': self.fixtures_dir,
                'STUDENT': f'{_get_home_dir(username)}/student/',
                'AT_OUTPUT': self.output_dir,
                'LANG': 'en_US.UTF-8',
                'LC_ALL': 'en_US.UTF-8',
            }
        )
        return new_env

    @contextlib.contextmanager
    def extra_env(self, extra_env: t.Mapping[str, str]) -> t.Iterator:
        """Temporarily set extra environment variables in all processes that
        run in this container.

        Supports nesting. Variables defined in the inner context manager take
        precedence over variables defined in the outer one.

        :param extra_env: The extra environment variables to set. This is a
            mapping from variable name to value.
        """
        old_extra_env = self._extra_env
        new_extra_env = old_extra_env.copy()
        new_extra_env.update(extra_env)

        try:
            self._extra_env = new_extra_env
            yield
        finally:
            self._extra_env = old_extra_env

    @staticmethod
    def _signal_start() -> None:
        lxc.Container.signal_start()

    def _run_command(
        self, cmd_user: t.Tuple[t.List[str], t.Optional[str]]
    ) -> int:
        cmd, user = cmd_user
        env = self._create_env(user or CODEGRADE_USER)

        if user:
            self._change_user(user)

        self._signal_start()
        os.execvpe(cmd[0], cmd, env)

    def _run_shell(self, cmd_cwd_user: t.Tuple[str, str, str]) -> int:
        cmd, cwd, user = cmd_cwd_user
        env = self._create_env(user)
        home_dir = _get_home_dir(CODEGRADE_USER)
        env['PATH'] += f'{home_dir}/student/:{self.fixtures_dir}'

        self._change_user(user)
        cmd_list = [BASH_PATH, '-c', cmd]
        os.chdir(cwd)

        self._signal_start()
        os.execve(cmd_list[0], cmd_list, env)

    @staticmethod
    def _make_restricted_append(
        lst: t.List[bytes],
        size_left: LockableValue[int],
        callback: t.Callable[[bytes], None] = lambda _: None
    ) -> t.Callable[[bytes], None]:
        r"""Make a restricted append function.

        The returned function will append its argument to ``lst`` while
        ``size_left`` is still higher than 0. It is safe to share ``size_left``
        between multiple append functions, the total size of all lists will not
        exceed ``size_left`` in this case. The function ``callback`` is called
        for every output, no matter how much output we already received.

        >>> from copy import deepcopy
        >>> max_size = LockableValue(10)
        >>> lst = []
        >>> append = StartedContainer._make_restricted_append(lst, max_size)
        >>> for i in range(100): append(str(i))
        >>> len(lst)
        11
        >>> lst[-1]
        b' <OUTPUT TRUNCATED>\n'
        >>> old_lst = deepcopy(lst)
        >>> append('something')
        >>> old_lst == lst
        True

        >>> max_size = LockableValue(10)
        >>> lst = []
        >>> append = StartedContainer._make_restricted_append(lst, max_size)
        >>> append('1234567890abcdefghi')
        >>> len(lst)
        2
        >>> lst[0]
        '1234567890'
        >>> lst2 = []
        >>> append2 = StartedContainer._make_restricted_append(lst2, max_size)
        >>> append2('bytes')
        >>> append2('bytes')
        >>> lst2
        [b' <OUTPUT TRUNCATED>\n']
        """
        outputed_truncated_emitted = False

        def emit_truncated() -> None:
            nonlocal outputed_truncated_emitted
            if not outputed_truncated_emitted:
                lst.append(b' <OUTPUT TRUNCATED>\n')
                outputed_truncated_emitted = True

        def fun(data: bytes) -> None:
            callback(data)
            if outputed_truncated_emitted:
                return

            with size_left as inner:
                if inner.value < 0:
                    emit_truncated()
                    return
                elif len(data) > inner.value:
                    new_val = data[:inner.value]
                    if new_val:
                        lst.append(new_val)
                    emit_truncated()
                else:
                    lst.append(data)
                inner.value = inner.value - len(data)

        return fun

    def run_student_command(
        self,
        cmd: str,
        timeout: float,
        stdin: t.Union[None, bytes] = None,
        *,
        cwd: str = None,
        keep_stdout_tail: bool = False,
    ) -> StudentCommandResult:
        """Run a command provided by the student or teacher.

        The main difference between this function and
        :meth:`StartedContainer.run_command` is that the command here is a
        string and it will be executed by a shell.

        :param cmd: The command that should be executed.
        :param timeout: The maximum amount of time the command may take in
            seconds.
        :param stdin: The stdin that should be provided to the command.
        :param cwd: The location in which the command should be executed.
        :returns: A tuple of four items, which are respectively the exit code
            of the command, the produced stdout, the produced stderr and the
            time taken by the command.
        """
        stdout: t.List[bytes] = []
        stderr: t.List[bytes] = []
        max_tail_len = self._config['AUTO_TEST_MAX_OUTPUT_TAIL']
        stdout_tail: t.Deque[int] = collections.deque([], maxlen=max_tail_len)
        tail_overflowed: bool = False

        user = CODEGRADE_USER
        if cwd is None:
            cwd = f'{_get_home_dir(user)}/student/'

        assert timeout > 0
        max_size = self._config['AUTO_TEST_OUTPUT_LIMIT']
        assert max_size > 0

        size_left = LockableValue(max_size)

        def get_stdout_and_stderr() -> t.List[str]:
            return [
                b''.join(v).decode('utf-8', 'backslashreplace')
                for v in [stdout, stderr]
            ]

        if keep_stdout_tail:

            def on_stdout(data: bytes) -> None:
                nonlocal tail_overflowed
                tail_overflowed = (
                    tail_overflowed or
                    len(data) + len(stdout_tail) > max_tail_len
                )
                stdout_tail.extend(data)
        else:

            def on_stdout(data: bytes) -> None:  # pylint: disable=unused-argument
                return

        time_spend = 0.0
        try:
            with timed_code('run_student_command') as get_time_spend:
                code = self._run(
                    cmd=(cmd, cwd, user),
                    callback=self._run_shell,
                    stdout=self._make_restricted_append(
                        stdout, size_left, on_stdout
                    ),
                    stderr=self._make_restricted_append(stderr, size_left),
                    stdin=stdin,
                    check=False,
                    timeout=timeout,
                )
            time_spend = get_time_spend()
        except CommandTimeoutException as e:
            stdout_str, stderr_str = get_stdout_and_stderr()
            raise CommandTimeoutException(
                cmd=cmd,
                stdout=stdout_str,
                stderr=stderr_str,
                time_spend=e.time_spend,
            ) from e

        stdout_str, stderr_str = get_stdout_and_stderr()
        return StudentCommandResult(
            exit_code=code,
            stdout=stdout_str,
            stderr=stderr_str,
            time_spend=time_spend,
            stdout_tail=OutputTail(
                data=stdout_tail, overflowed=tail_overflowed
            ),
        )

    def run_command(
        self,
        cmd: t.List[str],
        stdout: t.Union[OutputCallback, None, str] = None,
        stderr: t.Optional[OutputCallback] = None,
        stdin: t.Optional[bytes] = None,
        user: t.Optional[str] = None,
        check: bool = True,
        retry_amount: int = 1,
    ) -> int:
        """Run a command in this started container.

        :param cmd: The command argument list that should be run.
        :param stdout: A callback that will be called for when we recieve
            output on stdout. This might not contain full lines, or it might
            contain multiple lines. If passed a string this is interpreted as a
            filename, where ``stdout`` is redirected to.
        :param stderr: Same as ``stdout`` but for output to stderr, only the
            file option is not supported.
        :param stdin: The stdin that should be provided to the container.
        :param user: The user that should run the command. If not provided the
            command will be executed by the root user.
        :param check: If ``true`` and exception will be raised when the exit
            code of the command is not 0.
        :param retry_amount: The amount of times the command will be retried
            when the exit code is not 0. This option has to be 1 if ``check``
            is ``False``.
        :returns: The exit code of the command.
        """
        ret: int = -1

        if retry_amount != 1:
            assert check

        for _ in helpers.retry_loop(
            retry_amount,
            sleep_time=0,
            make_exception=lambda: LXCProcessError(
                f'Command "{cmd}" crashed: {ret}',
            )
        ):
            ret = self._run(
                cmd=(cmd, user),
                callback=self._run_command,
                stdout=stdout,
                stderr=stderr,
                stdin=stdin,
                check=False,
                timeout=None
            )
            if not check or ret == 0:
                return ret

        raise RuntimeError  # pragma: no cover

    @contextlib.contextmanager
    def _prepared_output(
        self,
        stdout: t.Union[OutputCallback, None, str],
        stderr: t.Optional[OutputCallback],
        stdin: t.Union[None, bytes],
    ) -> t.Generator[t.Tuple[t.IO[bytes], t.BinaryIO, t.BinaryIO, threading.
                             Event, t.Callable[[float], None]], None, None]:

        with tempfile.TemporaryDirectory() as output_dir, (
            open('/dev/null', 'rb')
            if stdin is None else tempfile.NamedTemporaryFile()
        ) as stdin_file:
            local_logger = structlog.threadlocal.as_immutable(logger)
            if stdin is not None:
                os.chmod(stdin_file.name, 0o777)
                stdin_file.write(stdin)
                stdin_file.flush()
                stdin_file.seek(0, 0)

            def _make_log_function(log_location: str
                                   ) -> t.Callable[[bytes], None]:
                def inner(__data: bytes) -> None:
                    local_logger.info(
                        'Got output from command',
                        location=log_location,
                        output=__data,
                    )

                return inner

            def stderr_inceptor(__data: bytes) -> None:
                if not command_started.is_set():
                    if __data[0] == 0:
                        __data = __data[1:]
                    command_started.set()

                stderr_callback(__data)

            command_started = threading.Event()
            stop_reader_threads = LockableValue(False)
            stderr_callback = stderr or _make_log_function('stderr')

            stderr_fifo = os.path.join(output_dir, 'stderr')
            os.mkfifo(stderr_fifo)

            reader_fifo_files = {stderr_fifo: stderr_inceptor}

            # If `stdout` is a string this is the path to the file where stdout
            # should be redirected to.
            if not isinstance(stdout, str):
                stdout_fifo = os.path.join(output_dir, 'stdout')
                os.mkfifo(stdout_fifo)
                stdout_callback = stdout or _make_log_function('stdout')
                reader_fifo_files[stdout_fifo] = stdout_callback

            reader_thread = threading.Thread(
                target=self._read_fifo,
                args=(reader_fifo_files, stop_reader_threads)
            )
            reader_thread.start()

            def stop_reader_thread(wait_time: float) -> None:
                reader_thread.join(wait_time)
                stop_reader_threads.set(True)

            # The order is really important here! We first need to close the
            # two fifo files before we join our threads. As otherwise the
            # threads will hang because they are still reading from these
            # files.
            try:
                with open(
                    stdout if isinstance(stdout, str) else stdout_fifo, 'wb'
                ) as out, open(stderr_fifo, 'wb') as err:
                    yield (
                        stdin_file,
                        out,
                        err,
                        command_started,
                        stop_reader_thread,
                    )
            finally:
                reader_thread.join()

    def _run(
        self,
        cmd: T,
        callback: t.Callable[[T], int],
        stdout: t.Union[OutputCallback, None, str],
        stderr: t.Optional[OutputCallback],
        stdin: t.Union[None, bytes],
        check: bool,
        timeout: t.Union[None, float, int],
    ) -> int:
        self._dirty = True
        assert timeout is None or timeout > 0

        with cg_logger.bound_to_logger(
            cmd=cmd, timeout=timeout
        ), self._prepared_output(stdout, stderr, stdin) as [
            stdin_file, stdout_file, stderr_file, command_started, stop_reading
        ]:
            self._maybe_quit_running()

            pid = self._container.attach(
                callback,
                cmd,
                stdout=stdout_file,
                stderr=stderr_file,
                stdin=stdin_file,
            )

            left = 0.0

            try:
                res = _wait_for_attach(pid, command_started)
                if res is None:
                    self._maybe_quit_running()
                    res, left = _wait_for_pid(
                        pid, timeout or sys.maxsize, self._maybe_quit_running
                    )
            except CommandTimeoutException:
                logger.info('Exception occurred when waiting', exc_info=True)
                # Wait for 1 second to clear all remaining output.
                left = 1
                raise
            finally:
                # Wait for at most a minute to clear all remaining output.
                left = min(left, 60)
                stderr_file.close()
                stdout_file.close()
                stop_reading(left)

        if check and res != 0:
            raise LXCProcessError(f'Command "{cmd}" crashed: {res}')

        return res


class AutoTestContainer:
    """This class represents a lxc container that will be used in an AutoTest.

    This container might be started, not started. To execute commands you
    should use the :class:`StartedContainer` class which can be obtained using
    the :meth:`AutoTestContainer.started_container` method.
    """

    def __init__(
        self,
        name: str,
        config: 'psef.FlaskConfig',
        *,
        cont: t.Optional[lxc.Container] = None,
        maybe_quit_running: MaybeQuitRunning,
    ) -> None:
        self._name = name
        self._lock = threading.RLock()
        self._config = config
        if cont is None:
            self._cont = lxc.Container(name)
        else:
            self._cont = cont
        self._maybe_quit_running = maybe_quit_running

    @property
    def name(self) -> str:
        """Get the name of this container.
        """
        return self._name

    def create(self) -> None:
        """Create a backing lxc container for this AutoTestContainer.
        """
        created = self._cont.create(
            'download',
            0, {
                'dist': 'ubuntu',
                'release': 'bionic',
                'arch': 'amd64',
            },
            bdevtype=self._config['AUTO_TEST_BDEVTYPE']
        )
        if not created:  # pragma: no cover
            raise AssertionError(
                'Failed to create container, last error {}'.format(
                    self._cont.last_error
                )
            )

    @contextlib.contextmanager
    def started_container(self) -> t.Generator[StartedContainer, None, None]:
        """Start a block wherein this container is started.
        """
        started = None

        try:
            self.start_container()
            started = StartedContainer(
                self._cont, self._name, self._config, self._maybe_quit_running
            )
            yield started
        finally:
            self._stop_container(started)

    def start_container(self) -> None:
        _start_container(
            self._cont, maybe_quit_running=self._maybe_quit_running
        )

    def destroy_container(self) -> None:
        self._cont.destroy()

    def _stop_container(self, cont: t.Optional[StartedContainer]) -> None:
        with cg_logger.bound_to_logger(cont=self):
            try:
                _stop_container(self._cont)
                if cont is not None:
                    logger.info('Destroying snapshots')
                    cont.destroy_snapshots()
            finally:
                with timed_code('destroy_container'):
                    self.destroy_container()

    def clone(self, *, new_name: str = '') -> 'AutoTestContainer':
        """Clone this container to a new container.

        :param new_name: The name of the new container, will be randomly
            generated if not provided.
        :returns: A clone of this container with the provided name.
        """
        self._maybe_quit_running()

        with self._lock, timed_code('clone_container'):
            new_name = new_name or _get_new_container_name()
            cont = self._cont.clone(new_name)
            assert isinstance(cont, lxc.Container)
            return type(self)(
                new_name,
                self._config,
                cont=cont,
                maybe_quit_running=self._maybe_quit_running
            )


class AutoTestRunner:
    """This class contains all functionality needed to run a single AutoTest.
    """

    def __init__(
        self, base_url: URL, instructions: RunnerInstructions,
        global_password: str, config: 'psef.FlaskConfig'
    ) -> None:
        self._global_password = global_password
        self.instructions = instructions
        result_ids = instructions['result_ids']
        self.work = [
            cg_worker_pool.Work(result_id=result_id, student_id=student_id)
            for result_id, student_id in
            zip(result_ids, instructions.get('student_ids', result_ids))
        ]
        self.auto_test_id = instructions['auto_test_id']
        self.config = config
        self.setup_script = self.instructions['setup_script']
        self.base_url = (
            f'{base_url}/api/v-internal/auto_tests/{self.auto_test_id}'
        )

        self.fixtures = self.instructions['fixtures']
        self._reqs: t.Dict[t.Tuple[int, int], requests.Session] = {}

        self._stop_running = multiprocessing.Event()

    def _stop_running_is_set(self) -> bool:
        return self._stop_running.is_set()

    def _set_stop_running(self) -> None:
        self._stop_running.set()

    def _maybe_quit_running(self) -> None:
        """Throw appropriate exception if container should stop running.

        >>> from collections import defaultdict
        >>> self = AutoTestRunner('', defaultdict(list), '', {})
        >>> self._maybe_quit_running() is None
        True
        >>> self._set_stop_running()
        >>> self._maybe_quit_running()
        Traceback (most recent call last):
        ...
        StopContainerException
        >>> self._stop_running.clear()
        >>> self._maybe_quit_running() is None
        True
        """
        if self._stop_running_is_set():
            raise StopContainerException

    @staticmethod
    def _get_amount_of_needed_workers() -> int:
        """Get the amount of needed workers.

        >>> AutoTestRunner._get_amount_of_needed_workers() >= 4
        True
        """
        return _get_amount_cpus() + 4

    @staticmethod
    def _should_poll_after_done(instructions: RunnerInstructions) -> bool:
        """Should we poll after done.

        >>> AutoTestRunner._should_poll_after_done({})
        False
        >>> AutoTestRunner._should_poll_after_done({'poll_after_done': True})
        True
        """
        return instructions.get('poll_after_done', False)

    def _make_worker_pool(
        self,
        base_container_name: str,
        cpu_cores: CpuCores,
    ) -> cg_worker_pool.WorkerPool:
        mult = int(self._should_poll_after_done(self.instructions))

        return cg_worker_pool.WorkerPool(
            # Over provision a bit so clones can be made quicker.
            processes=self._get_amount_of_needed_workers(),
            function=lambda get_work:
            _run_student(self, base_container_name, cpu_cores, get_work),
            sleep_time=self.config['AUTO_TEST_CF_SLEEP_TIME'],
            extra_amount=mult * self.config['AUTO_TEST_CF_EXTRA_AMOUNT'],
            initial_work=self.work,
        )

    def _work_producer(self, last_call: bool) -> t.List[cg_worker_pool.Work]:
        url = furl.furl(self.base_url).add(
            path=['runs', self.instructions['run_id'], 'results', ''],
            args={
                'last_call': last_call,
                'limit': _get_amount_cpus() * 4,
            },
        )
        res = self.req.get(str(url), timeout=_REQUEST_TIMEOUT)
        res.raise_for_status()
        return [cg_worker_pool.Work(**item) for item in res.json()]

    @staticmethod
    def _make_req_key() -> t.Tuple[int, int]:
        """
        >>> import threading, multiprocessing
        >>> key = AutoTestRunner._make_req_key()
        >>> key == AutoTestRunner._make_req_key()
        True
        >>> def test_f(): print(AutoTestRunner._make_req_key() == key)
        >>> def test_ff(): assert AutoTestRunner._make_req_key() == key
        >>> t = threading.Thread(target=test_f)
        >>> t.start(); t.join()
        False
        >>> p = multiprocessing.Process(target=test_ff)
        >>> p.start(); p.join()
        >>> p.exitcode == 1
        True
        >>> key == AutoTestRunner._make_req_key()
        True
        """
        return os.getpid(), threading.get_ident()

    @staticmethod
    def _get_retry_adapter() -> HTTPAdapter:
        return HTTPAdapter(
            max_retries=Retry(
                total=_REQUEST_RETRIES,
                read=_REQUEST_RETRIES,
                connect=_REQUEST_RETRIES,
                status=_REQUEST_RETRIES,
                backoff_factor=_REQUEST_BACKOFF_FACTOR,
                method_whitelist=frozenset(
                    [*Retry.DEFAULT_METHOD_WHITELIST, 'PATCH']
                ),
                status_forcelist=(500, 501, 502, 503, 504),
            )
        )

    @property
    def req(self) -> requests.Session:
        """Get a request session unique for this thread and process.

        :returns: A requests session unique for this thread and process that
            has the correct headers for authentication.
        """
        key = self._make_req_key()

        if key not in self._reqs:
            req = requests.Session()
            req.auth = ('', '')
            req.headers.update(
                {
                    'CG-Internal-Api-Password': self._global_password,
                    'CG-Internal-Api-Runner-Password': self._local_password,
                }
            )
            adapter = self._get_retry_adapter()
            req.mount('http://', adapter)
            req.mount('https://', adapter)
            self._reqs[key] = req
        return self._reqs[key]

    @property
    def _local_password(self) -> str:
        return self.instructions["runner_id"]

    @property
    def _wget_headers(self) -> t.List[str]:
        return [
            '--header',
            f'CG-Internal-Api-Password: {self._global_password}',
            '--header',
            f'CG-Internal-Api-Runner-Password: {self._local_password}',
        ]

    def download_file(
        self,
        cont: StartedContainer,
        url: str,
        dst: str,
        from_home: bool = True
    ) -> None:
        """Download the given url to the given destination.

        :param cont: The container in which to download the files.
        :param url: The url from which to download the files.
        :param dst: The path in the container where to store the file.
        :param from_home: Should the ``dst`` path be interpreted as a relative
            path from the home directory of the codegrade user.
        """
        if from_home:
            dst = f'{_get_home_dir(CODEGRADE_USER)}/{dst}'
        for _ in helpers.retry_loop(
            _REQUEST_RETRIES,
            sleep_time=lambda n: min(
                _REQUEST_BACKOFF_FACTOR * (2 ** (n - 1)),
                Retry.BACKOFF_MAX,
            ),
            make_exception=StopRunningStudentException
        ):
            if cont.run_command(
                [
                    'wget',
                    *self._wget_headers,
                    f'{self.base_url}/{url}',
                    '-O',
                    dst,
                ],
                user=CODEGRADE_USER,
                check=False,
            ) == 0:
                break
        cont.run_command(['chmod', '-R', '750', dst], user=CODEGRADE_USER)
        logger.info('Downloaded file', dst=dst, url=url)

    def download_fixtures(self, cont: StartedContainer) -> None:
        """Download all the fixtures of this test.

        :param cont: The container in which the fixtures should be downloaded.
        """
        for name, fixture_id in self.fixtures:
            self.download_file(
                cont,
                f'fixtures/{fixture_id}',
                f'{cont.fixtures_dir}{name}',
                from_home=False,
            )

        cont.run_command(
            ['ls', '-hl', cont.fixtures_dir],
            user=CODEGRADE_USER,
        )

    @timed_function
    def download_student_code(
        self, cont: StartedContainer, result_id: int
    ) -> None:
        """Download the code of the student.

        :param cont: The lxc container in which to download the code.
        :param result_id: The id of the code which should be downloaded.
        """
        url = f'results/{result_id}?type=submission_files'
        self.download_file(cont, url, 'student.zip')

        cont.run_command(
            [
                'unzip', '-DD', f'{_get_home_dir(CODEGRADE_USER)}/student.zip',
                '-d', f'{_get_home_dir(CODEGRADE_USER)}/student/'
            ],
            user=CODEGRADE_USER
        )
        logger.info('Extracted student code')

        cont.run_command(
            ['chmod', '-R', '+x', f'{_get_home_dir(CODEGRADE_USER)}/student/'],
            user=CODEGRADE_USER
        )
        cont.run_command(
            ['rm', '-f', f'{_get_home_dir(CODEGRADE_USER)}/student.zip']
        )

    @timed_function
    def _upload_output_folder(
        self,
        cont: StartedContainer,
        result_id: int,
        test_suite: SuiteInstructions,
    ) -> None:
        has_files = False

        def stdout_callback(output: bytes) -> None:
            nonlocal has_files
            if output:
                has_files = True

        cont.run_command(
            ['find', cont.output_dir, '-type', 'f'],
            stdout=stdout_callback,
        )
        if not has_files:
            return

        with tempfile.NamedTemporaryFile() as tfile:
            os.chmod(tfile.name, 0o622)
            cont.run_command(
                ['tar', 'cjf', '/dev/stdout', cont.output_dir],
                user=CODEGRADE_USER,
                stdout=tfile.name
            )
            tfile.seek(0, 0)

            suite_id = test_suite['id']
            base = self.base_url
            url = f'{base}/results/{result_id}/suites/{suite_id}/files/'
            response = self.req.post(
                url,
                files={
                    'file': ('f.tar.bz2', tfile, 'application/octet-stream'),
                },
            )
            logger.info(
                'Uploaded files to server',
                response=response,
                response_content=response.content
            )

    @timed_function
    def _run_test_suite(
        self, student_container: StartedContainer, result_id: int,
        test_suite: SuiteInstructions, cpu_core: CpuCores.Core
    ) -> t.Tuple[float, float]:
        total_points = 0.0
        possible_points = 0.0

        def yield_core() -> None:
            with snap.stopped_container():
                cpu_core.yield_core()
            snap.pin_to_core(cpu_core.get_core_number())

        extra_env = self._get_suite_env(
            result_id,
            submission_info=test_suite.get('submission_info', False),
        )

        step_result_id: t.Optional[int] = None

        def outer_update_test_result(
            state: models.AutoTestStepResultState,
            log: t.Dict[str, object],
            test_step: StepInstructions,
            attachment: t.Optional[t.IO[bytes]],
        ) -> None:
            nonlocal step_result_id
            data = {
                'log': log,
                'state': state.name,
                'auto_test_step_id': test_step['id'],
                'has_attachment': attachment is not None,
            }
            if step_result_id is not None:
                data['id'] = step_result_id

            logger.info('Posting result data', json=data, url=url)
            if attachment is not None:
                json_data = io.StringIO()
                json.dump(data, json_data)
                json_data.seek(0, 0)

                response = self.req.put(
                    url,
                    files={
                        'attachment': attachment,
                        'json': json_data,
                    },
                    timeout=_REQUEST_TIMEOUT,
                )
            else:
                response = self.req.put(
                    url,
                    json=data,
                    timeout=_REQUEST_TIMEOUT,
                )
            logger.info('Posted result data', response=response)
            response.raise_for_status()
            step_result_id = response.json()['id']

        with student_container.as_snapshot(
            test_suite['network_disabled']
        ) as snap, snap.extra_env(extra_env):
            url = f'{self.base_url}/results/{result_id}/step_results/'

            for idx, test_step in enumerate(test_suite['steps']):
                logger.info('Running step', step=test_step)
                step_result_id = None

                def update_test_result(
                    state: models.AutoTestStepResultState,
                    log: t.Dict[str, object],
                    *,
                    attachment: t.Optional[t.IO[bytes]] = None,
                    test_step: StepInstructions = test_step,
                ) -> None:
                    return outer_update_test_result(
                        state, log, test_step=test_step, attachment=attachment
                    )

                typ = auto_test_handlers[test_step['test_type_name']]

                with timed_code('run_suite_step'
                                ) as get_step_time, cg_logger.bound_to_logger(
                                    test_step=test_step
                                ):
                    try:
                        total_points += typ.execute_step(
                            snap,
                            ExecuteOptions(
                                update_test_result=update_test_result,
                                test_instructions=test_step,
                                achieved_percentage=helpers.safe_div(
                                    total_points, possible_points, 1
                                ),
                                yield_core=yield_core,
                            )
                        )
                    except StopRunningStepsException:
                        logger.info('Stopping steps', exc_info=True)
                        # We still need the correct amount of possible points,
                        # so we update it here.
                        possible_points += sum(
                            ts['weight']
                            for ts in test_suite['steps'][idx + 1:]
                        )
                        break
                    except CommandTimeoutException as e:
                        logger.warning('Command timed out', exc_info=True)
                        update_test_result(
                            models.AutoTestStepResultState.timed_out, {
                                'exit_code': e.EXIT_CODE,
                                'stdout': e.stdout,
                                'stderr': e.stderr,
                                'time_spend': get_step_time(),
                            }
                        )
                        yield_core()
                    else:
                        logger.info('Finished step', total_points=total_points)
                    finally:
                        possible_points += test_step['weight']

            self._upload_output_folder(snap, result_id, test_suite)

        return total_points, possible_points

    @staticmethod
    def _is_old_submission_error(
        exc: t.Union[Exception, requests.Response]
    ) -> bool:
        """Check if the given exception is a ``NOT_NEWEST_SUBMSSION`` error.

        >>> f = AutoTestRunner._is_old_submission_error
        >>> f(Exception())
        False
        >>> r = requests.HTTPError()
        >>> f(r)
        False
        >>> r.response = requests.get('https://google.com')
        >>> f(r)
        False
        >>> # Get {"code": "NOPE"}
        >>> r.response = requests.get('http://www.mocky.io/v2/5d9e5e2d320000c532329d37')
        >>> f(r)
        False
        >>> f(r.response)
        False
        """
        if isinstance(exc, requests.HTTPError):
            if exc.response is None:
                return False
            response = exc.response
        elif isinstance(exc, requests.Response):
            response = exc
        else:
            return False

        try:
            res = response.json()
        except ValueError:
            return False

        res = res if isinstance(res, dict) else {}
        return res.get('code', None) == APICodes.NOT_NEWEST_SUBMSSION.name

    @timed_function
    def _run_student(  # pylint: disable=too-many-statements,too-many-branches
        self,
        cont: StartedContainer,
        cpu: CpuCores.Core,
        result_id: int,
    ) -> bool:
        # TODO: Split this function
        result_url = f'{self.base_url}/results/{result_id}'

        result_state: t.Optional[models.AutoTestStepResultState]
        result_state = models.AutoTestStepResultState.passed

        try:
            with timed_code('set_cgroup_limits'):
                cont.set_cgroup_item(
                    'memory.limit_in_bytes',
                    self.config['AUTO_TEST_MEMORY_LIMIT']
                )
                cont.pin_to_core(cpu.get_core_number())
                cont.set_cgroup_item(
                    'memory.memsw.limit_in_bytes',
                    self.config['AUTO_TEST_MEMORY_LIMIT']
                )

            self.download_student_code(cont, result_id)

            cont.move_fixtures_dir(uuid.uuid4().hex)
            self._maybe_run_setup(cont, self.setup_script, result_url)

            logger.info('Dropping sudo rights')
            cont.run_command(['deluser', CODEGRADE_USER, 'sudo'])
            # TODO: escape the codegrade user here if that is needed
            cont.run_command(
                ['sed', '-i', f's/^{CODEGRADE_USER}.*$//g', '/etc/sudoers']
            )
            assert cont.run_command(
                ['grep', '-c', CODEGRADE_USER, '/etc/sudoers'], check=False
            ) != 0, 'Sudo was not dropped!'

            cont.run_command(
                [
                    BASH_PATH,
                    '-c',
                    (
                        'mkdir -p "{output_dir}" && '
                        'chown -R {user}:"$(id -gn {user})" "{output_dir}" && '
                        'chmod 770 "{output_dir}"'
                    ).format(
                        output_dir=OUTPUT_DIR,
                        user=CODEGRADE_USER,
                    ),
                ]
            )

            total_points = 0.0
            possible_points = 0.0

            for test_set in self.instructions['sets']:
                for test_suite in test_set['suites']:
                    cont.move_fixtures_dir(uuid.uuid4().hex)
                    achieved_points, suite_points = self._run_test_suite(
                        cont, result_id, test_suite, cpu
                    )
                    total_points += achieved_points
                    possible_points += suite_points
                    logger.info(
                        'Finished suite',
                        total_points=total_points,
                        test_suite=test_suite,
                    )
                logger.info(
                    'Finished set',
                    total_points=total_points,
                    stop_points=test_set['stop_points'],
                    test_set=test_set,
                )

                if helpers.FloatHelpers.le(
                    helpers.safe_div(total_points, possible_points, 1),
                    test_set['stop_points']
                ):
                    break
        except (StopRunningStudentException, *NETWORK_EXCEPTIONS) as e:
            result_state = None
            if self._is_old_submission_error(e):
                logger.warning('Was running old submission', exc_info=True)
            elif isinstance(e, StopRunningStudentException):
                logger.error('Stop running student exception', exc_info=True)
            else:
                logger.warning(
                    'HTTP error, so stopping this student', exc_info=True
                )
            return False
        except StopRunningTestsException:
            result_state = None
            logger.error('Stop running steps', exc_info=True)
            raise
        except cg_worker_pool.KillWorkerException:
            result_state = None
            logger.error('Worker wanted to be killed', exc_info=True)
            return False
        except:
            logger.error('Something went wrong', exc_info=True)
            result_state = models.AutoTestStepResultState.failed
            raise
        else:
            result_state = models.AutoTestStepResultState.passed
            return True
        finally:
            if result_state is not None:
                self.req.patch(
                    result_url,
                    json={'state': result_state.name},
                    timeout=_REQUEST_TIMEOUT,
                )

    def run_student(
        self, base_container_name: str, cpu_cores: CpuCores,
        opts: cg_worker_pool.CallbackArguments
    ) -> None:
        """Run the test for a single student.

        :param base_container_name: The name of the base lxc container.
        :param cpu_cores: The cpu cores which are available during testing.
        :param result_id: The id of the student to run.
        :param opts: The way to get work from the worker pool.
        :returns: Nothing.
        """
        base_container = AutoTestContainer(
            base_container_name,
            self.config,
            maybe_quit_running=self._maybe_quit_running
        )
        student_container = base_container.clone()

        def retry_work(work: cg_worker_pool.Work) -> None:
            try:
                self.req.patch(
                    f'{self.base_url}/results/{work.result_id}',
                    json={
                        'state':
                            models.AutoTestStepResultState.not_started.name
                    },
                    timeout=_REQUEST_TIMEOUT,
                )
            except:  # pylint: disable=bare-except
                pass
            finally:
                opts.retry_work(work)

        with student_container.started_container() as cont:
            while True:
                work = opts.get_work()
                if work is None:
                    return
                result_id = work.result_id

                with cpu_cores.reserved_core() as cpu:
                    patch_res = self.req.patch(
                        f'{self.base_url}/results/{result_id}',
                        json={
                            'state':
                                models.AutoTestStepResultState.running.name
                        },
                        timeout=_REQUEST_TIMEOUT,
                    )

                    try:
                        patch_res.raise_for_status()
                    except requests.HTTPError as e:
                        if self._is_old_submission_error(e):
                            opts.mark_work_as_finished(work)
                        else:
                            retry_work(work)
                        continue

                    if patch_res.json()['taken']:
                        opts.mark_work_as_finished(work)
                    else:
                        with cg_logger.bound_to_logger(result_id=result_id):
                            if self._run_student(cont, cpu, result_id):
                                opts.mark_work_as_finished(work)
                            else:
                                # Student didn't finish correctly. So put back
                                # in the queue. The retry function contains the
                                # functionality for only retrying a fixed
                                # amount of time.
                                retry_work(work)
                            return

    def _get_suite_env(
        self,
        result_id: int,
        *,
        submission_info: bool,
    ) -> t.Mapping[str, str]:
        """Get environment variables to be set in the AutoTest environment of
        the given result.

        :param result_id: The id of the result to get the environment for.
        :param submission_info: Whether to include the submission information.
        :returns: A mapping from environment variable name to value.
        """
        env = {'CG_INFO': '{}'}

        if submission_info:
            env['CG_INFO'] = self._get_submission_info_json(result_id)

        return env

    def _get_submission_info_json(self, result_id: int) -> str:
        """Get information associated with the submission to be included in the
        AutoTest environment.

        :param result_id: The id of the result to get the information for.
        :returns: A JSON object with the information encoded as a string.
        """
        instructions = self.instructions
        submission_info: t.MutableMapping[str, object] = {}

        # TODO: The information we need on the instructions is still marked as
        # optional, to keep backward compatibility. This information should be
        # required in the future, which will slightly simplify the code below.

        assig_info = instructions.get('assignment_info')
        if assig_info is not None:
            submission_info['deadline'] = assig_info['deadline']
        else:  # pragma: no cover
            logger.warning(
                'No assignment info in runner instructions',
                instructions=instructions,
            )

        student_info: t.Optional[StudentInformation] = None
        student_infos = instructions.get('student_infos')
        if student_infos is not None:
            student_info = next(
                (s for s in student_infos if s['result_id'] == result_id),
                None,
            )
        if student_info is not None:
            submission_info.update(
                {
                    'result_id': student_info['result_id'],
                    'student_id': student_info['student_id'],
                    'submitted_at': student_info['created_at'],
                }
            )
        else:  # pragma: no cover
            logger.warning(
                'No student info in runner instructions',
                instructions=instructions,
            )

        return json.dumps(submission_info)

    def _started_heartbeat(self) -> 'RepeatedTimer':
        def push_heartbeat() -> None:
            if not self._stop_running_is_set():
                self.req.post(
                    f'{self.base_url}/runs/{self.instructions["run_id"]}/'
                    'heartbeats/',
                    timeout=_REQUEST_TIMEOUT,
                ).raise_for_status()

        interval = self.instructions['heartbeat_interval']
        logger.info('Starting heartbeat interval', interval=interval)
        return RepeatedTimer(interval, push_heartbeat)

    def run_test(self, cont: StartedContainer) -> None:
        """Run the test for all students using the given container as base.

        :param cont: The base container used for all students.
        :returns: Nothing.
        """
        run_result_url = f'{self.base_url}/runs/{self.instructions["run_id"]}'
        time_taken: t.Optional[float] = None

        cont.set_maybe_quit_running(self._maybe_quit_running)

        with self._started_heartbeat():
            try:
                with timed_code('run_complete_auto_test') as get_time_taken:
                    self._run_test(cont)
                time_taken = get_time_taken()
            except:  # pylint: disable=bare-except
                logger.error('Error when running tests', exc_info=True)
            finally:
                self._set_stop_running()
                self.req.patch(
                    run_result_url,
                    json={
                        'state': 'stopped',
                        'time_taken': time_taken,
                    },
                    timeout=_REQUEST_TIMEOUT,
                )

    def _maybe_run_setup(
        self,
        cont: 'StartedContainer',
        cmd: str,
        url: str,
        cwd: str = None,
    ) -> None:
        if cmd:
            with timed_code('run_setup_script', setup_cmd=cmd):
                res = cont.run_student_command(cmd, 900, cwd=cwd)

            self.req.patch(
                url,
                json={
                    'setup_time_spend': res.time_spend,
                    'setup_stdout': res.stdout,
                    'setup_stderr': res.stderr
                },
                timeout=_REQUEST_TIMEOUT,
            )

    def _run_test(self, cont: StartedContainer) -> None:
        helpers.ensure_on_test_server()
        with timed_code('run_setup_commands'):
            cont.run_command(
                [
                    BASH_PATH,
                    '-c',
                    (
                        'adduser --shell {bash_path} --disabled-password --gecos'
                        ' "" {user} && '
                        'mkdir -p "{home_dir}/student/" && '
                        'mkdir -p "{fixtures_root}/{fixtures}" && '
                        'chown -R {user}:"$(id -gn {user})" "{home_dir}" && '
                        'chown -R {user}:"$(id -gn {user})" "{fixtures_root}" && '
                        'chmod 110 "{fixtures_root}"'
                    ).format(
                        user=CODEGRADE_USER,
                        home_dir=_get_home_dir(CODEGRADE_USER),
                        fixtures=PRE_STUDENT_FIXTURES_DIR,
                        fixtures_root=FIXTURES_ROOT,
                        bash_path=BASH_PATH,
                    ),
                ],
            )

            cont.run_command(['usermod', '-aG', 'sudo', CODEGRADE_USER])

            cont.run_command(
                ['tee', '--append', '/etc/sudoers'],
                stdin=(f'\n{CODEGRADE_USER} ALL=(ALL) NOPASSWD: ALL\n'
                       ).encode('utf8')
            )
            cont.run_command(['grep', CODEGRADE_USER, '/etc/sudoers'])

        with timed_code('download_fixtures'):
            self.download_fixtures(cont)

        self._maybe_run_setup(
            cont,
            self.instructions['run_setup_script'],
            f'{self.base_url}/runs/{self.instructions["run_id"]}',
            cwd=f'{FIXTURES_ROOT}/{PRE_STUDENT_FIXTURES_DIR}',
        )

        with cont.stopped_container() as base_container, timed_code(
            'run_all_students'
        ), _Manager() as manager:
            # Known issue from typeshed:
            # https://github.com/python/typeshed/issues/3018
            cpu_cores: CpuCores = CpuCores(t.cast(_Manager, manager))
            pool = self._make_worker_pool(base_container.name, cpu_cores)

            try:
                pool.start(self._work_producer)
            except:
                logger.error('AutoTest crashed', exc_info=True)
                raise
            else:
                logger.info('Done with containers, cleaning up')
            finally:
                self._set_stop_running()
