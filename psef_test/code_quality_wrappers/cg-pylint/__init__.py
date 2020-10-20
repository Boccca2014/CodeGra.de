import os
import abc
import subprocess

from code_quality_wrappers import Tester


class PyLintTester(Tester):
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


class PyLintValidNoConfigTester(PyLintValidTester):
    def run_test(self):
        self.run_wrapper('', 'pylint_test_dir')


class PyLintValidConfigTester(PyLintValidTester):
    def run_test(self):
        config = self.write_file('config', '''[pylint]
disable = unused-argument
''')
        self.run_wrapper(config, 'pylint_test_dir')

    @property
    def expected_output(self):
        return [
            c
            for c in super().expected_output
            if c['code'] != 'unused-argument'
        ]


class PyLintValidNoCommentsTester(PyLintTester):
    def run_test(self):
        self.run_wrapper('', 'pylint_test_dir')

    @property
    def submission_archive(self):
        return 'test_pylint_no_comments.tar.gz'

    @property
    def expected_output(self):
        return None


class PyLintInvalidTester(PyLintTester):
    @property
    def expected_output(self):
        return None


class PyLintInvalidNoArgsTester(PyLintInvalidTester):
    def run_test(self):
        _, _, err = self.run_wrapper(status=32)

        assert 'PyLint crashed' in err

class PyLintInvalidModuleTester(PyLintInvalidTester):
    def run_test(self):
        _, _, err = self.run_wrapper('', 'pylint_test_dir', status=1)

        assert 'The submission is not a valid python module' in err

    @property
    def submission_archive(self):
        return 'test_pylint_invalid_module.tar.gz'


wrapper_testers = [
    PyLintValidNoConfigTester,
    PyLintValidConfigTester,
    PyLintValidNoCommentsTester,
    PyLintInvalidNoArgsTester,
    PyLintInvalidModuleTester,
]
