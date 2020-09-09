import os
import sys

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


@pytest.fixture(scope='session')
def app():
    import cg_cache.intra_request as c
    app = flask.Flask(__name__)
    c.init_app(app)
    yield app
