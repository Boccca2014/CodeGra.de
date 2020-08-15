import pytest

from cg_helpers import humanize


@pytest.mark.parametrize('input,expected', [
    (2.4 * 2 ** 20, '2.40MB'),
    (2.4444444 * 2 ** 20, '2.44MB'),
])
def test_rounding(input, expected):
    assert humanize.size(input) == expected


@pytest.mark.parametrize('input,expected', [
    (-1, '-1B'),
    (1023, '1023B'),
    (1024, '1KB'),
    (1024 * 1024, '1MB'),
])
def test_simple_inputs(input, expected):
    assert humanize.size(input) == expected
