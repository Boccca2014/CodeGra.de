from cg_maybe import Just, Nothing


def test_map():
    assert Just(5).map(lambda x: x * x).value == 25


def test_unsafe_extract():
    just = Just(object())
    assert just.unsafe_extract() is just.value


def test_or_default():
    a, b = object(), object()
    just = Just(a)
    assert just.or_default(b) is a
    assert just.or_default(b) is not b


def test_if_just():
    called = False
    obj = object()

    def call(value):
        nonlocal called
        called = True
        assert value is obj

    Just(obj).if_just(call)
    assert called


def test_alt():
    just1 = Just(5)
    just2 = Just(6)

    assert just1.alt(just2) is just1
    assert just1.alt(Nothing) is just1
