from datetime import timedelta

import pytest
import fakeredis

import cg_cache.inter_request as c


def make_error():
    assert False


class Redis(fakeredis.FakeStrictRedis):
    def __init__(self, mapping):
        super().__init__()
        self.calls = []
        for key, value in mapping.items():
            super().set(key, value)

    def get(self, *args, **kwargs):
        self.calls.append(('get', args, kwargs))
        return super().get(*args, **kwargs)

    def set(self, *args, **kwargs):
        self.calls.append(('set', args, kwargs))
        return super().set(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.calls.append(('delete', args, kwargs))
        return super().delete(*args, **kwargs)


def test_redis_get():
    ttl = object()
    redis = Redis({'namespace/existing': '[]'})
    cache = c.RedisBackend('namespace', ttl, redis)
    with pytest.raises(KeyError):
        cache.get('non_existing')

    assert len(redis.calls) == 1
    assert redis.calls.pop() == ('get', ('namespace/non_existing', ), {})

    assert cache.get('existing') == []

    obj = object()
    assert cache.get_or('non_existing', obj) is obj


def test_redis_get_or_set():
    ttl = timedelta(seconds=1)
    redis = Redis({'namespace/existing': '[]'})
    cache = c.RedisBackend('namespace', ttl, redis)

    assert cache.get_or_set('existing', make_error) == []
    assert len(redis.calls) == 1
    assert redis.calls.pop() == ('get', ('namespace/existing', ), {})

    assert cache.get_or_set('non_existing', lambda: 6) == 6
    assert redis.calls == [
        ('get', ('namespace/non_existing', ), {}),
        # ttl was set to 1 second so that is 1000ms
        (
            'set', (),
            {'name': 'namespace/non_existing', 'value': '6', 'px': 1000}
        ),
    ]


def test_redis_clear():
    ttl = timedelta(seconds=1)
    redis = Redis({'namespace/existing': '[6]'})
    cache = c.RedisBackend('namespace', ttl, redis)

    assert cache.get('existing') == [6]
    redis.calls.pop()

    cache.clear('existing')
    obj = object()
    assert cache.get_or('existing', obj) is obj
    assert redis.calls == [
        ('delete', ('namespace/existing', ), {}),
        ('get', ('namespace/existing', ), {}),
    ]
