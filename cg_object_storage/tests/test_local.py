import os
import tempfile

import pytest

from cg_object_storage import LocalStorage


@pytest.fixture
def storage_type():
    yield LocalStorage


@pytest.mark.parametrize('amount', [101, 100000])
def test_put_by_stream(storage, storage_location, make_content, amount):
    with tempfile.TemporaryFile() as named_temp:
        # 100 is the limit so that should be allowed
        content = make_content(amount)
        named_temp.write(content)
        named_temp.flush()
        named_temp.seek(0)

        with storage.putter() as p:
            result = p.from_stream(named_temp, max_size=100)
            assert result.is_nothing
            assert not os.listdir(storage_location)

