"""
This module implements generic helpers and convenience functions.

SPDX-License-Identifier: AGPL-3.0-only
"""
import io
import os
import re
import abc
import sys
import enum
import time
import typing as t
import tempfile
import threading
import contextlib
import subprocess
import collections
import urllib.parse
import multiprocessing
from operator import itemgetter
from functools import wraps

import flask
import requests
import structlog
import mypy_extensions
import sqlalchemy_utils
from flask import g, request
from werkzeug.local import LocalProxy
from mypy_extensions import Arg
from requests.adapters import HTTPAdapter
from typing_extensions import Final, Literal, Protocol
from urllib3.util.retry import Retry
from sqlalchemy.dialects import postgresql
from werkzeug.datastructures import FileStorage
from sqlalchemy.sql.expression import or_

import psef
import cg_register as register
from cg_json import (
    JSONResponse, ExtendedJSONResponse, jsonify, extended_jsonify
)
from cg_timers import timed_code
from cg_helpers import flatten, handle_none, on_not_none, maybe_wrap_in_list
from cg_dt_utils import DatetimeWithTimezone
from cg_flask_helpers import (
    EmptyResponse, make_empty_response, callback_after_this_request
)
from cg_helpers.humanize import size as human_readable_size
from cg_sqlalchemy_helpers.types import Base, MyQuery, DbColumn

from . import validate, jsonify_options
from .. import errors, current_tester

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    import werkzeug  # pylint: disable=unused-import

    import psef.archive

    from ..models import Base  # pylint: disable=unused-import

logger = structlog.get_logger()

#: Type vars
T = t.TypeVar('T')
T_CONTRA = t.TypeVar('T_CONTRA', contravariant=True)  # pylint: disable=invalid-name
T_STOP_THREAD = t.TypeVar('T_STOP_THREAD', bound='StoppableThread')  # pylint: disable=invalid-name
T_CAL = t.TypeVar('T_CAL', bound=t.Callable)  # pylint: disable=invalid-name
TT = t.TypeVar('TT')
K = t.TypeVar('K')  # pylint: disable=invalid-name
TTT = t.TypeVar('TTT', bound='IsInstanceType')
ZZ = t.TypeVar('ZZ')
Z = t.TypeVar('Z', bound='Comparable')
DIV = t.TypeVar('DIV', bound='Dividable')
Y = t.TypeVar('Y', bound='Base')
T_Type = t.TypeVar('T_Type', bound=t.Type)  # pylint: disable=invalid-name
T_TypedDict = t.TypeVar(  # pylint: disable=invalid-name
    'T_TypedDict',
    bound=t.Mapping,
)
T_Hashable = t.TypeVar('T_Hashable', bound='Hashable')  # pylint: disable=invalid-name

IsInstanceType = t.Union[t.Type, t.Tuple[t.Type, ...]]  # pylint: disable=invalid-name


class MissingType(enum.Enum):
    token = 0


class UnsetType(enum.Enum):
    token = '__CG_UNSET__'


class _RequiredButMissingType(enum.Enum):
    token = '__CG_REQUIRED_BUT_MISSING__'


MISSING: Literal[MissingType.token] = MissingType.token
_REQUIRED_BUT_MISSING: Literal[_RequiredButMissingType.token
                               ] = _RequiredButMissingType.token
UNSET: Literal[UnsetType.token] = UnsetType.token


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

    jsonify_options.init_app(app)


def add_warning(warning: str, code: psef.exceptions.APIWarnings) -> None:
    """Add a warning to the current request.

    It is also safe to call this function from a celery task, but as expected
    the warning will not be displayed.

    >>> import flask
    >>> import psef
    >>> app = flask.Flask(__name__)
    >>> with app.app_context():
    ...     add_warning('Hello', psef.exceptions.APIWarnings.DEPRECATED)
    ...     print(len(flask.g.request_warnings))
    1
    """
    if not hasattr(g, 'request_warnings'):
        g.request_warnings = []
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


def mark_as_deprecated_route(warning: str) -> t.Callable[[T_CAL], T_CAL]:
    """Mark a given route as deprecated.

    :param warning: The deprecation warning that should be added to each
        request to the wrapped route.
    """

    def __wrapper(fun: T_CAL) -> t.Any:
        @wraps(fun)
        def __inner(*args: object, **kwargs: object) -> object:
            add_deprecate_warning(warning)
            return fun(*args, **kwargs)

        return t.cast(T_CAL, __inner)

    return __wrapper


class Dividable(Protocol):  # pragma: no cover
    """A protocol that for dividable variables.
    """

    @abc.abstractmethod
    def __truediv__(self: T, other: T) -> T:
        ...


class Hashable(Protocol):  # pragma: no cover
    """A protocol for hashable values.
    """

    @abc.abstractmethod
    def __hash__(self) -> int:
        ...


