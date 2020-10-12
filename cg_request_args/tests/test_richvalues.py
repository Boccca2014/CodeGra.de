import uuid
from datetime import timedelta

import pytest

import cg_object_storage
from cg_dt_utils import DatetimeWithTimezone
from cg_request_args import RichValue, SimpleValue, SimpleParseError


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
def test_email_list(ok, value, maybe_raises, schema_mock):
    parser = RichValue.EmailList
    with maybe_raises(not ok, SimpleParseError) as maybe_exc:
        parser.try_parse(value)

    if not ok:
        exc = maybe_exc.value
        if isinstance(value, str):
            assert 'A str as email list' in str(exc)

    assert parser.to_open_api(schema_mock) == {'type': ('Convert', str)}


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
def test_int_value_gte(ok, value, minimum, maybe_raises, schema_mock):
    parser = RichValue.ValueGte(SimpleValue.int, minimum)
    with maybe_raises(not ok, SimpleParseError) as maybe_exc:
        parser.try_parse(value)
    if not ok:
        exc = maybe_exc.value
        if isinstance(value, int):
            assert 'An int larger than {}'.format(minimum) in str(exc)
        else:
            assert 'An int is required, but got' in str(exc)

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


def test_datetime(schema_mock):
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
    assert str(
        exc.value
    ).startswith("A DateTime as str is required, but got 'yesterday'")

    assert parser.to_open_api(schema_mock) == {
        'type': ('Convert', str),
        'format': 'date-time',
    }


def test_uuid(schema_mock):
    parser = RichValue.UUID
    val = uuid.uuid4()
    assert parser.try_parse(str(val)) == val
    assert parser.try_parse(val.hex) == val

    with pytest.raises(SimpleParseError) as exc:
        parser.try_parse('Not a uuid')
    assert "which can't be parsed as a valid uuid" in str(exc.value)

    assert parser.to_open_api(schema_mock) == {
        'type': ('Convert', str),
        'format': 'uuid',
    }


def test_timedelta_from_int(schema_mock):
    assert RichValue.TimeDelta.try_parse(5).total_seconds() == 5
    assert RichValue.TimeDelta.try_parse(-10).total_seconds() == -10
    assert RichValue.TimeDelta.try_parse(60) == timedelta(minutes=1)

    assert RichValue.TimeDelta.to_open_api(schema_mock) == {
        'anyOf': [
            {'type': ('Convert', int)},
            {
                'type': ('Convert', str),
                'format': 'time-delta',
            },
        ],
    }


def test_timedelta_simple_string_duration():
    assert RichValue.TimeDelta.try_parse('PT15M') == timedelta(minutes=15)
    assert RichValue.TimeDelta.try_parse('-PT15M') == timedelta(minutes=-15)
    assert RichValue.TimeDelta.try_parse('P15D') == timedelta(days=15)
    assert RichValue.TimeDelta.try_parse('P15DT01S') == timedelta(
        days=15, seconds=1
    )
    assert RichValue.TimeDelta.try_parse('P1DT1S') == timedelta(
        days=1, seconds=1
    )

    with pytest.raises(SimpleParseError) as exc:
        RichValue.TimeDelta.try_parse('PINVALID')
    assert 'TimeDelta as Union[str, float]' in str(exc.value)


def test_filesize(schema_mock):
    assert RichValue.FileSize.try_parse(
        '5kb',
    ) == cg_object_storage.FileSize(5 * 1 << 10)
    assert RichValue.FileSize.try_parse(
        '5b',
    ) == cg_object_storage.FileSize(5)
    assert RichValue.FileSize.try_parse(
        '5mb',
    ) == cg_object_storage.FileSize(5 * 1 << 20)

    with pytest.raises(SimpleParseError):
        RichValue.FileSize.try_parse(5)

    with pytest.raises(SimpleParseError) as exc:
        RichValue.FileSize.try_parse('5tb')
    assert 'FileSize' in str(exc.value)

    assert RichValue.FileSize.to_open_api(schema_mock) == {
        'type': ('Convert', str),
        'pattern': r'^\d+(k|m|g)?b$',
    }
