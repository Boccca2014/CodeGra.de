import os
import abc
import subprocess

from code_quality_wrappers import Tester


class Flake8Tester(Tester):
    def run_test(self):
        return self.run_wrapper()

    @property
    def wrapper_name(self):
        return 'cg-flake8'


class Flake8ValidTester(Flake8Tester):
    @property
    def submission_archive(self):
        return 'test_flake8.tar.gz'

    @property
    def expected_output(self):
        return [
            {
                'origin': 'Flake8',
                'msg': 'indentation contains tabs',
                'code': 'W191',
                'severity': 'warning',
                'line': {'start': 2, 'end': 2},
                'column': {'start': 1, 'end': None},
                'path': ['test_flake8', 'test.py'],
            },
            {
                'origin': 'Flake8',
                'msg': "whitespace before '('",
                'code': 'E211',
                'severity': 'error',
                'line': {'start': 2, 'end': 2},
                'column': {'start': 7, 'end': None},
                'path': ['test_flake8', 'test.py'],
            },
            {
                'origin': 'Flake8',
                'msg': "whitespace after '('",
                'code': 'E201',
                'severity': 'error',
                'line': {'start': 2, 'end': 2},
                'column': {'start': 9, 'end': None},
                'path': ['test_flake8', 'test.py'],
            },
            {
                'origin': 'Flake8',
                'msg': "whitespace before ')'",
                'code': 'E202',
                'severity': 'error',
                'line': {'start': 2, 'end': 2},
                'column': {'start': 11, 'end': None},
                'path': ['test_flake8', 'test.py'],
            },
        ]


wrapper_testers = [
    Flake8ValidTester
]
