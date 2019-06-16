"""
This module implements generic helpers and convenience functions.

SPDX-License-Identifier: AGPL-3.0-only
"""
import re
import abc
import enum
import time
import typing as t
import datetime
import threading
import contextlib
import subprocess
import urllib.parse
import multiprocessing
from functools import wraps

import flask
import requests
import structlog
import mypy_extensions
from flask import g, request
from typing_extensions import Protocol
from werkzeug.datastructures import FileStorage
from sqlalchemy.sql.expression import or_

import psef
from cg_json import (
    JSONResponse, ExtendedJSONResponse, jsonify, extended_jsonify
)
from cg_timers import timed_code
from cg_sqlalchemy_helpers.types import Base, MyQuery, DbColumn

from . import features, validate
from .. import errors, current_tester

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    import psef.archive
    from ..models import Base  # pylint: disable=unused-import
    import werkzeug  # pylint: disable=unused-import

logger = structlog.get_logger()

#: Type vars
T = t.TypeVar('T')
T_STOP_THREAD = t.TypeVar('T_STOP_THREAD', bound='StoppableThread')
T_CAL = t.TypeVar('T_CAL', bound=t.Callable)
TT = t.TypeVar('TT')
TTT = t.TypeVar('TTT', bound='IsInstanceType')
ZZ = t.TypeVar('ZZ')
Z = t.TypeVar('Z', bound='Comparable')
Y = t.TypeVar('Y', bound='Base')
T_Type = t.TypeVar('T_Type', bound=t.Type)  # pylint: disable=invalid-name
T_TypedDict = t.TypeVar(  # pylint: disable=invalid-name
    'T_TypedDict',
    bound=t.Mapping,
)

IsInstanceType = t.Union[t.Type, t.Tuple[t.Type, ...]]  # pylint: disable=invalid-name


class MissingType(enum.Enum):
    token = 0


MISSING: MissingType = MissingType.token


def init_app(app: 'psef.Flask') -> None:
    """Initialize the app.

    :param app: The flask app to initialize.
    """

    @app.before_request
    def __set_warnings() -> None:
        g.request_warnings = []

    @app.after_request
    def __maybe_add_warning(res: flask.Response) -> flask.Response:
        for warning in getattr(g, 'request_warnings', []):
            logger.info('Added warning to response', warning=warning)
            res.headers.add('Warning', warning)
        return res


def add_warning(warning: str, code: psef.exceptions.APIWarnings) -> None:
    g.request_warnings.append(psef.errors.make_warning(warning, code))


def add_deprecate_warning(warning: str) -> None:
    """Add a deprecation warning to the request.

    :param warning: Explanation about what api is deprecated.
    :returns: Nothing
    """
    logger.info(
        'A deprecated api was used',
        deprecation_warning=True,
        warning_msg=warning,
    )
    g.request_warnings.append(
        psef.errors.make_warning(
            f'This API is deprecated: {warning}',
            psef.exceptions.APIWarnings.DEPRECATED,
        )
    )


class Comparable(Protocol):  # pragma: no cover
    """A protocol that for comparable variables.

    To satisfy this protocol a object should implement the ``__eq__``,
    ``__lt__``, ``__gt__``, ``__le__`` and``__ge__`` magic functions.
    """

    @abc.abstractmethod
    def __eq__(self, other: t.Any) -> bool:
        ...  # pylint: disable=W0104

    @abc.abstractmethod
    def __lt__(self: Z, other: Z) -> bool:
        ...  # pylint: disable=W0104

    def __gt__(self: Z, other: Z) -> bool:
        return (not self < other) and self != other

    def __le__(self: Z, other: Z) -> bool:
        return self < other or self == other

    def __ge__(self: Z, other: Z) -> bool:
        return not (self < other)  # pylint: disable=superfluous-parens


