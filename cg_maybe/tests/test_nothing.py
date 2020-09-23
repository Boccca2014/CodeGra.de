import pytest

from cg_maybe import Nothing


def test_map():
    assert Nothing.map(lambda x: x * x) is Nothing


def test_unsafe_extract():
    with pytest.raises(AssertionError):
        Nothing.unsafe_extract()


def test_or_default():
    obj = object()
    assert Nothing.or_default(obj) is obj


def test_if_just():
    called = False

    def call():
        nonlocal called
        called = True

    Nothing.if_just(call)
    assert not called
