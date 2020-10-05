from cg_request_args import AnyValue


def test_any(schema_mock):
    obj = object()
    assert AnyValue().try_parse(obj) is obj
    assert AnyValue().to_open_api(schema_mock) == {'type': 'object'}
    assert AnyValue().describe() == 'Any'
