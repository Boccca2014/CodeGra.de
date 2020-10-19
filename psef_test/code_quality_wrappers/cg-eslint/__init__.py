import os
import abc
import subprocess

from code_quality_wrappers import Tester


class ESLintTester(Tester):
    def run_test(self):
        return self.run_wrapper('**/*.js')

    @property
    def wrapper_name(self):
        return 'cg-eslint'

class ESLintValidTester(ESLintTester):
    @property
    def submission_archive(self):
        return 'test_eslint.tar.gz'

    @property
    def expected_output(self):
        return [
            {
                'origin': 'ESLint',
                'msg': "Parsing error: The keyword 'import' is reserved",
                'code': None,
                'severity': 'fatal',
                'line': {'start': 2, 'end': 2},
                'column': {'start': 1, 'end': None},
                'path': ['index.js'],
            }
        ]


wrapper_testers = [
    ESLintValidTester
]
