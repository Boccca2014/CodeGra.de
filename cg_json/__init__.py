"""This module contains all functionality for serializing objects to json.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import json as system_json
import uuid
import typing as t
import datetime
import contextlib
from json import JSONEncoder

import flask
import structlog
from flask import current_app

T = t.TypeVar('T')
logger = structlog.get_logger()


def _maybe_log_response(obj: object, response: t.Any, extended: bool) -> None:
    if not isinstance(obj, Exception):
        to_log = str(b''.join(response.response))
        max_length = 1000
        if len(to_log) > max_length:
            logger.bind(truncated=True, truncated_size=len(to_log))
            to_log = '{1:.{0}} ... [TRUNCATED]'.format(max_length, to_log)

        ext = 'extended ' if extended else ''
        logger.info(
            f'Created {ext}json return response',
            reponse_type=str(type(obj)),
            response=to_log,
        )
        logger.try_unbind('truncated', 'truncated_size')


class SerializableEnum(enum.Enum):
    """An enum that you can serialize to json.
    """

    def __to_json__(self) -> str:
        return self.name


class CustomJSONEncoder(JSONEncoder):
    """This JSON encoder is used to enable the JSON serialization of custom
    classes.

    Classes can define their serialization by implementing a `__to_json__`
    method.
    """

    def default(self, o: t.Any) -> t.Any:  # pylint: disable=method-hidden
        """A way to serialize arbitrary methods to JSON.

        Classes can use this method by implementing a `__to_json__` method that
        should return a JSON serializable object.

        :param obj: The object that should be converted to JSON.
        """
        if isinstance(o, uuid.UUID):
            return str(o)
        elif isinstance(o, datetime.datetime):
            return o.isoformat()
        elif isinstance(o, datetime.timedelta):
            return o.total_seconds()
        elif hasattr(o, '__to_json__'):
            return o.__to_json__()
        else:
            return super().default(o)


def get_extended_encoder_class(
    use_extended: t.Callable[[object], bool],
) -> t.Type:
    """Get a json encoder class.

    :param use_extended: The returned class only uses the
        ``__extended_to_json__`` method if this callback returns something that
        is equal to ``True``. This method is called with a single argument that
        is the object that is currently encoded.
    :returns: A class (not a instance!) that can be used as ``JSONEncoder``
        class.
    """

    class CustomExtendedJSONEncoder(CustomJSONEncoder):
        """This JSON encoder is used to enable the JSON serialization of custom
        classes.

        Classes can define their serialization by implementing a
        `__extended_to_json__` or a `__to_json__` method. This class first
        tries the extended method and if it does not exist it tries to normal
        one.
        """

        # These are false positives by pylint.
        def default(self, o: t.Any) -> t.Any:  # pylint: disable=method-hidden
            """A way to serialize arbitrary methods to JSON.

            Classes can use this method by implementing a `__to_json__` method
            that should return a JSON serializable object.

            :param o: The object that should be converted to JSON.
            """
            if hasattr(o, '__extended_to_json__') and use_extended(o):
                return o.__extended_to_json__()
            else:
                return super().default(o)

    return CustomExtendedJSONEncoder


T_JSONResponse = t.TypeVar('T_JSONResponse', bound='JSONResponse')  # pylint: disable=invalid-name

_UseExtendedType = t.Union[t.Callable[[object], bool],
                           type,
                           t.Tuple[type, ...],
                           ]


class JSONResponse(t.Generic[T], flask.Response):  # pylint: disable=too-many-ancestors
    """A datatype for a JSON response.

    This is a subtype of :py:class:`werkzeug.wrappers.Response` where the body
    is a valid JSON object and ``content-type`` is ``application/json``.
    """

    _SEPERATORS = (',', ':')

    @classmethod
    @contextlib.contextmanager
    def _setup_env(
        cls,
        use_extended: _UseExtendedType,  # pylint: disable=unused-argument
    ) -> t.Generator[None, None, None]:
        try:
            old_encoder = current_app.json_encoder
            current_app.json_encoder = CustomJSONEncoder
            yield
        finally:
            current_app.json_encoder = old_encoder

    @classmethod
    def _dump_to_string(cls, obj: T, use_extended: _UseExtendedType) -> str:
        with cls._setup_env(use_extended):
            return flask.json.dumps(
                obj,
                indent=None,
                separators=cls._SEPERATORS,
            ) + '\n'

    @classmethod
    def dump_to_object(cls, obj: T) -> t.Mapping:
        """Serialize the given object and parse its serialization.
        """

        class Unused:
            pass

        return system_json.loads(cls._dump_to_string(obj, use_extended=Unused))

    @classmethod
    def _make(
        cls: t.Type[T_JSONResponse],
        obj: T,
        status_code: int,
        *,
        use_extended: _UseExtendedType,
    ) -> T_JSONResponse:
        return cls(
            cls._dump_to_string(obj, use_extended=use_extended),
            mimetype=flask.current_app.config['JSONIFY_MIMETYPE'],
            status=status_code,
        )

    @classmethod
    def make(cls, obj: T, *, status_code: int = 200) -> 'JSONResponse[T]':
        """Create a response with the given object ``obj`` as json payload.

        :param obj: The object that will be jsonified using
            :py:class:`~.CustomJSONEncoder`
        :param status_code: The status code of the response
        :returns: The response with the jsonified object as payload
        """
        self = cls._make(obj, status_code, use_extended=object)

        _maybe_log_response(obj, self, False)

        return self


class ExtendedJSONResponse(t.Generic[T], JSONResponse[T]):  # pylint: disable=too-many-ancestors
    """A datatype for a JSON response created by using the
    ``__extended_to_json__`` if available.

    This is a subtype of :py:class:`werkzeug.wrappers.Response` where the body
    is a valid JSON object and ``content-type`` is ``application/json``.
    """

    @classmethod
    @contextlib.contextmanager
    def _setup_env(cls, use_extended: _UseExtendedType
                   ) -> t.Generator[None, None, None]:
        if isinstance(use_extended, (tuple, type)):
            class_only = use_extended
            use_extended = lambda o: isinstance(o, class_only)

        try:
            old_encoder = current_app.json_encoder
            current_app.json_encoder = get_extended_encoder_class(use_extended)
            yield
        finally:
            current_app.json_encoder = old_encoder

    @classmethod
    def dump_to_object(
        cls,
        obj: T,
        use_extended: _UseExtendedType = object,
    ) -> t.Mapping:
        """Serialize the given object and parse its serialization.

        See :meth:`.ExtendedJSONResponse.make` for the meaning of the
        arguments of this method.
        """
        return system_json.loads(
            cls._dump_to_string(obj, use_extended=use_extended)
        )

    @classmethod
    def make(
        cls,
        obj: T,
        *,
        status_code: int = 200,
        use_extended: _UseExtendedType = object,
    ) -> 'ExtendedJSONResponse[T]':
        """Create a response with the given object ``obj`` as json payload.

        This function differs from :py:func:`jsonify` by that it used the
        ``__extended_to_json__`` magic function if it is available.

        :param obj: The object that will be jsonified using
            :py:class:`~.CustomExtendedJSONEncoder`
        :param status_code: The status code of the response
        :param use_extended: The ``__extended_to_json__`` method is only used
            if this function returns something that equals to ``True``. This
            method is called with object that is currently being encoded. You
            can also pass a class or tuple as this parameter which is converted
            to ``lambda o: isinstance(o, passed_value)``.
        :returns: The response with the jsonified object as payload
        """
        self = cls._make(obj, status_code, use_extended=use_extended)

        _maybe_log_response(obj, self, True)

        return self


extended_jsonify = ExtendedJSONResponse.make  # pylint: disable=invalid-name
jsonify = JSONResponse.make  # pylint: disable=invalid-name
