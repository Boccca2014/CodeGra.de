import os
import sys
import secrets
import tempfile

import flask
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from cg_object_storage import LocalFile, LocalStorage  # isort: skip


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
def storage_location():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture(params=[LocalStorage])
def storage_type(request):
    yield request.param


@pytest.fixture
def storage(storage_location, storage_type):
    yield storage_type(storage_location)


@pytest.fixture
def make_content():
    yield lambda amount: secrets.token_bytes(amount)
