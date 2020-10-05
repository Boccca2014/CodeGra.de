from cg_request_args import AnyValue


def test_any():
    obj = object()
    assert AnyValue().try_parse(obj) is obj
