import io

import pytest

from cg_object_storage.utils import CopyResult, exact_copy, limited_copy


def test_limited_copy_success():
    dst = io.BytesIO()
    result = limited_copy(io.BytesIO(b'1234567890'), dst, 15)
    assert result == CopyResult(complete=True, amount=10)
    assert dst.seek(0) == 0
    assert dst.read() == b'1234567890'


def test_limited_copy_too_large():
    dst = io.BytesIO()
    result = limited_copy(io.BytesIO(b'1234567890'), dst, 5, bufsize=1)
    assert result == CopyResult(complete=False, amount=5)


def test_exact_copy_equal():
    dst = io.BytesIO()
    result = exact_copy(io.BytesIO(b'12345'), dst, 5, bufsize=2)
    assert result == CopyResult(complete=True, amount=5)
    dst.seek(0)
    assert dst.read() == b'12345'


def test_exact_copy_too_much_data():
    dst = io.BytesIO()
    result = exact_copy(io.BytesIO(b'123456'), dst, 5, bufsize=2)
    assert result == CopyResult(complete=True, amount=5)
    dst.seek(0)
    assert dst.read() == b'12345'


@pytest.mark.parametrize('bufsize', list(range(1, 10)))
def test_exact_copy_too_little_data(bufsize):
    dst = io.BytesIO()
    result = exact_copy(io.BytesIO(b'1234'), dst, 5, bufsize=bufsize)
    assert not result.complete
