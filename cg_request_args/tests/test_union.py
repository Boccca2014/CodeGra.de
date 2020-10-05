import pytest

from cg_request_args import (
    List, SimpleValue, SimpleParseError, MultipleParseErrors, _SimpleUnion
)


def test_simple_union():
    parser = SimpleValue(str) | SimpleValue(int)

    assert parser.try_parse('5') == '5'
    assert parser.try_parse(5) == 5
    assert parser.try_parse('hello a nice string') == 'hello a nice string'

    with pytest.raises(SimpleParseError):
        parser.try_parse(5.5)

    with pytest.raises(SimpleParseError):
        # Booleans are not allowed as integers
        parser.try_parse(True)


def test_simple_union_with_float():
    parser = SimpleValue(str) | SimpleValue(float)

    assert parser.try_parse(5.5) == 5.5
    # Ints are allowed but are cast to floats
    assert parser.try_parse(5) == 5.0


def test_larger_simple_union():
    parser = SimpleValue(str) | SimpleValue(float) | SimpleValue(bool)
    assert isinstance(parser._parser, _SimpleUnion)
    assert isinstance((SimpleValue(bool) | parser)._parser, _SimpleUnion)
    assert isinstance((parser | parser)._parser, _SimpleUnion)

    assert parser.try_parse('str') == 'str'
    assert parser.try_parse(5) == 5.0
    assert parser.try_parse(10.1) == 10.1
    assert parser.try_parse(True) is True


def test_rich_union():
    parser1 = List(SimpleValue(int)) | List(SimpleValue(str))
    parser2 = List(SimpleValue(int) | SimpleValue(str))

    for p in [parser1, parser2]:
        p.try_parse([1, 2]) == [1, 2]
        p.try_parse(['str', 'str']) == ['str', 'str']

    with pytest.raises(MultipleParseErrors) as err:
        parser1.try_parse([1, 'str'])

    parser2.try_parse([1, 'str']) == [1, 'str']
