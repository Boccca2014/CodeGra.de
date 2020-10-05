import pytest

from cg_request_args import (
    List, SimpleValue, SimpleParseError, MultipleParseErrors
)


def test_list():
    parser = List(SimpleValue(str))

    assert parser.try_parse([]) == []
    assert parser.try_parse(['str']) == ['str']
    assert parser.try_parse(['str', 'str2']) == ['str', 'str2']

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse('not a list')
    assert 'A List[str] is required, but got' in str(exc.value)

    with pytest.raises(MultipleParseErrors):
        parser.try_parse([5, 'str'])

    with pytest.raises(MultipleParseErrors):
        parser.try_parse(['str', 'st42', 5.5])