def get_all_subclasses(cls: T_Type) -> t.Iterable[T_Type]:
    """Returns all subclasses of the given class.

    Stolen from:
    https://stackoverflow.com/questions/3862310/how-can-i-find-all-subclasses-of-a-class-given-its-name

    :param cls: The parent class
    :returns: A list of all subclasses
    """
    all_subclasses = []

    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))

    return all_subclasses


def escape_like(unescaped_like: str) -> str:
    r"""Escape a string used for the LIKE clause by escaping all wildcards.

    .. note::

      The escape characters are "%", "_" and "\". They are escaped by placing a
      "\" before them.

    >>> escape_like('hello')
    'hello'
    >>> escape_like('This is % a _ string\\%')
    'This is \\% a \\_ string\\\\\\%'
    >>> escape_like('%')
    '\\%'

    :param unescaped_like: The string to escape
    :returns: The same string but escaped
    """
    return re.sub(r'(%|_|\\)', r'\\\1', unescaped_like)


def between(min_bound: Z, item: Z, max_bound: Z) -> Z:
    """Make sure ``item`` is between two bounds.

    >>> between(0, 5, 10)
    5
    >>> between(0, -1, 10)
    0
    >>> between(0, 11, 10)
    10
    >>> between(10, 5, 0)
    Traceback (most recent call last):
    ...
    ValueError: `min_bound` cannot be higher than `max_bound`

    .. note::

        ``min_bound`` cannot be larger than ``max_bound``. They can be equal.

    :param min_bound: The minimum this function should return
    :param max_bound: The maximum this function should return
    :param item: The item to check
    :returns: ``item`` if it is between ``min_bound`` and ``max_bound``,
        otherwise the bound is returned that is closest to the item.
    """
    if min_bound > max_bound:
        raise ValueError('`min_bound` cannot be higher than `max_bound`')

    if item <= min_bound:
        return min_bound
    elif item >= max_bound:
        return max_bound

    return item


def get_request_start_time() -> datetime.datetime:
    """Return the start time of the current request.

    :returns: The time as returned by the python time module.
    :rtype: float
    """
    return flask.g.request_start_time


_JSONValue = t.Union[str, int, float, bool, None, t.Dict[str, t.Any],  # pylint: disable=invalid-name
                     t.List[t.Any]]
JSONType = t.Union[t.Dict[str, _JSONValue], t.List[_JSONValue], _JSONValue]  # pylint: disable=invalid-name


class EmptyResponse:
    """An empty response.

    This is a subtype of :py:class:`werkzeug.wrappers.Response` where the body
    is empty and the status code is always 204.

    .. warning::

        This class is only used for type hinting and is never actually used! It
        does not contain any valid data!
    """

    def __init__(self) -> None:  # pragma: no cover
        raise NotImplementedError("Do not use this class as actual data")


def get_in_or_error(
    model: t.Type[Y],
    in_column: DbColumn[T],
    in_values: t.List[T],
    options: t.Optional[t.List[t.Any]] = None,
) -> t.List[Y]:
    """Get object by doing an ``IN`` query.

    This method protects against empty ``in_values``, and will return an empty
    list in that case. If not all items from the ``in_values`` this function
    will raise an exception.

    :param model: The objects to get.
    :param in_column: The column of the object to perform the in on.
    :param in_values: The values used for the ``IN`` clause. This may be an
        empty sequence, which is handled without doing a query.
    :param options: A list of options to give to the executed query. This can
        be used to undefer or eagerly load some columns or relations.
    :returns: A list of objects with the same length as ``in_values``.

    :raises APIException: If on of the items in ``in_values`` was not found.
    """
    if not in_values:
        return []

    query = psef.models.db.session.query(model).filter(
        in_column.in_(in_values)
    )

    if options is not None:
        query = query.options(*options)

    res = query.all()
    if len(res) != len(in_values):
        raise psef.errors.APIException(
            f'Not all requested {model.__name__.lower()} could be found', (
                f'Out of the {len(in_values)} requested only {len(res)} were'
                ' found'
            ), psef.errors.APICodes.OBJECT_ID_NOT_FOUND, 404
        )
    return res