class Comparable(Protocol):  # pragma: no cover
    """A protocol that for comparable variables.

    To satisfy this protocol a object should implement the ``__eq__``,
    ``__lt__``, ``__gt__``, ``__le__`` and``__ge__`` magic functions.
    """

    @abc.abstractmethod
    def __eq__(self, other: t.Any) -> bool:
        ...

    @abc.abstractmethod
    def __lt__(self: Z, other: Z) -> bool:
        ...

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
    return sqlalchemy_utils.escape_like(unescaped_like, escape_char='\\')


class FloatHelpers:
    """Utilities for dealing with float comparisons.
    """

    @staticmethod
    def ge(a: float, b: float) -> bool:
        """Check if ``a`` is greater than ``b``.

        >>> ge = FloatHelpers.ge
        >>> ge(1.0, 2.0)
        False
        >>> ge(1.0, 1.0)
        False
        >>> ge(1.1, 1.0)
        True
        >>> ge(1.0, 1.0 + (sys.float_info.epsilon / 2))
        False

        :param a: The number to check if it is greater than ``b``.
        :param b: The number to check against.
        """
        return a > b

    @staticmethod
    def le(a: float, b: float) -> bool:
        """Check if ``a`` is less than ``b``.

        >>> le = FloatHelpers.le
        >>> le(1.0, 2.0)
        True
        >>> le(1.0, 1.0)
        False
        >>> le(1.1, 1.0)
        False
        >>> le(1.0, 1.0 + (sys.float_info.epsilon / 2))
        False

        :param a: The number to check if it is less than ``b``.
        :param b: The number to check against.
        """
        return a < b

    @classmethod
    def leq(cls, a: float, b: float) -> bool:
        """Check if ``a`` is less than or equal to ``b``.

        >>> leq = FloatHelpers.leq
        >>> leq(1.0, 2.0)
        True
        >>> leq(1.0, 1.0)
        True
        >>> leq(1.1, 1.0)
        False
        >>> leq(1.0, 1.0 + (sys.float_info.epsilon / 2))
        True

        :param a: The number to check if it is less than ``b``.
        :param b: The number to check against.
        """
        return cls.le(a, b) or cls.eq(a, b)

    @classmethod
    def geq(cls, a: float, b: float) -> bool:
        """Check if ``a`` is greater than or equal to ``b``.

        >>> geq = FloatHelpers.geq
        >>> geq(1.0, 2.0)
        False
        >>> geq(1.0, 1.0)
        True
        >>> geq(1.1, 1.0)
        True
        >>> geq(1.0, 1.0 - sys.float_info.epsilon)
        True

        :param a: The number to check if it is greater than ``b``.
        :param b: The number to check against.
        """
        return cls.ge(a, b) or cls.eq(a, b)

    @staticmethod
    def eq(a: float, b: float) -> bool:
        """Check if ``a`` and ``b`` are equal.

        >>> eq = FloatHelpers.eq
        >>> eq(1.0, 2.0)
        False
        >>> eq(1.0, 1.0)
        True
        >>> eq(1.0, 1.0 + sys.float_info.epsilon)
        True
        """
        return abs(a - b) <= sys.float_info.epsilon


def safe_div(a: DIV, b: DIV, default: T) -> t.Union[DIV, T]:
    """Divide ``a`` by ``b``, when this raises a :class:`ZeroDivisionError`
        ``default`` is returned.

    >>> safe_div(1, 2, object())
    0.5
    >>> sentinal = object()
    >>> safe_div(1, 0, sentinal) is sentinal
    True

    :param a: The dividend of the division.
    :param b: The divisor of the division.
    :param default: The default value if the division raises
        :class:`ZeroDivisionError`
    :returns: The division or default.
    """
    try:
        return a / b
    except ZeroDivisionError:
        return default


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


def get_request_start_time() -> DatetimeWithTimezone:
    """Return the start time of the current request.

    :returns: The time as returned by the python time module.
    :rtype: float
    """
    if not hasattr(flask.g, 'request_start_time'):
        flask.g.request_start_time = DatetimeWithTimezone.utcnow()
    return flask.g.request_start_time


_JSONValue = t.Union[str, int, float, bool, None, t.Dict[str, t.Any],  # pylint: disable=invalid-name
                     t.List[t.Any]]
JSONType = t.Union[t.Dict[str, _JSONValue], t.List[_JSONValue], _JSONValue]  # pylint: disable=invalid-name


class LockType(enum.Enum):
    """How should the row be locked.
    """
    full = 1
    read = 2


@t.overload
def get_in_or_error(
    model: t.Type[Y],
    in_column: DbColumn[T],
    in_values: t.List[T],
    options: t.Optional[t.List[t.Any]] = None,
    *,
    as_map: Literal[True],
    also_error: t.Callable[[Y], bool] = None,
    same_order_as_given: Literal[False] = False,
) -> t.Dict[T, Y]:
    # pylint: disable=missing-function-docstring
    ...


@t.overload
def get_in_or_error(
    model: t.Type[Y],
    in_column: DbColumn[T],
    in_values: t.List[T],
    options: t.Optional[t.List[t.Any]] = None,
    *,
    as_map: Literal[False] = False,
    also_error: t.Callable[[Y], bool] = None,
    same_order_as_given: bool = False,
) -> t.List[Y]:
    # pylint: disable=missing-function-docstring
    ...


