from datetime import timedelta

import cg_cache.inter_request as c


def test_cached_call():
    cache = c.MemoryBackend('test', timedelta(minutes=1))
    call_amount = 0
    obj = object()

    def raises(value):
        nonlocal call_amount
        call_amount += 1
        assert value == 2
        return obj

    cache.set('hel', 1)

    assert cache.cached_call(
        'hel', get_value=lambda: 2, callback=raises
    ) is obj
    assert call_amount == 2
