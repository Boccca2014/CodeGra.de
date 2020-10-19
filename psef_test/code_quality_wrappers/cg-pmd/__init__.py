import os
import abc
import subprocess

from code_quality_wrappers import Tester

BASE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'),
)


class PMDTester(Tester):
    def run_test(self):
        return self.run_wrapper('-rulesets', self.config_file)

    @property
    def wrapper_name(self):
        return 'cg-pmd'

    @property
    @abc.abstractmethod
    def config_file(self):
        raise NotImplementedError


class PMDValidTester(PMDTester):
    @property
    def submission_archive(self):
        return 'test_pmd.tar.gz'

    @property
    def config_file(self):
        return os.path.join(
            BASE_DIR, 'resources', 'pmd', 'maven.xml'
        )

    @property
    def expected_output(self):
        return [
            {
                'origin': 'PMD',
                'msg': "Invoke equals() on the object you've already ensured is not null",
                'code': 'UnusedNullCheckInEquals',
                'severity': 'warning',
                'line': {'start': 15, 'end': 15},
                'column': {'start': 1, 'end': None},
                'path': ['error.java'],
            },
            {
                'origin': 'PMD',
                'msg': 'Method call on object which may be null',
                'code': 'BrokenNullCheck',
                'severity': 'error',
                'line': {'start': 17, 'end': 17},
                'column': {'start': 1, 'end': None},
                'path': ['error.java'],
            },
            {
                'origin': 'PMD',
                'msg': "Avoid unused local variables such as 'c'.",
                'code': 'UnusedLocalVariable',
                'severity': 'warning',
                'line': {'start': 19, 'end': 19},
                'column': {'start': 1, 'end': None},
                'path': ['error.java'],
            },
            {
                'origin': 'PMD',
                'msg': 'Ternary operators that can be simplified with || or &&',
                'code': 'SimplifiedTernary',
                'severity': 'warning',
                'line': {'start': 19, 'end': 19},
                'column': {'start': 1, 'end': None},
                'path': ['error.java'],
            },
        ]


wrapper_testers = [
    PMDValidTester
]
