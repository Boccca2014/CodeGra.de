from datetime import timedelta

import pytest

from cg_dt_utils import DatetimeWithTimezone
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
def test_number_gte(ok, value, minimum, maybe_raises, schema_mock):
    parser = RichValue.NumberGte(minimum)
    with maybe_raises(not ok, SimpleParseError):
        parser.try_parse(value)

    assert parser.to_open_api(schema_mock) == {
        'type': ('Convert', int),
        'minimum': minimum,
    }


def test_password(schema_mock):
    parser = RichValue.Password
    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse(5)

    assert 'REDACTED' in str(exc.value)
    assert '5' not in str(exc.value)

    assert parser.try_parse('hunter2') == 'hunter2'

    assert parser.to_open_api(schema_mock) == {
        'type': ('Convert', str),
        'format': 'password',
    }


def test_datetime():
    parser = RichValue.DateTime
    now = DatetimeWithTimezone.utcnow()
    assert parser.try_parse(now.isoformat()) == now
    assert parser.try_parse(now.isoformat().replace('+00:00', 'Z')) == now

    assert (
        parser.try_parse(
            now.isoformat().replace('+00:00', '+01:00'),
        ) == now - timedelta(hours=1)
    )

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse('2020-10-02 0')
    assert "which can't be parsed as a valid datetime" in str(exc.value)
    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse('now')
    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse('yesterday')