def _filter_or_404(
    model: t.Type[Y],
    get_all: bool,
    criteria: t.Tuple,
    also_error: t.Optional[t.Callable[[Y], bool]],
) -> t.Union[Y, t.Sequence[Y]]:
    """Get the specified object by filtering or raise an exception.

    :param get_all: Get all objects if ``True`` else get a single one.
    :param model: The object to get.
    :param criteria: The criteria to filter with.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    crit_str = ' AND '.join(str(crit) for crit in criteria)
    query = model.query.filter(*criteria)  # type: ignore
    obj = query.all() if get_all else query.one_or_none()
    if not obj or (also_error is not None and also_error(obj)):
        raise psef.errors.APIException(
            f'The requested {model.__name__.lower()} was not found',
            f'There is no "{model.__name__}" when filtering with {crit_str}',
            psef.errors.APICodes.OBJECT_ID_NOT_FOUND, 404
        )
    return obj


def filter_all_or_404(model: t.Type[Y], *criteria: t.Any) -> t.Sequence[Y]:
    """Get all objects of the specified model filtered by the specified
    criteria.

    .. note::
        ``Y`` is bound to :py:class:`.Base`, so it should be a
        SQLAlchemy model.

    :param model: The object to get.
    :param criteria: The criteria to filter with.
    :returns: The requested objects.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    return t.cast(t.Sequence[Y], _filter_or_404(model, True, criteria, None))


def filter_single_or_404(
    model: t.Type[Y],
    *criteria: t.Any,
    also_error: t.Optional[t.Callable[[Y], bool]] = None,
) -> Y:
    """Get a single object of the specified model by filtering or raise an
    exception.

    .. note::
        ``Y`` is bound to :py:class:`.Base`, so it should be a
        SQLAlchemy model.

    :param model: The object to get.
    :param criteria: The criteria to filter with.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    return t.cast(Y, _filter_or_404(model, False, criteria, also_error))


def get_or_404(
    model: t.Type[Y],
    object_id: t.Any,
    options: t.Optional[t.List[t.Any]] = None,
    also_error: t.Optional[t.Callable[[Y], bool]] = None,
) -> Y:
    """Get the specified object by primary key or raise an exception.

    .. note::
        ``Y`` is bound to :py:class:`.Base`, so it should be a
        SQLAlchemy model.

    :param model: The object to get.
    :param object_id: The primary key identifier for the given object.
    :param options: A list of options to give to the executed query. This can
        be used to undefer or eagerly load some columns or relations.
    :param also_error: If this function when called with the found object
        returns ``True`` generate the 404 error even though the object was
        found.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    query = psef.models.db.session.query(model)
    if options is not None:
        query = query.options(*options)
    obj: t.Optional[Y] = query.get(object_id)

    if obj is None or (also_error is not None and also_error(obj)):
        raise psef.errors.APIException(
            f'The requested "{model.__name__}" was not found',
            f'There is no "{model.__name__}" with primary key {object_id}',
            psef.errors.APICodes.OBJECT_ID_NOT_FOUND, 404
        )
    return obj


def filter_users_by_name(
    query: str, base: 'MyQuery[psef.models.User]', *, limit: int = 25
) -> 'MyQuery[psef.models.User]':
    """Find users from the given base query using the given query string.

    :param query: The string to filter usernames and names of users with.
    :param base: The query to filter.
    :param limit: The amount of users to limit the search too.
    :returns: A new query with the users filtered.
    """
    if len(re.sub(r'\s', '', query)) < 3:
        raise psef.errors.APIException(
            'The search string should be at least 3 chars',
            f'The search string "{query}" is not 3 chars or longer.',
            psef.errors.APICodes.INVALID_PARAM, 400
        )

    likes = [
        t.cast(t.Any, col).ilike(
            '%{}%'.format(
                escape_like(query).replace(' ', '%'),
            )
        ) for col in [psef.models.User.name, psef.models.User.username]
    ]

    return base.filter(or_(*likes)).order_by(
        t.cast(DbColumn[str], psef.models.User.name)
    ).limit(limit)


