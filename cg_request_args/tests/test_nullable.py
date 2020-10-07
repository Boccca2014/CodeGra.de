import pytest

from cg_request_args import Nullable, SimpleValue, SimpleParseError


def test_simple(schema_mock):
    inner = SimpleValue.str
    parser = Nullable(inner)

    with pytest.raises(SimpleParseError):
        inner.try_parse(None)

    assert parser.try_parse(None) is None
    assert parser.try_parse('str') == 'str'
    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse(5)
    assert str(exc.value) == 'An Union[None, str] is required, but got 5.'

    assert parser.to_open_api(schema_mock) == {
        'nullable': True,
        'type': ('Convert', str),
    }
