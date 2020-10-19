import os
import abc
import subprocess

from code_quality_wrappers import Tester

BASE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'),
)


class CheckstyleTester(Tester):
    def run_test(self):
        return self.run_wrapper('-c', self.config_file)

    @property
    def wrapper_name(self):
        return 'cg-checkstyle'

    @property
    @abc.abstractmethod
    def config_file(self):
        raise NotImplementedError



class CheckstyleValidTester(CheckstyleTester):
    @property
    def submission_archive(self):
        return 'test_checkstyle.tar.gz'

    @property
    def config_file(self):
        return os.path.join(
            BASE_DIR, 'resources', 'checkstyle', 'google.xml'
        )

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


wrapper_testers = [
    CheckstyleValidTester
]