def coerce_json_value_to_typeddict(
    obj: JSONType, typeddict: t.Type[T_TypedDict]
) -> T_TypedDict:
    """Coerce a json object to a typed dict.

    .. warning::

        All types of the typed dict must be types that can be used with
        :func:`isinstance`.

    .. note::

        The original object is returned, this only checks if all values are
        valid.

    :param obj: The object to coerce:
    :param typeddict: The typeddict type that ``obj`` should be coerced to.
    :returns: The given value ``obj``.
    """
    mapping = ensure_json_dict(obj)
    annots = list(typeddict.__annotations__.items())
    assert all(
        isinstance(t, type) for _, t in annots
    ), "This function only supports checking for basic types"
    ensure_keys_in_dict(mapping, annots)
    return t.cast(T_TypedDict, mapping)


def ensure_on_test_server() -> None:
    assert not flask.has_app_context()
    assert not flask.has_request_context()
    assert current_tester._get_current_object() is not None


def _get_type_name(typ: t.Union[t.Type, t.Tuple[t.Type, ...]]) -> str:
    if isinstance(typ, tuple):
        return ', '.join(ty.__name__ for ty in typ)
    else:
        return typ.__name__


def get_key_from_dict(
    mapping: t.Mapping[T, object], key: T, default: TT
) -> TT:
    """Get a key from a mapping of a specific type.

    :param mapping: The mapping to get the key from.
    :param key: The key in the mapping.
    :param default: The default value used if the key is not in the dict.
    :returns: The found value of the given default.
    :raises APIException: If the found value is of a different type than the
        given default.
    """
    val = mapping.get(key, default)
    if not isinstance(val, type(default)):
        raise psef.errors.APIException(
            f'The given object contains the wrong type for the key "{key}"', (
                f'A value of type "{_get_type_name(type(default))} is'
                f' required, but "{val}" was given, which is a'
                f' "{_get_type_name(type(val))}"'
            ), psef.errors.APICodes.MISSING_REQUIRED_PARAM, 400
        )
    return val


@contextlib.contextmanager
def get_from_map_transaction(
    mapping: t.Mapping[T, TT],
    *,
    ensure_empty: bool = False,
) -> t.Generator[t.Tuple[t.Callable[[T, t.Type[TTT]], TTT], t.
                         Callable[[T, t.Type[TTT], ZZ], t.
                                  Union[TTT, ZZ]]], None, None]:
    all_keys_requested = []
    keys = []

    def fun1(key: T, typ: t.Type[TTT]) -> TTT:
        all_keys_requested.append(key)
        keys.append((key, typ))
        return t.cast(TTT, mapping.get(key, MISSING))

    def fun2(key: T, typ: t.Type[TTT], default: ZZ) -> t.Union[TTT, ZZ]:
        if key not in mapping:
            all_keys_requested.append(key)
            return default
        return fun1(key, typ)

    try:
        yield fun1, fun2
    finally:
        ensure_keys_in_dict(mapping, keys)
        if ensure_empty and len(all_keys_requested) < len(mapping):
            key_lookup = set(all_keys_requested)
            raise psef.errors.APIException(
                'Extra keys in the object found', (
                    'The object could only contain "{}", but is also contained'
                    ' "{}".'
                ).format(
                    ', '.join(map(str, all_keys_requested)),
                    ', '.join(
                        str(m) for m in mapping.keys() if m not in key_lookup
                    ),
                ), psef.errors.APICodes.INVALID_PARAM, 400
            )


