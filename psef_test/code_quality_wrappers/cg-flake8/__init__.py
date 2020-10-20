import os
import abc
import subprocess

from code_quality_wrappers import Tester


class Flake8Tester(Tester):
    @property
    def wrapper_name(self):
        return 'cg_flake8.py'

    @property
    def submission_archive(self):
        return 'test_flake8.tar.gz'


class Flake8ValidTester(Flake8Tester):
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


class Flake8ValidNoArgsTester(Flake8ValidTester):
    def run_test(self):
        self.run_wrapper()


class Flake8ValidNoConfigTester(Flake8ValidTester):
    def run_test(self):
        self.run_wrapper('')


class Flake8ValidConfigTester(Flake8ValidTester):
    def run_test(self):
        config = self.write_file('config', '''[flake8]
ignore = E202
''')
        self.run_wrapper(config)

    @property
    def expected_output(self):
        return [
            c
            for c in super().expected_output
            if c['code'] != 'E202'
        ]


class Flake8ValidNoCommentsTester(Flake8Tester):
    @property
    def submission_archive(self):
        return 'test_flake8_no_comments.tar.gz'

    def run_test(self):
        self.run_wrapper()

        assert self.get_cgapi_output() is None

    @property
    def expected_output(self):
        return None


class Flake8InvalidConfigTester(Flake8Tester):
    def run_test(self):
        config = self.write_file('config', '''[flake8]
disable_noqa=Trues # This should crash
''')
        _, _, err = self.run_wrapper(config, status=1)

        assert 'Flake8 crashed' in err

    @property
    def expected_output(self):
        return None


wrapper_testers = [
    Flake8ValidNoArgsTester,
    Flake8ValidNoConfigTester,
    Flake8ValidConfigTester,
    Flake8ValidNoCommentsTester,
    Flake8InvalidConfigTester,
]
