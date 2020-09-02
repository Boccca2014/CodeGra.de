"""This module contains all code needed for logging and its configuration
within CodeGrade.

SPDX-License-Identifier: AGPL-3.0-only
"""
import sys
import time
import uuid
import typing as t
import logging as system_logging
import functools
import threading
import traceback
import contextlib
import multiprocessing

import flask
import structlog
import sentry_sdk
import sentry_sdk.utils
import flask_jwt_extended as flask_jwt
from flask import g, request
from sentry_sdk.hub import Hub
from mypy_extensions import KwArg
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from cg_dt_utils import DatetimeWithTimezone

logger = structlog.get_logger()

LogCallback = t.Callable[['PrintLogger', str, t.Dict[str, object]], None]
_logger_callbacks: t.List[LogCallback] = []

_T = t.TypeVar('_T')


def _sentry_before_request() -> None:
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag('version', flask.current_app.config.get('VERSION'))
        scope.set_tag(
            'external_url', flask.current_app.config.get('EXTERNAL_URL')
        )

        current_user = flask_jwt.current_user
        if current_user:
            scope.user = {
                'username': current_user.username,
                'id': current_user.id,
            }


def _sentry_before_send(
    event: t.Dict[str, object],
    _hint: object,
) -> t.Dict[str, t.Any]:
    sentry_request = event.get('request', None)
    if (
        isinstance(sentry_request, dict) and
        isinstance(sentry_request.get('data'), dict)
    ):
        del sentry_request['data']

    return event


def _create_logger(set_user: bool) -> None:
    g.request_start_time = DatetimeWithTimezone.utcnow()

    g.request_id = uuid.uuid4()
    log = logger.new(
        request_id=str(g.request_id),
        path=request.path,
        view=getattr(request.url_rule, 'rule', None),
        base_url=flask.current_app.config.get('EXTERNAL_URL'),
    )

    if set_user:
        flask_jwt.verify_jwt_in_request_optional()
        log.bind(
            current_user=flask_jwt.current_user and
            flask_jwt.current_user.username
        )

    func = log.info
    try:
        start = DatetimeWithTimezone.utcfromtimestamp(
            float(request.headers['X-Request-Start-Time'])
        )
        wait_time = (g.request_start_time - start).total_seconds()
        if wait_time > 5:
            func = log.error
        if wait_time > 1:
            func = log.warning
        log.bind(time_spend_in_queue=wait_time)
    except:  # pylint: disable=bare-except
        pass

    try:
        func(
            "Request started",
            host=request.host_url,
            method=request.method,
            query_args={
                k: '<PASSWORD>' if k == 'password' else v
                for k, v in request.args.items()
            },
        )
    finally:
        log.try_unbind('time_spend_in_queue')


def _after_request(res: _T) -> _T:
    queries_amount: int = getattr(g, 'queries_amount', 0)
    queries_total_duration: int = getattr(g, 'queries_total_duration', 0)
    queries_max_duration: int = getattr(g, 'queries_max_duration', 0) or 0
    log_msg = (
        logger.info if queries_max_duration < 0.5 and queries_amount < 20 else
        logger.warning
    )

    cache_hits: int = getattr(g, 'cache_hits', 0)
    cache_misses: int = getattr(g, 'cache_misses', 0)

    end_time = DatetimeWithTimezone.utcnow()
    start_time = getattr(g, 'request_start_time', end_time)
    log_msg(
        'Request finished',
        request_time=(end_time - start_time).total_seconds(),
        status_code=getattr(res, 'status_code', None),
        queries_amount=queries_amount,
        queries_total_duration=queries_total_duration,
        queries_max_duration=queries_max_duration,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )
    return res


def _find_first_app_frame_and_name() -> t.Tuple[object, str]:
    """
    Copied from structlog, MIT License
    """
    ignores = ['structlog', 'cg_logger']
    f = sys._getframe()  # pylint: disable=protected-access
    name = f.f_globals.get('__name__') or '?'
    while any(tuple(name.startswith(i) for i in ignores)):
        if f.f_back is None:
            name = '?'
            break
        f = f.f_back
        name = f.f_globals.get('__name__') or '?'
    return f, name


class PrintLogger(structlog.PrintLogger):  # type: ignore
    """This class implements a simple logger that prints its message to stdout.

    This logger also tries to add which methods called the logger.
    """

    def __init__(self) -> None:
        super().__init__()
        self.name = _find_first_app_frame_and_name()[1]
        self._in_err = False

    def msg(self, message: object) -> None:
        try:
            super().msg(message)
        except:  # pylint: disable=bare-except
            if not self._in_err:
                self._in_err = True
                logger.error(
                    'Something when wrong during logging', exc_info=True
                )
                self._in_err = False

    log = debug = info = warn = warning = msg
    fatal = failure = err = error = critical = exception = msg


def init_app(app: flask.Flask, set_user: bool = True) -> None:
    """Initialize the app.

    :param app: The flask app to initialize.
    """
    sentry_dsn = app.config.get('SENTRY_DSN')
    configure_logging(
        getattr(app, 'debug', False),
        getattr(app, 'testing', False),
        sentry_dsn=sentry_dsn,
        cur_commit=app.config.get('CUR_COMMIT'),
    )

    if sentry_dsn:
        app.before_request(_sentry_before_request)

    app.before_request(functools.partial(_create_logger, set_user=set_user))
    app.after_request(_after_request)


