"""This module provides utilities for timing functions

SPDX-License-Identifier: AGPL-3.0-only
"""
import time
import typing as t
import contextlib
from functools import wraps
from collections import defaultdict

import flask
import structlog
from typing_extensions import Literal

logger = structlog.get_logger()

T_CAL = t.TypeVar('T_CAL', bound=t.Callable)  # pylint: disable=invalid-name
Y_CAL = t.TypeVar('Y_CAL', bound=t.Callable)  # pylint: disable=invalid-name

__all__ = ['timed_code', 'timed_function']


def init_app(app: flask.Flask) -> None:
    """Initialize the app.

    :param app: The flask app to initialize.
    """

    @app.before_request
    def __setup_timers() -> None:
        flask.g.cg_timers_collection = defaultdict(
            lambda: {
                'amount': 0,
                'total_time': 0,
            }
        )

    @app.after_request
    def __after_req(res: flask.Response) -> flask.Response:
        # This can happen when the request fails before the `__setup_timers`
        # method is called
        if not hasattr(flask.g, 'cg_timers_collection'):
            return res

        for key, timer_dict in sorted(flask.g.cg_timers_collection.items()):
            amount = timer_dict['amount']
            total_time = timer_dict['total_time']

            if amount > 0:
                logger.info(
                    'Collected function information',
                    timed_function=key,
                    amount_called=amount,
                    total_call_time=total_time,
                    average_call_time=total_time / amount,
                )
        return res


@contextlib.contextmanager
def timed_code(code_block_name: str, **other_keys: object
               ) -> t.Generator[t.Callable[[], float], None, None]:
    """Measure the time it takes for the code in this context to run.

    :param code_block_name: Name of the measured block, for logging purposes.
    :param **other_keys: Keys to log along with the timing information.
    :returns: A context manager that measures its lifetime.
    """
    start_time = time.time()
    logger.info(
        'Starting timed code block',
        timed_code_block=code_block_name,
        **other_keys
    )
    end_time: t.Optional[float] = None

    try:
        yield lambda: (end_time or time.time()) - start_time
    except:
        exc_info = True
        raise
    else:
        exc_info = False
    finally:
        end_time = time.time()
        logger.info(
            'Finished timed code block',
            timed_code_block=code_block_name,
            exc_info=exc_info,
            exception_occurred=exc_info,
            elapsed_time=end_time - start_time,
            **other_keys,
        )


@t.overload
def timed_function(fun: T_CAL) -> T_CAL:
    ...


@t.overload
def timed_function(*, collect_in_request: Literal[True]
                   ) -> t.Callable[[T_CAL], T_CAL]:
    ...


def timed_function(fun: T_CAL = None, *, collect_in_request: bool = False
                   ) -> t.Union[T_CAL, t.Callable[[Y_CAL], Y_CAL]]:
    """Measure the time it takes for a function to run.

    :param fun: Function to measure the performance of.
    :param collect_in_request: Include the timings in the timing information of
        this request.
    :returns: A function that calls the given function and performs the
        measurement.
    """
    if collect_in_request:

        def __outer(fun: Y_CAL) -> Y_CAL:
            key = fun.__qualname__

            @wraps(fun)
            def _wrapper(*args: object, **kwargs: object) -> object:
                start = time.time()
                try:
                    return fun(*args, **kwargs)
                finally:
                    try:
                        timer_dict = flask.g.cg_timers_collection[key]
                        timer_dict['amount'] += 1
                        timer_dict['total_time'] += time.time() - start
                    except:  # pragma: no cover # pylint: disable=bare-except
                        pass

            return t.cast(Y_CAL, _wrapper)

        return __outer
    else:
        assert fun is not None
        qualname = fun.__qualname__

        @wraps(fun)
        def _wrapper(*args: object, **kwargs: object) -> object:
            with timed_code(qualname):
                return fun(*args, **kwargs)  # type: ignore

        return t.cast(T_CAL, _wrapper)