def ensure_keys_in_dict(
    mapping: t.Mapping[T, object], keys: t.Sequence[t.Tuple[T, IsInstanceType]]
) -> None:
    """Ensure that the given keys are in the given mapping.

    :param mapping: The mapping to check.
    :param keys: The keys that should be in the mapping. If key is a tuple it
        is of the form (key, type) where ``mappping[key]`` has to be of type
        ``type``.
    :return: Nothing.

    :raises psef.errors.APIException: If a key from ``keys`` is missing in
        ``mapping`` (MISSING_REQUIRED_PARAM)
    """

    missing: t.List[t.Union[T, str]] = []
    type_wrong = False
    for key, check_type in keys:
        if key not in mapping:
            missing.append(key)
        elif (not isinstance(mapping[key], check_type)
              ) or (check_type == int and isinstance(mapping[key], bool)):
            missing.append(
                f'{str(key)} was of wrong type'
                f' (should be a "{_get_type_name(check_type)}"'
                f', was a "{type(mapping[key]).__name__}")'
            )
            type_wrong = True
    if missing:
        msg = 'The given object does not contain all required keys'
        key_type = ', '.join(
            f"\'{k[0]}\': {_get_type_name(k[1])}" for k in keys
        )
        raise psef.errors.APIException(
            msg + (' or the type was wrong' if type_wrong else ''),
            '"{}" is missing required keys "{}" of all required keys "{}{}{}"'.
            format(
                mapping, ', '.join(str(m) for m in missing), '{', key_type, '}'
            ), psef.errors.APICodes.MISSING_REQUIRED_PARAM, 400
        )


def get_json_dict_from_request(
    replace_log: t.Optional[t.Callable[[str, object], object]] = None,
    log_object: bool = True,
) -> t.Dict[str, JSONType]:
    """Get the JSON dict from this request.

    :param replace_log: A function that replaces options in the log.
    :returns: The JSON found in the request if it is a dictionary.

    :raises psef.errors.APIException: If the found JSON is not a dictionary.
        (INVALID_PARAM)
    """
    return ensure_json_dict(request.get_json(), replace_log, log_object)


def ensure_json_dict(
    json_value: JSONType,
    replace_log: t.Optional[t.Callable[[str, object], object]] = None,
    log_object: bool = True,
) -> t.Dict[str, JSONType]:
    """Make sure that the given json is a JSON dictionary

    :param json_value: The input json that should be checked.
    :param replace_log: A function that replaces options in the log.
    :returns: Exactly the same JSON if it is in fact a dictionary.

    :raises psef.errors.APIException: If the given JSON is not a dictionary.
        (INVALID_PARAM)
    """
    if isinstance(json_value, t.Dict):
        if log_object:
            to_log = json_value
            if replace_log is not None:
                to_log = {k: replace_log(k, v) for k, v in json_value.items()}
            logger.info('JSON request processed', request_data=to_log)

        return json_value
    raise psef.errors.APIException(
        'The given JSON is not a object as is required',
        f'"{json_value}" is not a object',
        psef.errors.APICodes.INVALID_PARAM,
        400,
    )


def make_empty_response() -> EmptyResponse:
    """Create an empty response.

    :returns: A empty response with status code 204
    """
    response = flask.make_response('')
    response.status_code = 204

    return response


def human_readable_size(size: 'psef.archive.FileSize') -> str:
    """Get a human readable size.

    >>> human_readable_size(512)
    '512B'
    >>> human_readable_size(1024)
    '1KB'
    >>> human_readable_size(2.4 * 2 ** 20)
    '2.40MB'
    >>> human_readable_size(2.4444444 * 2 ** 20)
    '2.44MB'

    :param size: The size in bytes.
    :returns: A string that is the amount of bytes which is human readable.
    """
    size_f: float = size

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_f < 1024.0:
            break
        size_f /= 1024.0

    if int(size_f) == size_f:
        return f"{int(size_f)}{unit}"
    return f"{size_f:.2f}{unit}"


