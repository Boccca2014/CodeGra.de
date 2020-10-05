import pytest

from cg_request_args import SimpleValue, SimpleParseError


@pytest.mark.parametrize(
    'ok,value', [
        (True, ''),
        (True, 'HELLO'),
        (True, 'inf'),
        (True, 'NaN'),
        (False, 5),
        (False, False),
        (False, 5.5),
        (False, None),
    ]
)
def test_string_parser(ok, value, maybe_raises):
    parser = SimpleValue(str)
    with maybe_raises(not ok, SimpleParseError):
        res = parser.try_parse(value)
        assert isinstance(res, str)
        assert res == value


@pytest.mark.parametrize(
    'ok,value', [
        (False, ''),
        (False, 'HELLO'),
        (False, 't'),
        (False, '1'),
        (False, 5),
        (False, 5.5),
        (False, 1),
        (False, 0),
        (False, None),
        (True, False),
        (True, True),
    ]
)
def test_bool_parser(ok, value, maybe_raises):
    parser = SimpleValue(bool)
    with maybe_raises(not ok, SimpleParseError):
        res = parser.try_parse(value)
        assert isinstance(res, bool)
        assert res == value


@pytest.mark.parametrize(
    'ok,value', [
        (False, ''),
        (False, 'HELLO'),
        (False, 't'),
        (False, '1'),
        (False, None),
        (False, False),
        (False, True),
        (False, 5.5),
        (True, 5),
        (True, 1),
        (True, 0),
    ]
)
def test_int_parser(ok, value, maybe_raises):
    parser = SimpleValue(int)
    with maybe_raises(not ok, SimpleParseError):
        res = parser.try_parse(value)
        assert isinstance(res, int)
        assert res == value


@pytest.mark.parametrize(
    'ok,value',
    [
        (False, ''),
        (False, 'HELLO'),
        (False, 't'),
        (False, '1'),
        (False, None),
        (False, False),
        (False, True),
        (False, 'inf'),
        (False, 'NaN'),
        (True, 5.5),
        (True, -100.0),
        # We allow integers as floats as that makes using the API easier.
        (True, 5),
        (True, 1),
        (True, 0),
    ]
)
def test_float_parser(ok, value, maybe_raises):
    parser = SimpleValue(float)
    with maybe_raises(not ok, SimpleParseError):
        res = parser.try_parse(value)
        assert res == pytest.approx(value)
        assert isinstance(res, float)


@pytest.mark.parametrize('typ', [str, int, float, bool])
def test_to_open_api(schema_mock, typ):
    assert SimpleValue(typ).to_open_api(schema_mock) == {
        'type': ('Convert', typ)
    }
