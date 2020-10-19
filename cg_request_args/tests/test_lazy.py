from cg_request_args import Lazy, SimpleValue


def test_is_called_once():
    amount = 0

    def make():
        nonlocal amount
        amount += 1
        return SimpleValue.str

    parser = Lazy(make)
    assert parser.try_parse('5') == '5'
    assert parser.try_parse('6') == '6'
    assert amount == 1


def test_proxies_all_methods(schema_mock):
    parser = Lazy(lambda: SimpleValue.str)
    assert parser.describe() == SimpleValue.str.describe()
    assert parser.to_open_api(schema_mock
                              ) == SimpleValue.str.to_open_api(schema_mock)
