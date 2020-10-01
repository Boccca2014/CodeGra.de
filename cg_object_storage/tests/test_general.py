import os
import secrets
import tempfile

import pytest

from cg_maybe import Just


def test_copy_put_by_file(storage, make_content):
    with tempfile.NamedTemporaryFile() as named_temp:
        content = make_content(1000)
        named_temp.write(content)
        named_temp.flush()

        with storage.putter() as p:
            result = p.from_file(named_temp.name, move=False)
            # Can find and read before context manager has completed
            found = storage.get(result.name)
            assert os.path.isfile(named_temp.name)
            assert found.is_just
            assert found.value.name == result.name

            with found.value.open() as opened:
                assert opened.read() == content

        # Is also there after it has completed
        assert os.path.isfile(named_temp.name)
        with storage.get(result.name).value.open() as opened:
            assert opened.read() == content


def test_move_put_by_file(storage, make_content):
    with tempfile.NamedTemporaryFile(delete=False) as named_temp:
        content = make_content(1000)
        named_temp.write(content)
        named_temp.flush()

        with storage.putter() as p:
            result = p.from_file(named_temp.name, move=True)
            # Can find and read before context manager has completed
            found = storage.get(result.name)
            assert not os.path.isfile(named_temp.name)
            assert found.is_just
            assert found.value.name == result.name

            with found.value.open() as opened:
                assert opened.read() == content

        # Is also there after it has completed
        assert not os.path.isfile(named_temp.name)
        with storage.get(result.name).value.open() as opened:
            assert opened.read() == content


def test_put_by_string(storage):
    with storage.putter() as p:
        result = p.from_string('hello\n')
        found = storage.get(result.name)
        assert found.is_just
        assert found.value.name == result.name

        with found.value.open() as opened:
            assert opened.read() == b'hello\n'


def test_put_by_stream(storage, make_content):
    with tempfile.TemporaryFile() as named_temp:
        # 100 is the limit so that should be allowed
        content = make_content(100)
        named_temp.write(content)
        named_temp.flush()
        named_temp.seek(0)

        with storage.putter() as p:
            result = p.from_stream(named_temp, max_size=100)
            assert result.is_just
            # Can find and read before context manager has completed
            found = storage.get(result.value.name)
            assert found.is_just
            assert found.value.name == result.value.name
            assert found.value.name

            with found.value.open() as opened:
                assert opened.read() == content

        # Is also there after it has completed
        with storage.get(result.value.name).value.open() as opened:
            assert opened.read() == content


@pytest.mark.parametrize('amount', [101, 100000])
def test_put_by_stream_too_large(storage, make_content, amount):
    with tempfile.TemporaryFile() as named_temp:
        # 100 is the limit so that should be allowed
        content = make_content(amount)
        named_temp.write(content)
        named_temp.flush()
        named_temp.seek(0)

        with storage.putter() as p:
            result = p.from_stream(named_temp, max_size=100)
            assert result.is_nothing


@pytest.mark.parametrize('amount', [101, 100000])
def test_put_by_stream_limited_too_large(storage, make_content, amount):
    with tempfile.TemporaryFile() as named_temp:
        # 100 is the limit so that should be allowed
        content = make_content(amount)
        named_temp.write(content)
        named_temp.flush()
        named_temp.seek(0)

        with storage.putter() as p:
            result = p.from_stream(named_temp, max_size=100, size=Just(100))
            assert result.is_just

            with result.value.open() as opened:
                assert opened.read() == content[:100]

            result2 = p.from_stream(named_temp, max_size=100, size=Just(1001))
            assert result2.is_nothing


def test_rollback(storage, make_content):
    with tempfile.NamedTemporaryFile() as named_temp:
        named_temp.write(make_content(20))
        named_temp.flush()
        named_temp.seek(0)

        class StopPutter(Exception):
            pass

        with pytest.raises(StopPutter), storage.putter() as p:
            res = [
                p.from_string('hello\n').name,
                p.from_file(named_temp.name, move=False).name,
                p.from_stream(named_temp, max_size=100).value.name,
            ]
            for opt in res:
                assert storage.get(opt).is_just

            raise StopPutter

        assert len(res) == 3
        for opt in res:
            assert storage.get(opt).is_nothing


@pytest.mark.parametrize(
    'name',
    [
        '..',
        '.',
        '../../../../../etc/passwd',
        '//etc/passwd',
        'non_existing',
    ],
)
def test_get_non_existing(storage, name):
    assert storage.get(name).is_nothing
