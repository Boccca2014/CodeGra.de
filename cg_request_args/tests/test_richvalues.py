import pytest

from cg_request_args import RichValue, SimpleParseError


@pytest.mark.parametrize(
    'ok,value', [
        (False, 5),
        (False, 'not_an_email'),
        (False, '@codegrade.com'),
        (False, 'Thomas Schaper <>'),
        (False, 'Thomas Schaper <valid@codegrade.com>; noemail'),
        (True, 'thomas@codegrade.com'),
        (True, 'Thomas Schaper <valid@codegrade.com>'),
        (True, 'Thomas Schaper <valid@codegrade.com>, valid2@codegrade.com'),
    ]
)
def test_email_list(ok, value, maybe_raises):
    parser = RichValue.EmailList
    with maybe_raises(not ok, SimpleParseError):
        parser.try_parse(value)


@pytest.mark.parametrize(
    'ok,minimum,value', [
        (False, 10, 9),
        (False, -10, -11),
        (False, 10, -10),
        (False, 0, '10'),
        (True, 0, 10),
        (True, 10, 10),
        (True, 0, 10),
        (True, -10, 10),
    ]
)
def test_number_gte(ok, value, minimum, maybe_raises):
    parser = RichValue.NumberGte(minimum)
    with maybe_raises(not ok, SimpleParseError):
        parser.try_parse(value)


def test_password():
    parser = RichValue.Password
    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse(5)

    assert 'REDACTED' in str(exc.value)
    assert '5' not in str(exc.value)

    assert parser.try_parse('hunter2') == 'hunter2'
