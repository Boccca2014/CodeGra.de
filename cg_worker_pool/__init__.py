"""This module implements an alternative for ``multiprocessing.pool.Pool``.

In this implementation you can add work while the pool is running.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import threading
import traceback
import collections
import dataclasses
import multiprocessing as mp
from queue import Empty, Queue
from types import TracebackType
from multiprocessing import managers

import structlog
from typing_extensions import Protocol

logger = structlog.get_logger()

Work = t.NamedTuple('Work', [('result_id', int), ('student_id', int)])


def _make_process(*, target: t.Callable[[], object]) -> mp.Process:
    return mp.Process(target=target)


class GetWorkFunction(Protocol):
    """Protocol to get some work to run.
    """

    def __call__(self, *, block: bool = True) -> t.Optional[Work]:
        ...


class RetryWorkFunction(Protocol):
    """Protocol to retry a given work.
    """

    def __call__(self, work: Work) -> None:
        ...


class MarkWorkAsFinishedFunction(Protocol):
    """Protocol to mark work as finished.
    """

    def __call__(self, work: Work) -> None:
        ...


@dataclasses.dataclass(frozen=True)
class CallbackArguments:
    """The argument given to the `cg_worker` callback.

    :ivar get_work: Get the work to run.
    :ivar retry_work: Retry the given work.
    """
    get_work: GetWorkFunction
    retry_work: RetryWorkFunction
    mark_work_as_finished: MarkWorkAsFinishedFunction


class KillWorkerException(Exception):
    pass


class WorkerException(Exception):
    """The exception that is raised when a worker raises an exception.
    """

    def __init__(
        self, exc: Exception, tb: t.Union[None, str, TracebackType]
    ) -> None:
        super().__init__()

        self.exception = exc
        if isinstance(tb, str):
            self.formatted = tb
        else:
            self.formatted = ''.join(
                traceback.format_exception(type(exc), exc, tb)
            )

    def __str__(self) -> str:
        return '%s\nOriginal traceback:\n%s' % (
            Exception.__str__(self), self.formatted
        )

    def __reduce__(
        self
    ) -> t.Tuple[t.Type['WorkerException'], t.Tuple[Exception, str]]:
        return type(self), (self.exception, self.formatted)


class _PrioQueue:
    def __init__(self, max_retry_amount: int) -> None:
        self.queue: t.Deque[Work] = collections.deque()
        self.newest: t.Dict[int, int] = {}
        self.mutex = mp.Lock()

        self._non_finished_work: t.Set[Work] = set()

        self._version = 0
        self._amount_waiting = 0
        self._closed = False
        self._new_work = mp.Condition(self.mutex)
        self._work_needed = mp.Semaphore(0)
        self._retried: t.MutableMapping[Work, int
                                        ] = collections.defaultdict(lambda: 0)
        self._max_retry_amount = max_retry_amount

    def wait_on_work_needed(self, timeout: t.Optional[int]) -> bool:
        return self._work_needed.acquire(True, timeout=timeout)

    def notify_work_needed(self) -> None:
        """Notify that more work is needed.
        """
        with self.mutex:
            self._work_needed.release()

    def close(self) -> None:
        """Close the given queue.
        """
        with self.mutex:
            self._closed = True
            self._new_work.notify_all()
            self._work_needed.release()

    def _inc_version(self) -> None:
        self._version += 1

    def get_version(self) -> t.Tuple[object, bool, int]:
        """Get the version of the queue and if that version is empty.

        :returns: A tuple, the first value is the version (which is unique for
            this version of the queue), and the second value is if the given
            version is a version of this queue which is empty.
        """
        with self.mutex:
            return self._version, self._peek() is None, self._amount_waiting

    def put_all(self, works: t.Iterable[Work]) -> bool:
        """Put all the given work in the queue.

        :param works: The iterable of work to add.
        """
        added_amount = 0

        with self.mutex:
            for work in works:
                if work in self._non_finished_work:
                    # logger.info('Ignoring existing work', work=work)
                    continue
                logger.info('Adding new work', work=work)

                added_amount += 1
                self._non_finished_work.add(work)
                self.queue.append(work)
                self.newest[work.student_id] = work.result_id

            if added_amount > 0:
                self._inc_version()
                self._new_work.notify(added_amount)

        return added_amount > 0

    def _peek(self) -> t.Optional[Work]:
        while self.queue:
            work = self.queue[0]
            if self.newest[work.student_id] == work.result_id:
                return work
            else:
                self.queue.popleft()

        return None

    def retry(self, work: Work) -> None:
        """Retry the given work.

        If the work has been retried for more than `max_retry_amount` this
        function does nothing.

        :param work: The work to retry.
        """
        with self.mutex:
            if self._retried[work] >= self._max_retry_amount:
                self._non_finished_work.remove(work)
                self._retried[work] = 0
                return
            self._retried[work] += 1

            assert work in self._non_finished_work

            self.queue.append(work)
            # Do not update newest here. We want to retry this work, but we
            # don't want to do this if we have a newer work for this student.
            self._inc_version()
            self._new_work.notify(1)

    def get(self, *, block: bool = True) -> t.Optional[Work]:
        """Try to get more work.

        :returns: More work, or ``None`` if the queue is closed while getting
            more work.


        :param block: Should this function block if there is no more work.
        """
        logger.info('Getting new work')
        with self.mutex:
            while not self._closed:
                work = self._peek()
                if work is not None:
                    # Remove item from the queue
                    self.queue.popleft()
                    # Do not forget that what the newest work for this student
                    # is, as we might want need to retry the returned work
                    # later.
                    self._inc_version()

                    logger.info('Got new work', work=work)
                    return work
                elif not block:
                    break

                self._amount_waiting += 1
                self._work_needed.release()
                self._new_work.wait()
                self._amount_waiting -= 1

        logger.info('Got new work', work=None)
        return None

    def mark_as_finished(self, work: Work) -> None:
        """Mark given work as finished.

        This will forget about the given work completely, this means that if we
        encounter this work again (i.e. if the producer produces it again) we
        will try to process it.
        """
        with self.mutex:
            logger.info('Marking work as finished', work=work)
            self._non_finished_work.remove(work)
            self._retried[work] = 0


class _Manager(managers.SyncManager):
    pass


_Manager.register('PrioQueue', _PrioQueue)


class WorkerPool:
    """Class that implements a worker pool in which you can add more work while
    it is busy.
    """

    def __init__(
        self,
        processes: int,
        function: t.Callable[[CallbackArguments], None],
        sleep_time: float,
        extra_amount: int,
        initial_work: t.Iterable[Work],
        max_retry_amount: int = 2,
    ) -> None:
        self._processes = processes
        self._func = function
        self._manager = _Manager()
        self._manager.start()
        self._finish_queue = t.cast(
            'mp.Queue[WorkerException]',
            self._manager.Queue(self._processes + 4),
        )
        self._work_queue: _PrioQueue = self._manager.PrioQueue(  # type: ignore
            max_retry_amount=max_retry_amount,
        )

        self._stop = self._manager.Event()
        self._sleep_time = sleep_time
        self._extra_amount = extra_amount
        self._work_queue.put_all(initial_work)
        self._alive_procs: t.List[mp.Process] = []
        self._producer_lock = self._manager.Lock()
        self._processes_update_lock = mp.Lock()

    def _drain_finish_queue(self) -> None:
        while not self._finish_queue.empty():
            val = self._finish_queue.get()
            if val is not None:
                raise val

    def _worker_function(self) -> None:
        callback = CallbackArguments(
            get_work=self._work_queue.get,
            retry_work=self._work_queue.retry,
            mark_work_as_finished=self._work_queue.mark_as_finished,
        )
        while not self._stop.is_set():
            try:
                self._func(callback)
            except Exception as e:  # pylint: disable=broad-except
                self._finish_queue.put(WorkerException(e, e.__traceback__))
                self._work_queue.notify_work_needed()
                return

    def _populate_workers(self) -> None:
        assert not self._alive_procs

        for _ in range(self._processes):
            proc = _make_process(target=self._worker_function)
            proc.start()
            self._alive_procs.append(proc)

    def _join_all_procs(self) -> None:
        # This is we cleanup all these processes and their associated data in
        # the kernel.
        for proc in self._alive_procs:
            proc.join(0)

    def _add_new_worker(self) -> None:
        proc = _make_process(target=self._worker_function)
        proc.start()
        logger.info('Adding new worker', worker=proc)
        self._alive_procs.append(proc)

    def _stop_workers(self) -> None:
        # We need to set this flag before waking up all the processes, as
        # otherwise they might check the flag before we set it.
        self._stop.set()
        self._work_queue.close()

        self._drain_finish_queue()

        while self._alive_procs:
            self._alive_procs.pop().join()

        self._drain_finish_queue()

    def start(self, producer: t.Callable[[bool], t.Iterable[Work]]) -> None:
        """Start the workers to work on the given work.

        :param producer: The function to call to produce more work.
        :returns: Nothing.
        """
        bonus_round = threading.Event()
        # If this queue has a ``maxsize`` of 0, it will deadlock if the master
        # thread crashes in the bonus round, as the ``put`` will block, and the
        # waiting for ``_stop`` is never done.
        bonus_round_result: 'Queue[bool]' = Queue(self._extra_amount)

        def producer_fun() -> None:
            bonus_done = 0
            while bonus_done != self._extra_amount or not bonus_round.is_set():
                with self._producer_lock:
                    bonus = bonus_round.is_set()
                    final = bonus and (bonus_done + 1 == self._extra_amount)

                    try:
                        new_items = producer(final)
                        produced = self._work_queue.put_all(new_items)
                    except:  # pylint: disable=bare-except; # pragma: no cover
                        logger.warning('Producer crashed!', exc_info=True)
                        if self._stop.wait(self._sleep_time):
                            return
                        continue

                    if bonus:
                        if produced:
                            bonus_done = 0
                            bonus_round.clear()
                        else:
                            bonus_done += 1
                        bonus_round_result.put(produced)

                # This call returns the value of the internal flag
                if self._stop.wait(self._sleep_time):
                    return

        producer_thread = threading.Thread(target=producer_fun)
        producer_thread.start()

        try:
            self._populate_workers()

            self._start_master(bonus_round, bonus_round_result)
        finally:
            try:
                self._stop_workers()
            finally:
                if producer_thread is not None:
                    producer_thread.join()

    def _start_master(
        self, bonus_round: threading.Event, bonus_round_result: 'Queue[bool]'
    ) -> None:
        while True:
            # Wait with a timeout. This reduces the chance that every thread is
            # waiting and we need to start the bonus round, but we do not do it
            # because of some weird timing bug.
            self._work_queue.wait_on_work_needed(30)
            try:
                raise self._finish_queue.get(False)
            except WorkerException as e:
                logger.info(
                    'Got exception from worker',
                    exception=str(type(e.exception))
                )
                if isinstance(e.exception, KillWorkerException):
                    self._add_new_worker()
                else:
                    raise
            except Empty:
                pass

            self._join_all_procs()

            # We make sure that once the queue is empty it will not fill up, as
            # we lock the producer.
            with self._producer_lock:
                # Some workers might still be busy so we need to check that.
                (old_wq_version, queue_empty,
                 amount_waiting) = self._work_queue.get_version()
                logger.info(
                    'Checking if queue is empty',
                    queue_empty=queue_empty,
                    amount_waiting=amount_waiting,
                    amount_processes=self._processes,
                )

                # Every thread is waiting for more work to do, and there is no
                # more work.
                if queue_empty and amount_waiting == self._processes:
                    bonus_round.set()
                else:
                    continue

            logger.info('Starting bonus round')

            # We need to release the ``_new_work`` lock, as otherwise the
            # producer will never run. We do need to set the ``bonus_round``
            # Event while we hold the lock, as otherwise we might get out of
            # sync.
            for bonus_index in range(self._extra_amount):
                logger.info('Doing bonus round', round_number=bonus_index)
                if bonus_round_result.get():
                    logger.info('Got results, so stopping bonus')
                    break
            else:
                # The queue should be not changed, as we indicated that no
                # results were produced.
                logger.info('Bonus round finished, got no work')
                assert self._work_queue.get_version()[0] == old_wq_version
                return