def get_in_or_error(
    model: t.Type[Y],
    in_column: DbColumn[T],
    in_values: t.List[T],
    options: t.Optional[t.List[t.Any]] = None,
    *,
    also_error: t.Callable[[Y], bool] = None,
    as_map: bool = False,
    same_order_as_given: bool = False
) -> t.Union[t.Dict[T, Y], t.List[Y]]:
    """Get object by doing an ``IN`` query.

    This method protects against empty ``in_values``, and will return an empty
    list in that case. If not all items from the ``in_values`` this function
    will raise an exception.

    :param model: The objects to get.
    :param in_column: The column of the object to perform the in on.
    :param in_values: The values used for the ``IN`` clause. This may be an
        empty sequence, which is handled without doing a query. Each item in
        the list should be unique.
    :param options: A list of options to give to the executed query. This can
        be used to undefer or eagerly load some columns or relations.
    :param as_map: Should the return value be returned as mapping between the
        `in_column` and the received item from the database.
    :param same_order_s_given: If this is ``True`` the resulting list will
        ordered the same as the given list of ``in_values``. This option cannot
        be combined with ``as_map``. This option is especially useful for
        testing, as it allows a deterministic order of the returned list.

    :returns: A list of objects with the same length as ``in_values``.
    :raises APIException: If on of the items in ``in_values`` was not found.
    """
    assert not (as_map and same_order_as_given)
    if psef.current_app.do_sanity_checks:  # pragma: no cover
        # This check does some assumptions (that each value in ``in_values`` is
        # hashable for example), and can be quite slow. So we only do it when
        # sanity checks are enabled.
        assert not contains_duplicate(in_values), (
            'The given ``in_values`` ({}) contains duplicates, which is not'
            ' supported'
        ).format(in_values)

    res: t.List[t.Tuple[T, Y]]
    if not in_values:
        res = []
    else:
        query = psef.models.db.session.query(in_column, model).filter(
            in_column.in_(in_values)
        )
        if options is not None:
            query = query.options(*options)

        res = query.all()

    def _raise() -> t.NoReturn:
        raise psef.errors.APIException(
            f'Not all requested {model.__name__.lower()} could be found', (
                f'Out of the {len(in_values)} requested only {len(res)} were'
                ' found'
            ), psef.errors.APICodes.OBJECT_ID_NOT_FOUND, 404
        )

    if len(res) != len(in_values):
        _raise()
    elif also_error is not None and any(also_error(item[1]) for item in res):
        _raise()

    if as_map:
        return dict(res)
    elif same_order_as_given:
        lookup = dict(res)
        return [lookup[given_value] for given_value in in_values]
    return [item[1] for item in res]


@t.overload
def _filter_or_404(
    model: t.Type[Y],
    get_all: Literal[True],
    criteria: t.Sequence[DbColumn[bool]],
    also_error: t.Optional[t.Callable[[t.List[Y]], bool]],
    with_for_update: t.Union[bool, LockType],
    options: t.Optional[t.List[t.Any]] = None,
    with_for_update_of: t.Optional[t.Type['Base']] = None,
) -> t.Sequence[Y]:
    ...


@t.overload
def _filter_or_404(
    model: t.Type[Y],
    get_all: Literal[False],
    criteria: t.Sequence[DbColumn[bool]],
    also_error: t.Optional[t.Callable[[Y], bool]],
    with_for_update: t.Union[bool, LockType],
    options: t.Optional[t.List[t.Any]] = None,
    with_for_update_of: t.Optional[t.Type['Base']] = None,
) -> Y:
    ...


