"""This module contains utilities for caching between requests.

.. note:: This doesn't do caching between instances.

SPDX-License-Identifier: AGPL-3.0-only
"""
import abc
import enum
import json
import typing as t
from datetime import timedelta

import flask
import redis as redis_module
import structlog
from typing_extensions import Literal

logger = structlog.get_logger()


class NotSetType(enum.Enum):
    token = '__CG_CACHE_UNSET__'


T = t.TypeVar('T')
Y = t.TypeVar('Y')


def init_app(app: flask.Flask) -> None:  # pylint: disable=unused-argument
    """Initialize the caching.
    """


class Backend(abc.ABC, t.Generic[T]):
    """The base caching backend backend.
    """

    def __init__(self, namespace: str, ttl: timedelta) -> None:
        self._namespace = namespace
        self._ttl = ttl

    def _make_key(self, key: str) -> str:
        return f'{self._namespace}/{key}'

    @abc.abstractmethod
    def clear(self, key: str) -> None:
        """Clear the given ``key`` from the cache.

        :param key: The key to clear from the cache.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, key: str) -> T:
        """Get the given ``key`` from the cache.

        :param key: The key you want get.

        :returns: The found value.

        :raises KeyError: If the ``key`` was not found in the cache.
        """
        raise NotImplementedError

    def get_or(self, key: str, dflt: Y) -> t.Union[T, Y]:
        """Get the given ``key`` from the cache or return a default.

        :param key: The key to get from the cache.
        :param dflt: The item to return if the key wasn't found.

        :returns: The found item or the default.
        """
        try:
            return self.get(key)
        except KeyError:
            return dflt

    @abc.abstractmethod
    def set(self, key: str, value: T) -> None:
        """Unconditionally set ``value`` for the given ``key``.

        .. warning::

            The backing store doesn't actually have to save anything here. So
            setting a value and getting it directly after can still result in a
            ``KeyError``.

        :param key: The key to set.
        :param value: The value to set the given ``key`` to.

        :returns: Nothing.
        """
        raise NotImplementedError

    def get_or_set(
        self, key: str, get_value: t.Callable[[], T], *, force: bool = False
    ) -> T:
        """Set the ``key`` to the value procured by ``get_value`` if it is not
        present.

        :param key: The key to get or set.
        :param get_value: The method called if the ``key`` was not found. Its
            result is set as the value.
        :param force: If set to true the ``get_value`` method will always be
            called, and the result will be stored.

        :returns: The found or produced value.
        """
        found: t.Union[T, Literal[NotSetType.token]]
        if force:
            found = NotSetType.token
        else:
            found = self.get_or(key, NotSetType.token)

        if found is NotSetType.token:
            # It is important that we return `value` at the end, not only
            # because it is faster, but also because the cache makes not
            # guarantees about actually saving the key.
            found = get_value()
            self.set(key, found)
        else:
            logger.info('Found key in cache', key=key)
        return found


# Pylint bug: https://github.com/PyCQA/pylint/issues/2822
# pylint: disable=unsubscriptable-object
class RedisBackend(Backend[T], t.Generic[T]):
    """A cache backend using Redis as backing storage.
    """

    def __init__(
        self, namespace: str, ttl: timedelta, redis: redis_module.Redis
    ) -> None:
        """Create a new Redis backend.

        :param namespace: The namespace in which to store the values.
        :param ttl: The time after which a value set should expire.
        :param redis: The redis connection to use.
        """
        super().__init__(namespace=namespace, ttl=ttl)
        self._redis = redis

    def get(self, key: str) -> T:
        """Get a value from the backend.

        .. seealso:: method :meth:`Backend.get`
        """
        found = self._redis.get(self._make_key(key))

        if found is None:
            raise KeyError(key)

        return json.loads(found)

    def clear(self, key: str) -> None:
        """Clear the given ``key`` from the cache.

        .. seealso:: method :meth:`.Backend.clear`
        """
        self._redis.delete(self._make_key(key))

    def set(self, key: str, value: T) -> None:
        """Set a value with for a given ``key``.

        .. seealso:: method :meth:`Backend.set`
        """
        self._redis.set(
            name=self._make_key(key),
            value=json.dumps(value),
            px=round(self._ttl.total_seconds() * 1000),
        )
