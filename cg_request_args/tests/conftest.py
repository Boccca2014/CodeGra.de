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
    yield lambda raises, exc: pytest.raises(exc) if raises else nullcontext()