def _filter_or_404(
    model: t.Type[Y],
    get_all: bool,
    criteria: t.Sequence[DbColumn[bool]],
    also_error: t.Optional[t.Callable[[t.Any], bool]],
    with_for_update: t.Union[bool, LockType],
    options: t.Optional[t.List[t.Any]] = None,
    with_for_update_of: t.Optional[t.Type['Base']] = None,
) -> t.Union[Y, t.Sequence[Y]]:
    """Get the specified object by filtering or raise an exception.

    :param get_all: Get all objects if ``True`` else get a single one.
    :param model: The object to get.
    :param criteria: The criteria to filter with.
    :param with_for_update_of: Which tables should be locked, only useful when
        ``with_for_update`` is not ``None``.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    query = model.query.filter(*criteria)
    if with_for_update:
        query = query.with_for_update(
            read=with_for_update == LockType.read, of=with_for_update_of
        )
    if options is not None:
        query = query.options(*options)

    obj = query.all() if get_all else query.one_or_none()

    if not obj or (also_error is not None and also_error(obj)):
        crit_str = ' AND '.join(
            str(
                crit.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={'literal_binds': True}
                )
            ) for crit in criteria
        )
        raise psef.errors.APIException(
            f'The requested {model.__name__.lower()} was not found',
            f'There is no "{model.__name__}" when filtering with {crit_str}',
            psef.errors.APICodes.OBJECT_NOT_FOUND, 404
        )
    return obj


def filter_all_or_404(
    model: t.Type[Y],
    *criteria: DbColumn[bool],
    with_for_update: t.Union[bool, LockType] = False,
) -> t.Sequence[Y]:
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
    return t.cast(
        t.Sequence[Y],
        _filter_or_404(model, True, criteria, None, with_for_update)
    )


def filter_single_or_404(
    model: t.Type[Y],
    *criteria: DbColumn[bool],
    also_error: t.Optional[t.Callable[[Y], bool]] = None,
    with_for_update: t.Union[bool, LockType] = False,
    options: t.Optional[t.List[t.Any]] = None,
    with_for_update_of: t.Optional[t.Type['Base']] = None,
) -> Y:
    """Get a single object of the specified model by filtering or raise an
    exception.

    .. note::
        ``Y`` is bound to :py:class:`.Base`, so it should be a
        SQLAlchemy model.

    :param model: The object to get.
    :param criteria: The criteria to filter with.
    :param with_for_update_of: Which tables should be locked, only useful when
        ``with_for_update`` is not ``None``.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    return t.cast(
        Y,
        _filter_or_404(
            model,
            False,
            criteria,
            also_error,
            with_for_update,
            options,
            with_for_update_of=with_for_update_of,
        )
    )