class LoggerCallback:
    """A logger callback class.
    """

    def __init__(self, fun: LogCallback) -> None:
        self.fun = fun

    def disable(self) -> None:
        _logger_callbacks.remove(self.fun)


def logger_callback(fun: LogCallback) -> LoggerCallback:
    """Add a function as a logger callback.
    """
    assert fun not in _logger_callbacks
    _logger_callbacks.append(fun)
    return LoggerCallback(fun)


def _add_log_as_breadcrumb(
    print_logger: PrintLogger, _: object, event_dict: dict
) -> dict:
    Hub.current.add_breadcrumb({
        'ty': 'log',
        'level': event_dict.get('level', 'unknown'),
        'category': print_logger.name,
        'message': event_dict.get('event'),
        'timestamp': time.time(),
        'data': event_dict,
    })
    return event_dict


def _maybe_add_stacktrace(_: object, __: object, event_dict: dict) -> dict:
    if event_dict.pop('with_stacktrace', None):
        event_dict['stacktrace'] = traceback.format_stack()
    return event_dict


def _add_thread_name(_: object, __: object, event_dict: dict) -> dict:
    event_dict['thread_id'] = threading.current_thread().name
    event_dict['process_id'] = multiprocessing.current_process().name
    return event_dict


def _add_log_level(_: str, method_name: str, event_dict: t.Dict) -> t.Dict:
    """
    Add the log level to the event dict.
    """
    if method_name == "warn":
        # The stdlib has an alias
        method_name = "warning"

    event_dict['level'] = event_dict.pop('__level__', method_name)
    return event_dict


def _maybe_report_error_to_sentry(
    print_logger: object, method: str, event_dict: t.Dict[str, t.Any]
) -> t.Dict[str, t.Any]:
    if event_dict.get('report_to_sentry'):
        report_error_to_sentry(print_logger, method, event_dict, force=True)

        event_dict['in_sentry'] = True

    return event_dict


def report_error_to_sentry(
    _: object,
    __: str,
    event_dict: t.Dict[str, t.Any],
    *,
    force: bool = False,
) -> None:
    """Report the given event to sentry if it is an error or if ``force`` is
        true.

    You can use this method by adding it as logger callback if you want to
    automatically report every error to sentry.
    """
    if event_dict.get('in_sentry'):  # pragma: no cover
        return
    elif not force and event_dict.get('level') not in {'error', 'err'}:
        return

    try:
        hub = Hub.current
        if (
            hub.get_integration(FlaskIntegration) is not None and
            hub.client is not None
        ):  # pragma: no cover
            exc_info = sys.exc_info()
            if None not in exc_info:
                event, hint = sentry_sdk.utils.event_from_exception(
                    exc_info, client_options=hub.client.options
                )
                hub.capture_event(event, hint=hint)
            else:
                hub.capture_message(event_dict.get('event', '??'), 'error')

    except:  # pylint: disable=bare-except
        logger.info('Could not report error to sentry', exc_info=True)


def _call_log_callbacks(
    print_logger: PrintLogger,
    method_name: str,
    event_dict: t.Dict[str, object],
) -> t.Dict[str, object]:
    for callback in _logger_callbacks:
        try:
            callback(print_logger, method_name, event_dict)
        except:  # pylint: disable=bare-except
            pass

    return event_dict


def configure_logging(
    debug: bool, testing: bool, sentry_dsn: t.Optional[str],
    cur_commit: t.Optional[str]
) -> None:
    """Configure the structlog logger.

    :param debug: Are we in a debug environment.
    :param testing: Are we in a testing environment.
    """

    json_renderer = structlog.processors.JSONRenderer()

    processors = [
        structlog.stdlib.add_logger_name,
        _add_log_level,
        _add_thread_name,
        _maybe_add_stacktrace,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _add_log_as_breadcrumb,
        _maybe_report_error_to_sentry,
        _call_log_callbacks,
        json_renderer,
    ]
    if debug and not testing:
        processors[-1] = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=processors,
        context_class=structlog.threadlocal.wrap_dict(dict),
        logger_factory=PrintLogger,
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    system_logging.basicConfig(
        format='%(message)s',
        stream=sys.stdout,
    )
    system_logging.getLogger('psef').setLevel(system_logging.DEBUG)
    system_logging.getLogger('werkzeug').setLevel(system_logging.ERROR)
    # Let the celery logger shut up
    # system_logging.getLogger('celery').propagate = False

    if sentry_dsn is not None:
        logger.info('Setting up sentry')
        release = None
        if cur_commit is not None:
            release = f'CodeGra.de@{cur_commit}'

        sentry_sdk.init(
            release=release,
            dsn=sentry_dsn,
            integrations=[
                FlaskIntegration(transaction_style='url'),
                SqlalchemyIntegration(),
                CeleryIntegration(),
            ],
            before_send=_sentry_before_send,
        )


@contextlib.contextmanager
def bound_to_logger(**vals: object
                    ) -> t.Generator[t.Callable[[KwArg()], None], None, None]:
    """Bind values to logger for a certain block.

    :param **vals: The parameters you want to bind to the logger in this block.

    :yields: A method that you can the same way you called this method to bind
             more items to the logger that will also be dropped as soon as this
             context manager exists.
    """
    bound = list(vals.keys())
    logger.bind(**vals)
    # Remove reference to ``vals``
    del vals

    def bind_extra(**to_bind: object) -> None:
        bound.extend(to_bind.keys())
        logger.bind(**to_bind)

    try:
        yield bind_extra
    finally:
        logger.try_unbind(*bound)
