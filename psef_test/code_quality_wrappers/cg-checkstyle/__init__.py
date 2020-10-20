import os
import abc
import subprocess

from code_quality_wrappers import Tester

BASE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'),
)


class CheckstyleTester(Tester):
    google_config = os.path.join(
        BASE_DIR, 'resources', 'checkstyle', 'google.xml'
    )

    @property
    def wrapper_name(self):
        return 'cg_checkstyle.py'

    @property
    def submission_archive(self):
        return 'test_checkstyle.tar.gz'


class CheckstyleValidConfigTester(CheckstyleTester):
    def run_test(self):
        self.run_wrapper(self.google_config)

    @property
    def expected_output(self):
        return [
            {
                'origin': 'Checkstyle',
                'msg': "'method def modifier' has incorrect indentation level 4, expected level should be 2.",
                'code': 'com.puppycrawl.tools.checkstyle.checks.indentation.IndentationCheck',
                'severity': 'warning',
                'line': {'start': 14, 'end': 14},
                'column': {'start': 1, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            },
            {
                'origin': 'Checkstyle',
                'msg': 'Missing a Javadoc comment.',
                'code': 'com.puppycrawl.tools.checkstyle.checks.javadoc.MissingJavadocMethodCheck',
                'severity': 'warning',
                'line': {'start': 14, 'end': 14},
                'column': {'start': 5, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            },
            {
                'origin': 'Checkstyle',
                'msg': "'method def' child has incorrect indentation level 8, expected level should be 4.",
                'code': 'com.puppycrawl.tools.checkstyle.checks.indentation.IndentationCheck',
                'severity': 'warning',
                'line': {'start': 15, 'end': 15},
                'column': {'start': 1, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            },
            {
                'origin': 'Checkstyle',
                'msg': "'method def' child has incorrect indentation level 8, expected level should be 4.",
                'code': 'com.puppycrawl.tools.checkstyle.checks.indentation.IndentationCheck',
                'severity': 'warning',
                'line': {'start': 16, 'end': 16},
                'column': {'start': 1, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            },
            {
                'origin': 'Checkstyle',
                'msg': "'method def' child has incorrect indentation level 8, expected level should be 4.",
                'code': 'com.puppycrawl.tools.checkstyle.checks.indentation.IndentationCheck',
                'severity': 'warning',
                'line': {'start': 17, 'end': 17},
                'column': {'start': 1, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            },
            {
                'origin': 'Checkstyle',
                'msg': "'method def' child has incorrect indentation level 8, expected level should be 4.",
                'code': 'com.puppycrawl.tools.checkstyle.checks.indentation.IndentationCheck',
                'severity': 'warning',
                'line': {'start': 18, 'end': 18},
                'column': {'start': 1, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            },
            {
                'origin': 'Checkstyle',
                'msg': "'method def' child has incorrect indentation level 8, expected level should be 4.",
                'code': 'com.puppycrawl.tools.checkstyle.checks.indentation.IndentationCheck',
                'severity': 'warning',
                'line': {'start': 19, 'end': 19},
                'column': {'start': 1, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            },
            {
                'origin': 'Checkstyle',
                'msg': "'method def' child has incorrect indentation level 8, expected level should be 4.",
                'code': 'com.puppycrawl.tools.checkstyle.checks.indentation.IndentationCheck',
                'severity': 'warning',
                'line': {'start': 20, 'end': 20},
                'column': {'start': 1, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            },
            {
                'origin': 'Checkstyle',
                'msg': "'method def rcurly' has incorrect indentation level 4, expected level should be 2.",
                'code': 'com.puppycrawl.tools.checkstyle.checks.indentation.IndentationCheck',
                'severity': 'warning',
                'line': {'start': 21, 'end': 21},
                'column': {'start': 1, 'end': None},
                'path': ['Opgave1', 'Deel1.java'],
            }
    ]


class CheckstyleValidNoCommentsTester(CheckstyleTester):
    @property
    def submission_archive(self):
        return 'test_checkstyle_no_comments.tar.gz'

    def run_test(self):
        self.run_wrapper(self.google_config)

        assert self.get_cgapi_output() is None

    @property
    def expected_output(self):
        return None


class CheckstyleInvalidTester(CheckstyleTester):
    @property
    def expected_output(self):
        return None


class CheckstyleInvalidNoArgsTester(CheckstyleInvalidTester):
    def run_test(self):
        _, _, err = self.run_wrapper(status=1)

        assert 'Checkstyle requires a config file' in err


class CheckstyleInvalidNoConfigTester(CheckstyleInvalidTester):
    def run_test(self):
        _, _, err = self.run_wrapper('', status=1)

        assert 'Checkstyle requires a config file' in err


class CheckstyleInvalidSubmissionTester(CheckstyleInvalidTester):
    def run_test(self):
        _, _, err = self.run_wrapper(self.google_config, status=254)

        assert 'The given submission could not be parsed' in err

    @property
    def submission_archive(self):
        return 'test_checkstyle_invalid_java.tar.gz'


wrapper_testers = [
    CheckstyleValidConfigTester,
    CheckstyleValidNoCommentsTester,
    CheckstyleInvalidNoArgsTester,
    CheckstyleInvalidNoConfigTester,
    CheckstyleInvalidSubmissionTester,
]
