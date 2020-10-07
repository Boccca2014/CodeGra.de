import pytest

from cg_request_args import (
    List, SimpleValue, LookupMapping, SimpleParseError, MultipleParseErrors
)


def test_non_dict():
    mapping = LookupMapping(SimpleValue.str)

    with pytest.raises(SimpleParseError):
        mapping.try_parse('NOT A DICT')


def test_simple_mapping(schema_mock):
    mapping = LookupMapping(SimpleValue.str)

    inp = {'5': 'a key'}
    assert mapping.try_parse(inp) == inp
    assert mapping.try_parse(inp) is not inp

    with pytest.raises(MultipleParseErrors) as exc:
        # Keys have to be strings
        mapping.try_parse({5: 'a key'})
    assert len(exc.value.errors) == 1
    assert exc.value.errors[0].location == ['5']
    assert 'at index "5" a str is required, but got 5' in str(exc.value)

    with pytest.raises(MultipleParseErrors) as exc:
        # Values are also checked
        mapping.try_parse({'5': 'a key', 'wrong': None})
    assert len(exc.value.errors) == 1
    assert 'None' in str(exc.value)

    assert mapping.to_open_api(schema_mock) == {
        'type': 'object', 'additionalProperties': {'type': ('Convert', str)}
    }


def test_compound_values():
    mapping = LookupMapping(List(SimpleValue.str | SimpleValue.int))

    inp = {'5': [5, 'a']}
    assert mapping.try_parse(inp) == inp

    with pytest.raises(MultipleParseErrors) as exc:
        mapping.try_parse({'key': [5, 'd', {}]})
    assert len(exc.value.errors) == 1
    assert exc.value.errors[0].location == ["key"]
    assert isinstance(exc.value.errors[0], MultipleParseErrors)
    assert exc.value.errors[0].errors[0].location == [2]
    assert 'at index "2" an Union[str, int] is required' in str(exc.value)
