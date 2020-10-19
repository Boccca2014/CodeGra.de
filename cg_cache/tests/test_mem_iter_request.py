from datetime import timedelta

import pytest
import freezegun

import cg_dt_utils
import cg_cache.inter_request as c


def test_simple_cases():
    cache = c.MemoryBackend('test', timedelta(minutes=1))
    with pytest.raises(KeyError):
        cache.get('5')
    obj = object()
    cache.set('5', obj)
    assert cache.get('5') is obj

    # Can clear key not in cache
    cache.clear('6')

    cache.clear('5')
    with pytest.raises(KeyError):
        cache.get('5')


def test_redis_get_expired():
    cache = c.MemoryBackend('test', timedelta(minutes=1))
    obj = object()
    cache.set('5', obj)
    assert cache.get('5') is obj

    with freezegun.freeze_time(timedelta(seconds=5)):
        assert cache.get('5') is obj
    with freezegun.freeze_time(timedelta(minutes=5)):
        with pytest.raises(KeyError):
            assert cache.get('5') is obj
