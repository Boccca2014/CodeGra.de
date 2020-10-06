import os
import sys
from contextlib import nullcontext

import flask
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--postgresql",
            action="store",
            default=False,
            help="Run the test using postresql"
        )
    except ValueError:
        pass


@pytest.fixture
def maybe_raises():
    def fun(raises, exc):
        if raises:
            return pytest.raises(exc)
        return nullcontext()

    yield fun


@pytest.fixture
def schema_mock():
    class _Mock:
        def simple_type_to_open_api_type(self, typ):
            return ('Convert', typ)

        def make_comment(self, comment):
            return ('Comment', comment)

        def add_schema(self, schema):
            return ('Add Schema', schema)

    yield _Mock()
