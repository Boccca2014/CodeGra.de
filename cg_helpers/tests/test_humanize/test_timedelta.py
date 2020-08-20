from datetime import timedelta

import pytest

from cg_helpers import humanize


@pytest.mark.parametrize(
    'delta,expected', [
        (timedelta(seconds=-4), '4 seconds ago'),
        (timedelta(seconds=-45), '45 seconds ago'),
        (timedelta(minutes=-1, seconds=-20), 'a minute ago'),
        (timedelta(minutes=-4, seconds=-50), '5 minutes ago'),
        (timedelta(minutes=-59), 'an hour ago'),
        (timedelta(days=-1, hours=-4), '28 hours ago'),
        (timedelta(days=-5), '5 days ago'),
        (timedelta(days=-5000000), '13661 years ago'),
    ]
)
def test_negative(delta, expected):
    assert humanize.timedelta(delta) == expected


@pytest.mark.parametrize(
    'delta,expected', [
        (timedelta(seconds=1), 'just now'),
        (timedelta(seconds=45), 'in 45 seconds'),
        (timedelta(minutes=1, seconds=20), 'in a minute'),
        (timedelta(minutes=4, seconds=50), 'in 5 minutes'),
        (timedelta(minutes=59), 'in an hour'),
        (timedelta(days=1, hours=4), 'in 28 hours'),
        (timedelta(days=5), 'in 5 days'),
    ]
)
def test_positive(delta, expected):
    assert humanize.timedelta(delta) == expected


@pytest.mark.parametrize(
    'delta,expected', [
        (timedelta(seconds=1), 'a few seconds'),
        (timedelta(seconds=45), '45 seconds'),
        (timedelta(minutes=1, seconds=20), 'a minute'),
        (timedelta(minutes=4, seconds=50), '5 minutes'),
        (timedelta(minutes=59), 'an hour'),
        (timedelta(days=1, hours=4), '28 hours'),
        (timedelta(days=5), '5 days'),
    ]
)
def test_no_prefi(delta, expected):
    assert humanize.timedelta(delta, no_prefix=True) == expected
    # Positive or negative does not matter here
    assert humanize.timedelta(-delta, no_prefix=True) == expected
