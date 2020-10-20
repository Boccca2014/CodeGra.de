import os
import abc
import subprocess

from code_quality_wrappers import Tester

BASE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'),
)


class PMDTester(Tester):
    maven_config = os.path.join(
        BASE_DIR, 'resources', 'pmd', 'maven.xml'
    )

    @property
    def wrapper_name(self):
        return 'cg_pmd.py'

    @property
    def submission_archive(self):
        return 'test_pmd.tar.gz'


class PMDValidConfigTester(PMDTester):
    def run_test(self):
        self.run_wrapper(self.maven_config)

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


class PMDValidFatalTester(PMDTester):
    def run_test(self):
        ret, stdout, err = self.run_wrapper(self.maven_config)

        print(ret, stdout, err)

    @property
    def submission_archive(self):
        return 'test_pmd_invalid_java.tar.gz'

    @property
    def expected_output(self):
        return []


class PMDInvalidTester(PMDTester):
    @property
    def expected_output(self):
        return None


class PMDInvalidNoArgsTester(PMDInvalidTester):
    def run_test(self):
        _, _, err = self.run_wrapper(status=1)

        assert 'PMD requires a config file' in err


class PMDInvalidNoConfigTester(PMDInvalidTester):
    def run_test(self):
        _, _, err = self.run_wrapper('', status=1)

        assert 'PMD requires a config file' in err


wrapper_testers = [
    PMDValidConfigTester,
    PMDValidFatalTester,
    PMDInvalidNoArgsTester,
    PMDInvalidNoConfigTester,
]