def raise_file_too_big_exception(
    max_size: 'psef.archive.FileSize', single_file: bool = False
) -> mypy_extensions.NoReturn:
    """Get an exception that should be thrown when uploade file is too big.

    :param max_size: The maximum size that was overwritten.
    :returns: A exception that should be thrown when file is too big.
    """
    if single_file:
        msg = (
            f'The size of a single file is larger than the maximum, which '
            f'is {human_readable_size(psef.app.max_single_file_size)}.'
        )
    else:
        msg = (
            f'The size of the uploaded files is larger than the maximum. '
            f'The maximum is (extracted) size is '
            f'{human_readable_size(max_size)}.'
        )
    raise psef.errors.APIException(
        msg, 'Request is bigger than maximum upload size of max_size bytes.',
        psef.errors.APICodes.REQUEST_TOO_LARGE, 400
    )


def callback_after_this_request(
    fun: t.Callable[[], object],
) -> t.Callable[[T], T]:
    """Execute a callback after this request without changing the response.

    :param fun: The callback to execute after the current request.
    :returns: The function that will execute after this request that does that
        the response as argument, so this function wraps your given callback.
    """

    @flask.after_this_request
    def after(res: flask.Response) -> flask.Response:
        """The entire callback that is executed at the end of the request.
        """
        if res.status_code < 400:
            fun()
        return res

    return after


def get_class_by_name(superclass: T_Type, name: str) -> T_Type:
    """Get a class with given name

    :param superclass: A superclass of the class found
    :param name: The name of the class wanted.
    :returns: The class with the attribute `__name__` equal to `name`. If
        there are multiple classes with the name `name` the result can be any
        one of these classes.
    :raises ValueError: If the class with the specified name is not found.
    """
    for subcls in get_all_subclasses(superclass):
        if subcls.__name__ == name:
            return subcls
    raise ValueError('No class with name {} found.'.format(name))


def request_arg_true(arg_name: str) -> bool:
    """Check if a request arg was set to a 'truthy' value.

    :param arg_name: The name of the argument to check.
    :returns: ``True`` if and only iff the requested get parameter ``arg_name``
        is present and it value equals (case insensitive) ``'true'``, ``'1'``,
        or ``''`` (empty string).
    """
    return flask.request.args.get(arg_name,
                                  'false').lower() in {'true', '1', ''}


def extended_requested() -> bool:
    """Check if a extended JSON serialization was requested.

    :returns: The return value of :func:`.request_arg_true` called with
        ``'extended'`` as argument.
    """
    return request_arg_true('extended')


@contextlib.contextmanager
def defer(function: t.Callable[[], object]) -> t.Generator[None, None, None]:
    """Defer a function call to the end of the context manager.

    :param: The function to call.
    :returns: A context manager that can be used to execute the given function
        at the end of the block.
    """
    try:
        yield
    finally:
        function()


class StoppableThread(abc.ABC):
    @abc.abstractmethod
    def start(self: T_STOP_THREAD) -> T_STOP_THREAD:
        raise NotImplementedError

    @abc.abstractmethod
    def cancel(self) -> None:
        raise NotImplementedError

    def __exit__(
        self, exc_type: object, exc_value: object, traceback: object
    ) -> None:
        self.cancel()

    def __enter__(self: T_STOP_THREAD) -> T_STOP_THREAD:
        return self.start()


