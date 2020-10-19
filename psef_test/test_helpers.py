import enum
import random
from multiprocessing.sharedctypes import Value

import pytest

import psef.helpers as h
from cg_register import Register
from psef.helpers import RepeatedTimer, defer, deep_get, try_for_every
from psef.exceptions import APIException


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


def test_try_for_every():
    calls = []

    class MyError(Exception):
        pass

    def asserts_is_not_one(value):
        calls.append(value)
        if value == 1:
            raise MyError

    try_for_every([2, 1], asserts_is_not_one)
    assert calls == [2]

    calls.clear()
    try_for_every([1, 1, 2, 3], asserts_is_not_one)
    assert calls == [1, 1, 2]

    calls.clear()
    with pytest.raises(MyError):
        try_for_every([1, 1, 1], asserts_is_not_one)
    assert calls == [1, 1, 1]

    calls.clear()
    with pytest.raises(MyError):
        try_for_every([1], asserts_is_not_one, to_except=AssertionError)
    assert calls == [1]

    calls.clear()
    obj = object()
    try_for_every([obj], asserts_is_not_one, to_except=AssertionError)
    assert calls == [obj]
    assert calls[0] is obj

    def assert_no(_):
        assert False

    # Doesn't fail as the function is never called
    try_for_every([], assert_no)


def test_deep_get():
    obj1 = object()
    obj2 = object()
    obj3 = object()

    mapping = {
        '1': {
            '2': [4],
            '3': None,
            '4': {5: obj1},
        },
        '6': obj2,
    }

    assert deep_get(mapping, ['not_present', 'subkey'], obj3) is obj3
    assert deep_get(mapping, ['1', '2', 0], obj3) is obj3
    assert deep_get(mapping, ['6'], obj3) is obj2
    assert deep_get(mapping, ['1', '4', 5], obj3) is obj1
    assert deep_get(mapping, ['6', '6'], obj3) is obj3


def test_get_from_map_transaction_with_register():
    register = Register('Test')

    obj1 = object()
    register.register('val1')(obj1)
    register.register('val2')('Wow')

    with h.get_from_map_transaction({'k': 'val1'}) as [get, _]:
        res = get('k', register)

    assert res == ('val1', obj1)
    assert res[1] is obj1

    with pytest.raises(APIException) as exc:
        with h.get_from_map_transaction({'k': 'no_val'}) as [get, _]:
            res = get('k', register)

    assert 'TestRegister" (= val1, val2), was "no_val' in exc.value.description
