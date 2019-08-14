"""This module implements an alternative for ``multiprocessing.pool.Pool``.

In this implementation you can add work while the pool is running.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import threading
import traceback
import collections
import multiprocessing as mp
from queue import Empty, Queue
from types import TracebackType
from multiprocessing import managers

import structlog

logger = structlog.get_logger()

Work = t.NamedTuple('Work', [('result_id', int), ('student_id', int)])


def _make_process(*, target: t.Callable[[], object]) -> mp.Process:
    return mp.Process(target=target)


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
    def __init__(self) -> None:
        self.queue: t.Deque[Work] = collections.deque()
        self.newest: t.Dict[int, int] = {}
        self.mutex = mp.Lock()

        self.all_results: t.Set[int] = set()

        self._version = 0
        self._amount_waiting = 0
        self._closed = False
        self._new_work = mp.Condition(self.mutex)
        self._work_needed = mp.Semaphore(0)

    def wait_on_work_needed(self) -> None:
        self._work_needed.acquire()

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
                if work.result_id in self.all_results:
                    continue

                added_amount += 1
                self.all_results.add(work.result_id)
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

    def get(self) -> t.Optional[Work]:
        """Try to get more work.

        :returns: More work, or ``None`` if the queue is closed while getting
            more work.


        .. warning:: This function blocks if there is no more work.
        """
        with self.mutex:
            while not self._closed:
                work = self._peek()
                if work is not None:
                    # Remove item from the queue
                    self.queue.popleft()
                    del self.newest[work.student_id]
                    self._inc_version()

                    return work

                self._amount_waiting += 1
                self._work_needed.release()
                self._new_work.wait()
                self._amount_waiting -= 1

        return None


class _Manager(managers.SyncManager):
    pass


_Manager.register('PrioQueue', _PrioQueue)


class WorkerPool:
    """Class that implements a worker pool in which you can add more work while
    it is busy.
    """

    def __init__(
        self, processes: int, function: t.Callable[[Work], None],
        sleep_time: float, extra_amount: int, initial_work: t.Iterable[Work]
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
        )

        self._stop = self._manager.Event()
        self._sleep_time = sleep_time
        self._extra_amount = extra_amount
        self._work_queue.put_all(initial_work)
        self._alive_procs: t.List[mp.Process] = []
        self._producer_lock = self._manager.Lock()

    def _drain_finish_queue(self) -> None:
        while not self._finish_queue.empty():
            val = self._finish_queue.get()
            if val is not None:
                raise val

    def _worker_function(self) -> None:
        work = None

        while not self._stop.is_set():
            work = self._work_queue.get()
            if work is None:
                continue

            try:
                self._func(work)
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
            self._work_queue.wait_on_work_needed()
            try:
                raise self._finish_queue.get(False)
            except Empty:
                pass

            # We make sure that once the queue is empty it will not fill up, as
            # we lock the producer.
            with self._producer_lock:
                # Some workers might still be busy so we need to check that.
                (old_wq_version, queue_empty,
                 amount_waiting) = self._work_queue.get_version()

                # Every thread is waiting for more work to do, and there is no
                # more work.
                if queue_empty and amount_waiting == self._processes:
                    bonus_round.set()
                else:
                    continue

            # We need to release the ``_new_work`` lock, as otherwise the
            # producer will never run. We do need to set the ``bonus_round``
            # Event while we hold the lock, as otherwise we might get out of
            # sync.
            for _ in range(self._extra_amount):
                if bonus_round_result.get():
                    break
            else:
                # The queue should be not changed, as we indicated that no
                # results were produced.
                assert self._work_queue.get_version()[0] == old_wq_version
                return
