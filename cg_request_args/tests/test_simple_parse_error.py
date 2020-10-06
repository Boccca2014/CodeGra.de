from cg_request_args import SimpleValue, SimpleParseError


def test_add_locations():
    err = SimpleParseError(SimpleValue.str, 5)
    err = err.add_location(5).add_location('b').add_location(4)
    assert err._loc_to_str() == '4.b[5]'
