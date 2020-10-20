import os
import abc
import subprocess

from code_quality_wrappers import Tester


class PyLintTester(Tester):
    def run_test(self):
        self.run_wrapper('pylint_test_dir')
        return self.get_cgapi_output()

    @property
    def wrapper_name(self):
        return 'cg_pylint.py'

    @property
    def submission_archive(self):
        return 'test_pylint.tar.gz'


class PyLintValidTester(PyLintTester):
    @property
    def expected_output(self):
        return [
            {
                'origin': 'PyLint',
                'msg': 'Missing module docstring',
                'code': 'missing-module-docstring',
                'severity': 'info',
                'line': {'start': 1, 'end': 1},
                'column': {'start': 0, 'end': None},
                'path': ['pylint_test_dir', '__init__.py'],
            },
            {
                'origin': 'PyLint',
                'msg': 'Bad indentation. Found 1 spaces, expected 4',
                'code': 'bad-indentation',
                'severity': 'warning',
                'line': {'start': 2, 'end': 2},
                'column': {'start': 0, 'end': None},
                'path': ['pylint_test_dir', 'test.py'],
            },
            {
                'origin': 'PyLint',
                'msg': 'Missing module docstring',
                'code': 'missing-module-docstring',
                'severity': 'info',
                'line': {'start': 1, 'end': 1},
                'column': {'start': 0, 'end': None},
                'path': ['pylint_test_dir', 'test.py'],
            },
            {
                'origin': 'PyLint',
                'msg': 'Function name "a" doesn\'t conform to snake_case naming style',
                'code': 'invalid-name',
                'severity': 'info',
                'line': {'start': 1, 'end': 1},
                'column': {'start': 0, 'end': None},
                'path': ['pylint_test_dir', 'test.py'],
            },
            {
                'origin': 'PyLint',
                'msg': 'Argument name "b" doesn\'t conform to snake_case naming style',
                'code': 'invalid-name',
                'severity': 'info',
                'line': {'start': 1, 'end': 1},
                'column': {'start': 0, 'end': None},
                'path': ['pylint_test_dir', 'test.py'],
            },
            {
                'origin': 'PyLint',
                'msg': 'Missing function or method docstring',
                'code': 'missing-function-docstring',
                'severity': 'info',
                'line': {'start': 1, 'end': 1},
                'column': {'start': 0, 'end': None},
                'path': ['pylint_test_dir', 'test.py'],
            },
            {
                'origin': 'PyLint',
                'msg': "Unused argument 'b'",
                'code': 'unused-argument',
                'severity': 'warning',
                'line': {'start': 1, 'end': 1},
                'column': {'start': 6, 'end': None},
                'path': ['pylint_test_dir', 'test.py'],
            }
        ]


wrapper_testers = [
    PyLintValidTester
]
