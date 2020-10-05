import enum

import pytest

from cg_request_args import EnumValue, StringEnum, SimpleParseError


def test_string_enum():
    parser = StringEnum('a', 'b')
    assert parser.try_parse('a') == 'a'
    assert parser.try_parse('b') == 'b'

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse(5)
    assert 'which is of type int, not string' in str(exc.value)

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse('ab')
    assert "An Enum['a', 'b'] is required, but got 'ab'." == str(exc.value)


def test_normal_enum():
    class A(enum.Enum):
        a = 1
        b = 'str'

    parser = EnumValue(A)

    assert parser.try_parse('a') is A.a
    assert parser.try_parse('b') is A.b

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse(1)
    assert 'which is of type int, not string' in str(exc.value)

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse('str')
    assert "An Enum['a', 'b'] is required, but got 'str'." == str(exc.value)