def get_or_404(
    model: t.Type[Y],
    object_id: t.Any,
    options: t.Optional[t.List[t.Any]] = None,
    also_error: t.Optional[t.Callable[[Y], bool]] = None,
    *,
    with_for_update: t.Union[bool, LockType] = False,
    with_for_update_of: t.Optional[t.Type['Base']] = None,
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

    if with_for_update:
        query = query.with_for_update(
            read=with_for_update == LockType.read, of=with_for_update_of
        )
    else:
        assert with_for_update_of is None

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
    """Make sure we are on a test server.
    """
    assert not flask.has_app_context()
    assert not flask.has_request_context()
    # pylint: disable=protected-access
    assert current_tester._get_current_object() is not None


def _get_type_name(
    typ: t.Union[t.Type, t.Tuple[t.Type, ...], register.Register]
) -> str:
    if isinstance(typ, tuple):
        return ', '.join(map(_get_type_name, typ))
    elif isinstance(typ, register.Register):
        return 'UnionOf[{}]'.format(', '.join(map(str, typ.keys())))
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


class TransactionGet(Protocol[K]):
    """Protocol for a function to get something with a given type from a map.
    """

    @t.overload
    def __call__(self, to_get: K, typ: t.Type[T]) -> T:
        ...

    @t.overload
    def __call__(
        self,
        t_get: K,
        typ: register.Register[K, T],
        transform: t.Callable[[t.Tuple[K, T]], TT],
    ) -> TT:
        ...

    @t.overload
    def __call__(
        self,
        to_get: K,
        typ: t.Type[T],
        *,
        transform: t.Callable[[T], TT],
    ) -> TT:
        ...

    @t.overload
    def __call__(
        self,
        to_get: K,
        typ: t.Tuple[t.Type[T], t.Type[TT]],
        *,
        transform: t.Callable[[t.Union[T, TT]], ZZ],
    ) -> ZZ:
        ...

    @t.overload
    def __call__(
        self,
        to_get: K,
        typ: t.Tuple[t.Type[T], t.Type[TT]],
    ) -> t.Union[T, TT]:
        ...

    @t.overload
    def __call__(
        self,
        to_get: K,
        typ: t.Tuple[t.Type[T], t.Type[TT], t.Type[ZZ]],
    ) -> t.Union[T, TT, ZZ]:
        ...


class TransactionOptionalGet(Protocol[T_CONTRA]):
    """Protocol for a function to optionally get something with a given type
    from a map.
    """

    @t.overload
    def __call__(self, to_get: T_CONTRA, typ: t.Type[T],
                 default: TT) -> t.Union[T, TT]:
        ...

    @t.overload
    def __call__(
        self, to_get: T_CONTRA, typ: t.Tuple[t.Type[T], t.Type[TT]],
        default: ZZ
    ) -> t.Union[T, TT, ZZ]:
        ...

    @t.overload
    def __call__(self, to_get: T_CONTRA,
                 typ: t.Type[T]) -> t.Union[T, Literal[MissingType.token]]:
        ...

    @t.overload
    def __call__(
        self,
        to_get: T_CONTRA,
        typ: t.Tuple[t.Type[T], t.Type[TT]],
    ) -> t.Union[T, TT, Literal[MissingType.token]]:
        ...

    @t.overload
    def __call__(
        self,
        to_get: T_CONTRA,
        typ: t.Tuple[t.Type[T], t.Type[TT], t.Type[ZZ]],
    ) -> t.Union[T, TT, ZZ, Literal[MissingType.token]]:
        ...

    @t.overload
    def __call__(
        self,
        to_get: T_CONTRA,
        typ: t.Tuple[t.Type[T], t.Type[TT]],
        *,
        transform: t.Callable[[t.Union[T, TT]], ZZ],
    ) -> t.Union[ZZ, Literal[MissingType.token]]:
        ...


# pylint: enable


@contextlib.contextmanager
def get_from_map_transaction(
    mapping: t.Mapping[T, TT],
    *,
    ensure_empty: bool = False,
) -> t.Generator[t.Tuple[TransactionGet[T], TransactionOptionalGet[T]], None,
                 None]:
    """Get from the given map in a transaction like style.

    If all gets and optional gets succeed at the end of the ``with`` block no
    exception will be raised. However, as soon as one fails we continue with
    the block, but at the end an exception with all failed gets will be raised.

    :param mapping: The mapping to get values from.
    :param ensure_empty: Also raise an exception if the map contained more keys
        than requested.
    :returns: A tuple of two functions. The first function takes a key and type
        as arguments indicating that the value under the given key should be of
        the given type. The second function also takes a default value as
        argument, if the key was not found in the mapping this value will be
        returned.
    """
    all_keys_requested = []
    keys = []

    def get(
        key: T,
        typ: t.Union[t.Type, t.Tuple[t.Type, ...], register.Register],
        *,
        transform: t.Callable[[TT], TTT] = None,
    ) -> TTT:
        all_keys_requested.append(key)
        keys.append((key, typ))
        value: t.Union[TT, MissingType] = mapping.get(key, MISSING)
        correct_type = False

        if (
            isinstance(typ, type) and issubclass(typ, enum.Enum) and
            isinstance(value, str)
        ):
            value = t.cast(TT, typ.__members__.get(value, MISSING))
            correct_type = value is not MISSING
        elif isinstance(typ, register.Register):
            value = t.cast(TT, (value, typ.get_or(value, MISSING)))
            correct_type = value is not MISSING
        else:
            correct_type = isinstance(value, typ)

        if transform is not None and correct_type:
            return transform(t.cast(TT, value))

        return t.cast(TTT, value)

    def optional_get(
        key: T,
        typ: t.Union[t.Type, t.Tuple[t.Type, ...]],
        default: t.Any = MISSING,
        *,
        transform: t.Callable = None,
    ) -> object:
        if key not in mapping:
            all_keys_requested.append(key)
            return default
        return get(key, typ, transform=transform)

    try:
        yield get, optional_get  # type: ignore
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


def get_from_request_transaction(
    *,
    ensure_empty: bool = False,
) -> t.ContextManager[t.Tuple[TransactionGet[str], TransactionOptionalGet[str]]
                      ]:
    """The same as :func:`get_from_map_transaction` but with
        :func:`get_json_dict_from_request` as first argument.
    """
    return get_from_map_transaction(
        get_json_dict_from_request(), ensure_empty=ensure_empty
    )


def ensure_keys_in_dict(
    mapping: t.Mapping[T, object],
    keys: t.Sequence[t.Tuple[T, t.Union[IsInstanceType, register.Register]]]
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
        value = mapping.get(key, MISSING)
        if value is MISSING:
            missing.append(key)
        elif (
            isinstance(check_type, type) and
            issubclass(check_type, enum.Enum) and isinstance(value, str)
        ):
            if value not in check_type.__members__:
                missing.append(
                    f'{key} was of wrong type'
                    f' (should be a member of "{_get_type_name(check_type)}"'
                    f' (= {", ".join(it.name for it in check_type)})'
                    f', was "{value}")'
                )
                type_wrong = True
        elif isinstance(check_type, register.Register):
            if value not in check_type:
                missing.append(
                    f'{key} was of wrong type'
                    f' (should be a member of "{check_type}"'
                    f' (= {", ".join(map(str, check_type.keys()))})'
                    f', was "{value}")'
                )
        elif (
            (not isinstance(value, check_type)) or
            (check_type == int and isinstance(value, bool))
        ):
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


def maybe_apply_sql_slice(sql: 'MyQuery[T]') -> 'MyQuery[T]':
    """Slice the given query if ``limit`` is given in the request args.

    :param sql: The query to slice.
    :returns: The slices query with ``limit`` and ``offset`` from the request
        parameters. If these can not be found in the request parameters the
        query is returned unaltered.
    """
    limit = request.args.get('limit', None, type=int)
    if limit is None or limit <= 0:
        return sql

    offset = max(request.args.get('offset', 0, type=int), 0)
    return sql.slice(offset, offset + limit)


def get_json_dict_from_request(
    *,
    replace_log: t.Optional[t.Callable[[str, object], object]] = None,
    log_object: bool = True,
) -> t.Dict[str, JSONType]:
    """Get the JSON dict from this request.

    :param replace_log: A function that replaces options in the log.
    :returns: The JSON found in the request if it is a dictionary.

    :raises psef.errors.APIException: If the found JSON is not a dictionary.
        (INVALID_PARAM)
    """
    return ensure_json_dict(
        request.get_json(), replace_log=replace_log, log_object=log_object
    )


def ensure_json_dict(
    json_value: JSONType,
    *,
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
    if isinstance(json_value, dict):
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


def request_arg_true(
    arg_name: str, request_args: t.Mapping[str, str] = None
) -> bool:
    """Check if a request arg was set to a 'truthy' value.

    :param arg_name: The name of the argument to check.
    :returns: ``True`` if and only iff the requested get parameter ``arg_name``
        is present and it value equals (case insensitive) ``'true'``, ``'t'``,
        ``'1'``, or ``''`` (empty string).
    """
    if request_args is None:
        request_args = flask.request.args
    return request_args.get(arg_name,
                            'false').lower() in {'true', 't', '1', ''}


def extended_requested() -> bool:
    """Check if a extended JSON serialization was requested.

    :returns: The return value of :func:`.request_arg_true` called with
        ``'extended'`` as argument.
    """
    return request_arg_true('extended')


@contextlib.contextmanager
def defer(*functions: t.Callable[[], object]) -> t.Generator[None, None, None]:
    """Defer a function call to the end of the context manager.

    :param functions: The functions to call, they will be called in order, so
        the first function first, and the last. This means that
        ``with defer(f1, f2)`` is equivalent to ``with defer(f2), defer(f1)``.
    :returns: A context manager that can be used to execute the given functions
        at the end of the block.
    """
    if not functions:
        yield
    else:
        *rest, function = functions
        try:
            with defer(*rest):
                yield
        finally:
            logger.info('Calling defer', defer_function=function)
            function()


class StoppableThread(abc.ABC):
    """This abstract class represents a thread that can be stopped using a
    method.
    """

    @abc.abstractmethod
    def start(self: T_STOP_THREAD) -> T_STOP_THREAD:
        """Start this thread.

        This function should block until the thread has started.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def cancel(self) -> None:
        """Cancel this thread.

        This function should block until the thread has stopped.
        """
        raise NotImplementedError

    def __exit__(
        self, exc_type: object, exc_value: object, traceback: object
    ) -> None:
        self.cancel()

    def __enter__(self: T_STOP_THREAD) -> T_STOP_THREAD:
        return self.start()


class RepeatedTimer(StoppableThread):
    """Call a function repeatedly in a separate process.
    """

    def __init__(
        self,
        interval: int,
        function: t.Callable[[], None],
        *,
        cleanup: t.Callable[[], None] = lambda: None,
        setup: t.Callable[[], None] = lambda: None,
    ) -> None:
        super().__init__()
        self.__interval = interval
        self.__function_name = function.__qualname__

        def fun() -> None:
            try:
                function()
            except:  # pylint: disable=bare-except
                logger.warning('Repeated function crashed', exc_info=True)

        get_event = multiprocessing.Event

        self.__function = fun

        self.__finish = get_event()
        self.__finished = get_event()
        self.__started = get_event()

        self.__cleanup = cleanup
        self.__setup = setup
        self.__background: t.Optional[multiprocessing.Process] = None

    def cancel(self) -> None:
        if not self.__finish.is_set():
            assert self.__background
            self.__finish.set()
            self.__background.join()
            self.__finished.wait()

    def start(self) -> 'RepeatedTimer':
        self.__finish.clear()
        self.__started.clear()

        def fun() -> None:
            with defer(self.__function, self.__cleanup, self.__finished.set):
                self.__started.set()
                logger.info(
                    'Started repeating timer', function=self.__function_name
                )
                self.__setup()
                while not self.__finish.is_set():
                    self.__function()
                    self.__finish.wait(self.__interval)

        back = multiprocessing.Process(target=fun)
        back.start()
        self.__background = back
        self.__started.wait()

        return self


def call_external(
    call_args: t.List[str],
    input_callback: t.Callable[[str], bool] = lambda _: False,
    *,
    nice_level: t.Optional[int] = None,
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

    def preexec_fn() -> None:  # pragma: no cover
        if nice_level is not None:
            try:
                os.nice(nice_level)
            except:  # pylint: disable=bare-except
                pass

    try:
        child_env = {'PATH': os.environ['PATH']}
        # The preexec_fn is not really safe when combined with
        # threads. However, we don't combine it with threads as celery doesn't
        # run threaded. Even if it would run threaded, the function is really
        # simple so the chance of a deadlock is quite low.
        with subprocess.Popen(  # pylint: disable=subprocess-popen-preexec-fn
            call_args,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            shell=False,
            universal_newlines=False,
            bufsize=1,
            preexec_fn=preexec_fn,
            env=child_env,
        ) as proc:
            # `stdout` is never `None` as we pass in values for them, but in
            # typeshed they are annotated as optional:
            # https://github.com/python/typeshed/issues/3831
            # https://github.com/python/typeshed/pull/3652
            if proc.stdout is None:  # pragma: no cover
                # We use an `if` here so `mypy` will start complaining about
                # unreachable code if this issue is resolved.
                assert False

            while proc.poll() is None:
                process_line(
                    proc.stdout.readline().decode('utf8', 'backslashreplace')
                )

            ok = proc.returncode == 0

            # There still might be some output left
            for line in proc.stdout.readlines():
                process_line(line.decode('utf8', 'backslashreplace'))
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

    :param max_size: Maximum file size.
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
            if any(
                key.startswith(cur_key) for cur_key in keys
            ) and file.filename:
                res.append(file)
    else:
        for key in keys:
            if key in flask.request.files:
                file = flask.request.files[key]
                if file.filename:
                    res.append(file)

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


def mount_retry_adapter(
    session: requests.Session,
    *,
    retries: int = 10,
    backoff_fator: float = 1.2
) -> None:
    """Mount a retry adapter to the given session.

    :param session: The session to mount the adapter to.
    :param retries: The amount of retries to do.
    :param backoff_factor: The ``backoff_factor`` to provide to the adapter.
    """
    adapter = HTTPAdapter(
        max_retries=Retry(
            total=retries,
            read=retries,
            connect=retries,
            status=retries,
            backoff_factor=backoff_fator,
            method_whitelist=frozenset(
                [*Retry.DEFAULT_METHOD_WHITELIST, 'PATCH']
            ),
            status_forcelist=(500, 501, 502, 503, 504),
        )
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)


class BrokerSession(requests.Session):
    """A session to use when doing requests to the AutoTest broker.
    """

    def __init__(
        self,
        broker_pass: str = None,
        external_url: str = None,
        broker_base: str = None,
        runner_pass: str = None,
        *,
        retries: int = None,
    ) -> None:
        super().__init__()
        self.broker_base = (
            broker_base if broker_base is not None else
            psef.app.config['AUTO_TEST_BROKER_URL']
        )

        self.headers.update(
            {
                'CG-Broker-Pass':
                    broker_pass if broker_pass is not None else
                    psef.app.config['AUTO_TEST_BROKER_PASSWORD'],
                'CG-Broker-Instance':
                    external_url if external_url is not None else
                    psef.app.config['EXTERNAL_URL'],
                'CG-Broker-Runner-Pass': runner_pass or '',
            }
        )
        if retries is not None:
            mount_retry_adapter(self, retries=retries)

    def request(  # pylint: disable=signature-differs
        self,
        method: str,
        url: t.Union[str, bytes, t.Text],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> requests.Response:
        """Do a request to the AutoTest broker.
        """
        url = urllib.parse.urljoin(self.broker_base, str(url))
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 10
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


def retry_loop(
    amount: int,
    *,
    sleep_time: t.Union[float, t.Callable[[int], float]] = 1,
    make_exception: t.Callable[[], Exception],
) -> t.Iterator[int]:
    """Retry

    >>> import doctest
    >>> doctest.ELLIPSIS_MARKER = '-etc-'
    >>> for _ in retry_loop(5, make_exception=AssertionError): break
    >>> for i in retry_loop(2, make_exception=AssertionError):
    ...  if i == 0: break
    -etc-Retry loop failed-etc-
    >>> for i in retry_loop(1, make_exception=AssertionError):
    ...  if i: break
    Traceback (most recent call last):
    ...
    AssertionError
    >>> for i in retry_loop(1,  make_exception=lambda: ValueError()):
    ...  pass
    Traceback (most recent call last):
    ...
    ValueError
    >>> doctest.ELLIPSIS_MARKER = '-etc-'
    >>> args = []
    >>> for _ in retry_loop(
    ...      10,
    ...      sleep_time=lambda i: [args.append(i), 0][1],
    ...      make_exception=AssertionError):
    ...  pass
    Traceback (most recent call last):
    -etc-
    AssertionError
    >>> args  # We retry 10 times, so we expect 9 calls to sleep
    [1, 2, 3, 4, 5, 6, 7, 8, 9]
    """
    assert amount > 0, "amount should be higher than 0"

    i = amount

    if callable(sleep_time):
        get_sleep_time = sleep_time
    else:
        _time: float = sleep_time

        def get_sleep_time(_: int) -> float:
            return _time

    while i > 1:
        i -= 1
        yield i
        logger.warning(
            "Retry loop failed",
            amount_of_tries_left=i,
            total_amount_of_tries=amount,
        )
        time.sleep(get_sleep_time(amount - i))

    yield 0
    logger.warning("Retry loop failed", amount_of_tries_left=0)

    raise make_exception()


def format_list(lst: t.List[str], **formatting: str) -> t.List[str]:
    """Format a given list by formatting each item.

    >>> lst = ['{a}', 'b', '{ce} {a}']
    >>> format_list(lst, a='b', ce='wee')
    ['b', 'b', 'wee b']
    >>> res1 = format_list(lst, a='b', ce='wee')
    >>> res2 = format_list(lst, a='b', ce='wee')
    >>> res1 is not res2
    True
    >>> format_list(['{c}'])
    Traceback (most recent call last):
    ...
    KeyError: 'c'

    :param lst: A list of strings to format.
    :param formatting: The formatting arguments.
    :returns: A new fresh formatted list.
    """
    return [part.format(**formatting) for part in lst]


def readable_join(lst: t.Sequence[str]) -> str:
    """Join a list using comma's and the word "and"

    >>> readable_join(['a', 'b', 'c'])
    'a, b, and c'
    >>> readable_join(['a'])
    'a'
    >>> readable_join(['a', 'b'])
    'a and b'

    :param lst: The list to join.
    :returns: The list joined as described above.
    """
    if len(lst) < 3:
        return ' and '.join(lst)
    return ', '.join(lst[:-1]) + ', and ' + lst[-1]


def contains_duplicate(it_to_check: t.Iterable[T_Hashable]) -> bool:
    """Check if an iterable contains duplicate values.

    >>> import itertools as it
    >>> contains_duplicate(range(10))
    False
    >>> contains_duplicate([object(), object()])
    False
    >>> contains_duplicate([object, object])
    True
    >>> contains_duplicate(list(range(10)) + list(range(10)))
    True
    >>> contains_duplicate(it.chain(range(5), range(5)))
    True

    :param it_to_check: The sequence to check for duplicate values. This can be
        a generator which cannot be rewound.
    :returns: If ``it_to_check`` contains any duplicate values.
    """
    seen: t.Set[T_Hashable] = set()
    for item in it_to_check:
        if item in seen:
            return True
        seen.add(item)

    return False


def chunkify(iterable: t.Iterable[T],
             chunk_size: int) -> t.Iterable[t.List[T]]:
    """Chunkify the given iterable with chunks of size ``chunk_size``.

    >>> list(chunkify(range(5), 2))
    [[0, 1], [2, 3], [4]]
    >>> list(chunkify(range(4), 2))
    [[0, 1], [2, 3]]
    >>> list(chunkify([], 2))
    []

    :param iterable: The iterable to chunkify.
    :param chunk_size: The size of the chunks.
    """
    cur = []
    for item in iterable:
        cur.append(item)
        if len(cur) == chunk_size:
            yield cur
            cur = []

    if cur:
        yield cur


def maybe_unwrap_proxy(
    item: t.Union[T, LocalProxy], typ: t.Type[T], *, check: bool = False
) -> T:
    """Unwrap the possible local proxy for a given object.

    >>> obj1 = object()
    >>> prox = LocalProxy(lambda: obj1)
    >>> maybe_unwrap_proxy(obj1, object, check=True) is obj1
    True
    >>> maybe_unwrap_proxy(prox, object, check=True) is obj1
    True
    >>> maybe_unwrap_proxy(prox, int, check=False) is obj1
    True
    >>> maybe_unwrap_proxy(prox, int, check=True)
    Traceback (most recent call last):
    ...
    AssertionError
    >>> maybe_unwrap_proxy(5, str, check=True)
    Traceback (most recent call last):
    ...
    AssertionError

    :param item: The item we should unwrap.
    :param typ: The type that ``item`` is expected to be, this is unused during
        runtime if ``check`` is ``False``.
    :param check: Should we enforce that the resulting item is an instance of
        ``typ``.
    :returns: If the given ``item`` was a LocalProxy
        `_get_current_object()` is called and the return value is returned,
        otherwise the given ``item`` is returned.
    :raises AssertionError: If the given ``item`` was not of type ``type`` and
        ``check`` was ``True`` unwrapping.
    """
    if isinstance(item, LocalProxy):
        # pylint: disable=protected-access
        found = item._get_current_object()
    else:
        found = item

    if check and not isinstance(found, typ):
        raise AssertionError(f'The given item is not a {typ}')

    return found


def deep_get(
    dictionary: t.Mapping[str, t.Any], keys: t.List[str], dflt: t.Any
) -> t.Any:
    """Get the given keys from the given dictionary.

    .. note::

        This method destroys any type checking done by ``mypy``, if at all
        possible not use this method please don't. This method really is not meant to be
        used with a literal value for ``keys``.

    :param dictionary: The mapping from which you want to get the keys.
    :param keys: The keys to get.
    :param dflt: The value to return if one of the ``keys`` is not present in a
        mapping, or if one of the intermediate values is not an instance of
        :class:`.collections.Mapping`.

    :returns: The found value or ``dflt``.
    """
    val: t.Any = dictionary
    for key in keys:
        if not isinstance(val, collections.Mapping) or key not in val:
            return dflt
        val = val[key]
    return val


def try_for_every(
    options: t.Iterable[T],
    fun: t.Callable[[T], object],
    to_except: t.Type[Exception] = Exception
) -> None:
    """Try a function for multiple values until it passes.

    :param options: The options to try.
    :param fun: The function to call for every option.
    :param to_except: The errors to except, by default all errors are excepted.

    :returns: Nothing.
    :raises Exception: If the given ``fun`` errors for every given option.
    """
    if not options:
        return

    for option in options:
        try:
            fun(option)
        except to_except as e:  # pylint: disable=broad-except
            err = e
        else:
            break
    else:
        raise err