class RepeatedTimer(StoppableThread):
    """Call a function repeatedly in a separate thread.

    .. warning::

        This class doesn't work when threads don't work, which is the case when
        using it in a flask context.
    """

    def __init__(
        self,
        interval: int,
        function: t.Callable[[], None],
        *,
        cleanup: t.Callable[[], None] = lambda: None,
        setup: t.Callable[[], None] = lambda: None,
        use_process: bool = False,
        time_code: bool = True,
    ) -> None:
        super().__init__()
        self.__interval = interval
        self.__function_name = function.__qualname__

        def fun() -> None:
            try:
                if not time_code:
                    function()
                    return

                with timed_code(
                    'repeated_function', function=self.__function_name
                ):
                    function()
            except:
                pass

        get_event = multiprocessing.Event

        self.__function = fun

        self.__finish = get_event()
        self.__finished = get_event()
        self.__started = get_event()

        self.__cleanup = cleanup
        self.__use_process = use_process
        self.__setup = setup
        self.__background: t.Union[None, threading.Thread, multiprocessing.
                                   Process]

    def cancel(self) -> None:
        if not self.__finish.is_set():
            assert self.__background
            self.__finish.set()
            self.__background.join()
            self.__finished.wait()

    def start(self) -> 'RepeatedTimer':
        logger.info('Starting repeating timer', function=self.__function_name)
        self.__finish.clear()
        logger.info('Start repeating timer', function=self.__function_name)
        self.__started.clear()

        def fun() -> None:
            self.__started.set()
            logger.info(
                'Started repeating timer', function=self.__function_name
            )
            self.__setup()
            try:
                while True:
                    self.__function()
                    if self.__finish.wait(self.__interval):
                        break
                self.__function()
            finally:
                try:
                    self.__cleanup()
                finally:
                    self.__finished.set()

        back: t.Union[threading.Thread, multiprocessing.Process]
        if self.__use_process:
            back = multiprocessing.Process(target=fun)
        else:
            back = threading.Thread(target=fun)

        back.start()
        self.__background = back
        self.__started.wait()

        return self


def call_external(
    call_args: t.List[str],
    input_callback: t.Callable[[str], bool] = lambda _: False
) -> t.Tuple[bool, str]:
    """Safely call an external program without any exceptions.

    .. note:: This function should not be used when you don't want to handle
        errors as it will silently fail.

    :param call_args: The call passed to :py:func:`~subprocess.Popen`
        with ``shell`` set to ``False``.
    :param input_callback: The callback that will be called for each line of
        output. If the callback returns ``True`` the given line of output will
        be skipped.
    :returns: A tuple with the first argument if the process crashed, the
        second item is ``stdout`` and ``stderr`` interleaved.
    """
    output = []

    def process_line(line: str) -> None:
        nonlocal output
        out = line.replace('\0', '')
        if not input_callback(out):
            output.append(out)

    try:
        with subprocess.Popen(
            call_args,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            shell=False,
            universal_newlines=True,
            bufsize=1,
        ) as proc:
            while proc.poll() is None:
                process_line(proc.stdout.readline())

            ok = proc.returncode == 0

            # There still might be some output left
            for line in proc.stdout.readlines():
                process_line(line)
    # pylint: disable=broad-except
    except Exception:  # pragma: no cover
        logger.warning(
            'External program crashed in a strange way.',
            call_args=call_args,
            exc_info=True,
        )
        output.append('Unknown crash!')
        ok = False

    return ok, ''.join(output)


def get_files_from_request(
    *,
    max_size: 'psef.archive.FileSize',
    keys: t.Sequence[str],
    only_start: bool = False,
) -> t.MutableSequence[FileStorage]:
    """Get all the submitted files in the current request.

    This function also checks if the files are in the correct format and are
    lot too large if you provide check_size. This is done for the entire
    request, not only the processed files.

    :param only_small_files: Only allow small files to be uploaded.
    :param keys: The keys the files should match in the request.
    :param only_start: If set to false the key of the request should only match
        the start of one of the keys in ``keys``.
    :returns: The files in the current request. The length of this list is
        always at least one and if ``only_start`` is false is never larger than
        the length of ``keys``.
    :raises APIException: When a given file is not correct.
    """
    res = []

    if (request.content_length or 0) > max_size:
        raise_file_too_big_exception(max_size)

    if not flask.request.files:
        raise errors.APIException(
            "No file in HTTP request.",
            "There was no file in the HTTP request.",
            errors.APICodes.MISSING_REQUIRED_PARAM, 400
        )

    if only_start:
        for key, file in flask.request.files.items():
            if any(key.startswith(cur_key) for cur_key in keys):
                res.append(file)
    else:
        for key in keys:
            if key in flask.request.files:
                res.append(flask.request.files[key])

        # Make sure we never return more files than requested.
        assert len(keys) >= len(res)

    if not res:
        raise errors.APIException(
            'Request did not contain any valid files', (
                'The request did not contain any files {} the parameter'
                ' name{} with "{}"'
            ).format(
                'where' if only_start else 'with',
                ' started' if only_start else '',
                ','.join(keys),
            ), errors.APICodes.MISSING_REQUIRED_PARAM, 400
        )

    # Werkzeug >= 0.14.0 should check this, however the documentation is not
    # completely clear and it is better to blow up here than somewhere else.
    # XXX: It seems that Werkzeug 0.15.0+ doesn't check this anymore...
    assert all(f.filename for f in res)

    return res


