import os
import sys

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
