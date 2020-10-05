import typing as t

import pytest
from typing_extensions import Literal, TypedDict

from cg_request_args import BaseFixedMapping, MultipleParseErrors


class Simple(TypedDict):
    a: int
    b: t.Optional[str]
    c: float


class NonTotal(TypedDict, total=False):
    a: int


class Difficult(TypedDict):
    nested: Simple
    nested_in_list: t.List[Simple]
    lookup: t.Dict[str, int]
    d: t.Union[str, int]
    e: Literal['b']
    f: t.Any


def test_simple_base(schema_mock):
    map1 = BaseFixedMapping.from_typeddict(Simple)
    assert map1.try_parse({
        'a': 5,
        'b': 'not_none',
        'c': 5.0,
        'd': 'ignored',
    }) == {
        'a': 5,
        'b': 'not_none',
        'c': 5.0,
    }

    assert map1.try_parse({
        'a': 5,
        'b': None,
        'c': 5.0,
    }) == {
        'a': 5,
        'b': None,
        'c': 5.0,
    }

    with pytest.raises(MultipleParseErrors) as err:
        map1.try_parse({'a': 5, 'c': 1.0})
    assert '"b" an Union[None, str] is required, but' in str(err.value)

    map1.to_open_api(schema_mock) == ('Add Schema', Simple)


def test_difficult(schema_mock):
    map1 = BaseFixedMapping.from_typeddict(Difficult)
    res = {
        'nested': {'a': 0, 'b': '', 'c': 1},
        'nested_in_list': [],
        'lookup': {'5': 3},
        'd': 'str',
        'e': 'b',
        'f': None,
    }
    assert map1.try_parse(res) == res

    with pytest.raises(MultipleParseErrors) as err:
        map1.try_parse({})
    print(err.value)
    assert '"nested" a Mapping[' in str(err.value)
    assert '"nested_in_list" a List[' in str(err.value)
    assert '"lookup" a Mapping[' in str(err.value)

    map1.to_open_api(schema_mock) == ('Add Schema', Difficult)


def test_non_total():
    map1 = BaseFixedMapping.from_typeddict(NonTotal)
    assert map1.try_parse({}) == {}
    assert map1.try_parse({'a': 5}) == {'a': 5}
    assert map1.try_parse({'a': 5, 'b': 'd'}) == {'a': 5}
