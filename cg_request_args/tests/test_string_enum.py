import pytest

from cg_request_args import StringEnum, SimpleParseError


def test_simple():
    parser = StringEnum('a', 'b')
    assert parser.try_parse('a') == 'a'
    assert parser.try_parse('b') == 'b'

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse(5)
    assert 'which is of type int, not string' in str(exc.value)

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse('ab')
    assert 'An Enum[a, b] is required, but got \'ab\'.' == str(exc.value)
