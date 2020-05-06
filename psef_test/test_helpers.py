import enum
import random
from multiprocessing.sharedctypes import Value

import pytest

import psef.helpers as h
from psef.helpers import RepeatedTimer, defer
from psef.exceptions import APIException


def test_broker_session(monkeypatch):
    with h.BrokerSession('', '', 'http://www.mocky.io') as ses:
        assert ses.get('/v2/5d9e5e71320000c532329d38').json() == {'code': 5}


def test_defer():
    lst = []
    with defer(lambda: lst.append(2), lambda: lst.append(1)):
        lst.append(3)
    assert lst == [3, 2, 1]

    lst = []
    with defer(lambda: lst.append(1)), defer(lambda: lst.append(2)):
        lst.append(3)
    assert lst == [3, 2, 1]

    i = 0

    def inc():
        nonlocal i
        i += 1

    with pytest.raises(ZeroDivisionError):
        with defer(inc, lambda: 1 / 0, inc, inc, inc):
            pass
    assert i == 4


def test_repeated_timer(monkeypatch):
    i = Value('i', 0)
    crashes = Value('i', 0)

    def inc():
        assert random.random() > 0.5
        i.value += 1

    def on_crash(msg, exc_info):
        crashes.value += 1

    monkeypatch.setattr(h.logger, 'warning', on_crash)

    with RepeatedTimer(0.001, inc, cleanup=lambda: 1 / 0):
        # Even when we don't sleep the function is run
        while i.value < 100:
            for _ in range(10):
                pass

    assert crashes.value > 0
    assert i.value < 150
    assert i.value >= 100


def test_ensure_keys_in_dict():
    class Enum1(enum.Enum):
        a = 1
        b = '2'

    class Enum2(enum.Enum):
        a = '4'
        c = 5

    h.ensure_keys_in_dict({'hello': 'a'}, [('hello', Enum1)])
    h.ensure_keys_in_dict({'hello': 'a'}, [('hello', Enum2)])

    with pytest.raises(APIException) as err:
        h.ensure_keys_in_dict({'hello': 'b'}, [('hello', Enum2)])

    assert 'should be a member of' in err.value.description
    assert '(= a, c)' in err.value.description

    with pytest.raises(APIException) as err:
        h.ensure_keys_in_dict({'hello': 'c'}, [('hello', Enum1)])

    assert 'should be a member of' in err.value.description
    assert '(= a, b)' in err.value.description


def test_get_from_map_transaction():
    class Enum1(enum.Enum):
        a = 1
        b = '2'

    class Enum2(enum.Enum):
        a = '4'
        c = 5

    _missing = object()
    with h.get_from_map_transaction({'e1': 'a', 'e2': 'a',
                                     'fl': 5.0}) as [get, opt_get]:
        e1 = get('e1', Enum1)
        e2 = get('e2', Enum2)
        fl = get('fl', float)
        missing = opt_get('e3', float, _missing)

    assert e1 == Enum1.a
    assert e2 == Enum2.a
    assert e1 != e2
    assert fl == 5.0
    assert missing is _missing
