import pytest

from cg_request_args import (
    SimpleValue, FixedMapping, OptionalArgument, RequiredArgument,
    SimpleParseError, MultipleParseErrors
)


def test_simple_parse_success():
    map1 = FixedMapping(
        RequiredArgument('a', SimpleValue.int, ''),
        RequiredArgument('b', SimpleValue.str, ''),
        OptionalArgument('c', SimpleValue.bool, ''),
    )
    res = map1.try_parse({'a': 5, 'b': 'hello'})
    assert res.a == 5
    assert res.b == 'hello'
    # Is present when not given but simply a Nothing
    assert res.c.is_nothing

    res = map1.try_parse({'a': 10, 'b': 'bye', 'c': True})
    assert res.a == 10
    assert res.b == 'bye'
    # Is present as a Maybe
    assert res.c.unsafe_extract() is True


def test_dict_getter_unknown_attr():
    map1 = FixedMapping(RequiredArgument('a', SimpleValue.int, ''), )
    res = map1.try_parse({'a': 0})
    assert res.a == 0
    with pytest.raises(AttributeError):
        _ = res.b


def test_simple_parse_failure():
    map1 = FixedMapping(
        RequiredArgument('a', SimpleValue.int, ''),
        RequiredArgument('b', SimpleValue.str, ''),
        OptionalArgument('c', SimpleValue.bool, ''),
    )
    with pytest.raises(SimpleParseError):
        map1.try_parse('not a dict')

    with pytest.raises(MultipleParseErrors) as err:
        map1.try_parse({'a': 5, 'c': True})
    assert 'at index "b" a str is required, but got Nothing' in str(err.value)

    with pytest.raises(MultipleParseErrors) as err:
        map1.try_parse({'a': 5, 'b': 'a string', 'c': 'not a bool'})
    msg = str(err.value)
    assert "at index \"c\" a bool is required, but got 'not a bool'" in msg


def test_parse_with_tag(schema_mock):
    map1 = FixedMapping(
        RequiredArgument('value', SimpleValue.str, ''),
    ).add_tag('tag', 'tag_value')

    res = map1.try_parse({'value': 'str'})
    assert res.value == 'str'
    assert res.tag == 'tag_value'

    # Tag is never copied from data
    res = map1.try_parse({'value': 'str', 'tag': 'another value'})
    assert res.value == 'str'
    assert res.tag == 'tag_value'

    # Tag does not show up in schema
    assert map1.to_open_api(schema_mock) == {
        'type': 'object',
        'properties': {
            'value': {
                'description': ('Comment', ''),
                'type': ('Convert', str),
            },
        },
        'required': ['value'],
    }


def test_combine(schema_mock):
    map1 = FixedMapping(
        RequiredArgument('value1', SimpleValue.str, 'desc1'),
        OptionalArgument('value2', SimpleValue.int, 'desc2')
    )
    map2 = FixedMapping(RequiredArgument('value3', SimpleValue.bool, 'desc3'))
    map3 = map1.combine(map2)

    res = map3.try_parse({'value1': 'value1', 'value2': 100, 'value3': True})
    assert res.value1 == 'value1'
    assert res.value2.unsafe_extract() == 100
    assert res.value3 is True

    assert map3.to_open_api(schema_mock) == {
        'type': 'object',
        'properties': {
            'value1': {
                'description': ('Comment', 'desc1'),
                'type': ('Convert', str),
            },
            'value2': {
                'description': ('Comment', 'desc2'),
                'type': ('Convert', int),
            },
            'value3': {
                'description': ('Comment', 'desc3'),
                'type': ('Convert', bool),
            },
        },
        'required': ['value1', 'value3'],
    }