def is_sublist(needle: t.Sequence[T], hay: t.Sequence[T]) -> bool:
    """Check if a needle is present in the given hay.

    This is semi efficient, it uses Boyer-Moore however it doesn't cache the
    lookup tables.

    >>> is_sublist(list(range(10)), list(range(20)))
    True
    >>> is_sublist(list(range(5, 10)), list(range(20)))
    True
    >>> is_sublist(list(range(5, 21)), list(range(20)))
    False
    >>> is_sublist(list(range(20)), list(range(20)))
    True
    >>> is_sublist(list(range(21)), list(range(20)))
    False
    >>> is_sublist('thomas', 'hallo thom, ik as dit heel goed thomas, mooi he')
    True
    >>> is_sublist('saab', 'baas neem een racecar, neem een saab')
    True
    >>> is_sublist('aaaa', 'aa aaa aaba aaaa')
    True
    >>> is_sublist('aaaa', 'aa aaa aaba aaaba')
    False
    >>> is_sublist(['assig2'], ['assig2'])
    True
    >>> is_sublist(['assig2'], ['assig1'])
    False
    >>> is_sublist(['assig2'], ['assig1', 'assig2'])
    True

    :param needle: The thing you are searching for.
    :param hay: The thing you are searching in.
    :returns: A boolean indicating if ``needle`` was found in ``hay``.
    """
    if len(needle) > len(hay):
        return False
    elif len(needle) == len(hay):
        return needle == hay

    table: t.Dict[T, int] = {}
    index = len(needle) - 1
    needle_index = len(needle) - 1

    for i, element in enumerate(needle):
        if i == len(needle) - 1 and element not in table:
            table[element] = len(needle)
        else:
            table[element] = len(needle) - i - 1

    while index < len(hay):
        if needle[needle_index] == hay[index]:
            if needle_index == 0:
                return True
            else:
                needle_index -= 1
                index -= 1
        else:
            index += table.get(hay[index], len(needle))
            needle_index = len(needle) - 1
    return False


class BrokerSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.headers.update(
            {
                'CG-Broker-Pass': psef.app.config['AUTO_TEST_BROKER_PASSWORD'],
                'CG-Broker-Instance': psef.app.config['EXTERNAL_URL'],
            }
        )

    def request(
        self, method: str, url: str, *args: t.Any, **kwargs: t.Any
    ) -> requests.Response:
        url = urllib.parse.urljoin(
            psef.app.config['AUTO_TEST_BROKER_URL'], url
        )
        return super().request(method, url, *args, **kwargs)


class NotEqualMixin:
    """Simple mixin to provide correct ``__ne__`` behavior.

    >>> class Base:
    ...     x = 5
    ...     def __ne__(self, other): return self.x != other.x
    >>> class AWrong(Base):
    ...     def __eq__(self, other): return NotImplemented
    >>> class ACorrect(NotEqualMixin, Base):
    ...     def __eq__(self, other): return NotImplemented
    >>> AWrong() != AWrong
    False
    >>> ACorrect() != ACorrect()
    True
    """

    def __ne__(self, other: object) -> bool:
        return not self == other
