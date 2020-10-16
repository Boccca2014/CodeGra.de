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
import sqlalchemy
from typing_extensions import Literal, Protocol

import cg_dt_utils
import cg_sqlalchemy_helpers
import cg_sqlalchemy_helpers.mixins
from cg_sqlalchemy_helpers.types import MySession, FilterColumn

logger = structlog.get_logger()

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from cg_sqlalchemy_helpers.types import Base as _DBBase


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
    __slots__ = ('_namespace', '_ttl')

    def __init__(self, namespace: str, ttl: timedelta) -> None:
        self._namespace = namespace
        self._ttl = ttl

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

    def cached_call(
        self,
        key: str,
        *,
        get_value: t.Callable[[], T],
        callback: t.Callable[[T], Y],
    ) -> Y:
        value = self.get_or_set(key=key, get_value=get_value, force=False)
        try:
            return callback(value)
        except:  # pylint: disable=bare-except
            logger.info(
                'Callback failed, clearing cache and trying again',
                exc_info=True
            )
            self.clear(key=key)
            value = self.get_or_set(key=key, get_value=get_value, force=True)
            return callback(value)


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

    def _make_key(self, key: str) -> str:
        return f'{self._namespace}/{key}'

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


class _IDBStorage(Protocol):
    @classmethod
    def get_non_expired(
        cls,
        *,
        session: MySession,
        namespace: str,
        key: str,
    ) -> t.Optional[t.Any]:
        ...

    @classmethod
    def delete_non_expired(
        cls,
        *,
        session: MySession,
        namespace: str,
        key: str,
    ) -> None:
        ...

    @classmethod
    def make_and_add(
        cls,
        *,
        session: MySession,
        namespace: str,
        key: str,
        value: t.Any,
        ttl: timedelta,
    ) -> '_IDBStorage':
        ...


# Pylint bug: https://github.com/PyCQA/pylint/issues/2822
# pylint: disable=unsubscriptable-object
class DBBackend(Backend[T], t.Generic[T]):
    """A cache backend using Redis as backing storage.
    """

    @staticmethod
    def make_cache_table(
        base: t.Type[cg_sqlalchemy_helpers.types.Base],
        tablename: str,
    ) -> t.Type[_IDBStorage]:
        if not t.TYPE_CHECKING:
            _DBBase = base  # pylint: disable=invalid-name

        class _Storage(
            _DBBase,
            cg_sqlalchemy_helpers.mixins.TimestampMixin,
            cg_sqlalchemy_helpers.mixins.IdMixin,
        ):
            __tablename__ = tablename

            ttl = cg_sqlalchemy_helpers.Column(
                'expires',
                cg_sqlalchemy_helpers.Interval,
                nullable=False,
            )
            namespace = cg_sqlalchemy_helpers.Column(
                'namespace',
                cg_sqlalchemy_helpers.Unicode,
                nullable=False,
            )
            key = cg_sqlalchemy_helpers.Column(
                'key',
                cg_sqlalchemy_helpers.Unicode,
                nullable=False,
            )
            value = cg_sqlalchemy_helpers.Column(
                'value',
                cg_sqlalchemy_helpers.JSONB,
                nullable=False,
                index=False,
            )

            __table_args__ = (
                sqlalchemy.Index('namespace_key_index', key, namespace),
            )

            @classmethod
            def _get_non_expired_filter(cls) -> FilterColumn:
                return (
                    cg_sqlalchemy_helpers.func.now() < cls.created_at + cls.ttl
                )

            @classmethod
            def get_non_expired(
                cls,
                *,
                session: MySession,
                namespace: str,
                key: str,
            ) -> t.Optional[t.Any]:
                return session.query(cls).filter(
                    cls._get_non_expired_filter(),
                    cls.namespace == namespace,
                    cls.key == key,
                ).order_by(
                    cls.created_at.desc(),
                ).with_entities(
                    cls.value,
                ).limit(1).scalar()

            @classmethod
            def delete_non_expired(
                cls,
                *,
                session: MySession,
                namespace: str,
                key: str,
            ) -> None:
                session.query(cls).filter(
                    cls._get_non_expired_filter(),
                    cls.namespace == namespace,
                    cls.key == key,
                ).delete(synchronize_session='fetch')
                session.flush()

            @classmethod
            def make_and_add(
                cls,
                *,
                session: cg_sqlalchemy_helpers.types.MySession,
                namespace: str,
                key: str,
                value: t.Any,
                ttl: timedelta,
            ) -> '_IDBStorage':
                res = cls(namespace=namespace, key=key, value=value, ttl=ttl)
                session.add(res)
                session.flush()
                return res

        return _Storage

    def __init__(
        self,
        namespace: str,
        ttl: timedelta,
        get_session: t.Callable[[], cg_sqlalchemy_helpers.types.MySession],
        get_storage: t.Callable[[], t.Type[_IDBStorage]],
    ) -> None:
        """Create a new database backend.

        """
        super().__init__(namespace=namespace, ttl=ttl)
        self._get_storage = get_storage
        self._get_session = get_session

    def get(self, key: str) -> T:
        """Get a value from the backend.

        .. seealso:: method :meth:`Backend.get`
        """
        value = self._get_storage().get_non_expired(
            session=self._get_session(),
            namespace=self._namespace,
            key=key,
        )
        if value is None:
            raise KeyError(key)
        else:
            return value

    def clear(self, key: str) -> None:
        """Clear the given ``key`` from the cache.

        .. seealso:: method :meth:`.Backend.clear`
        """
        self._get_storage().delete_non_expired(
            session=self._get_session(),
            namespace=self._namespace,
            key=key,
        )

    def set(self, key: str, value: T) -> None:
        """Set a value with for a given ``key``.

        .. seealso:: method :meth:`Backend.set`
        """
        self._get_storage().make_and_add(
            session=self._get_session(),
            key=key,
            namespace=self._namespace,
            value=value,
            ttl=self._ttl,
        )


class MemoryBackend(Backend[T], t.Generic[T]):
    """A cache backend using an in memory dictionary as backing storage.


    .. warning::

        This cache should only be used when testing, not in production!
    """

    def __init__(self, namespace: str, ttl: timedelta) -> None:
        """Create a new Redis backend.

        :param namespace: The namespace in which to store the values.
        :param ttl: The time after which a value set should expire.
        """
        super().__init__(namespace=namespace, ttl=ttl)
        self._storage: t.Dict[str, t.Tuple[T, cg_dt_utils.
                                           DatetimeWithTimezone]] = {}

    def _make_key(self, key: str) -> str:
        return f'{self._namespace}/{key}'

    def get(self, key: str) -> T:
        """Get a value from the backend.

        .. seealso:: method :meth:`Backend.get`
        """
        found, expired = self._storage[key]
        if expired < cg_dt_utils.DatetimeWithTimezone.utcnow():
            raise KeyError(key)

        return found

    def clear(self, key: str) -> None:
        """Clear the given ``key`` from the cache.

        .. seealso:: method :meth:`.Backend.clear`
        """
        self._storage.pop(key, None)

    def set(self, key: str, value: T) -> None:
        """Set a value with for a given ``key``.

        .. seealso:: method :meth:`Backend.set`
        """
        self._storage[key] = (
            value,
            cg_dt_utils.DatetimeWithTimezone.utcnow() + self._ttl,
        )
