import os
import abc
import subprocess

from code_quality_wrappers import Tester


class ESLintTester(Tester):
    @property
    def wrapper_name(self):
        return 'cg_eslint.py'

    @property
    def submission_archive(self):
        return 'test_eslint_simple.tar.gz'


class ESLintValidNoConfigTester(ESLintTester):
    def run_test(self):
        self.run_wrapper('', '**/*.js')

    @property
    def expected_output(self):
        return None


class ESLintValidConfigTester(ESLintTester):
    def run_test(self):
        config = self.write_file('config', '''{
    "root": true,
    "rules": {
        "no-unused-vars": ["warn"],
        "semi": ["error", "always"]
    },
}
''')
        _, _, err = self.run_wrapper(config, '**/*.js')
        print(err)

    @property
    def expected_output(self):
        return [
            {
                'origin': 'ESLint',
                'msg': "'my_func' is defined but never used.",
                'code': 'no-unused-vars',
                'severity': 'warning',
                'line': {'start': 1, 'end': 1},
                'column': {'start': 10, 'end': 17},
                'path': ['index.js'],
            },
            {
                'origin': 'ESLint',
                'msg': "'a' is assigned a value but never used.",
                'code': 'no-unused-vars',
                'severity': 'warning',
                'line': {'start': 2, 'end': 2},
                'column': {'start': 7, 'end': 8},
                'path': ['index.js'],
            },
            {
                'origin': 'ESLint',
                'msg': 'Missing semicolon.',
                'code': 'semi',
                'severity': 'error',
                'line': {'start': 2, 'end': 2},
                'column': {'start': 12, 'end': None},
                'path': ['index.js'],
            },
            {
                'origin': 'ESLint',
                'msg': 'Missing semicolon.',
                'code': 'semi',
                'severity': 'error',
                'line': {'start': 3, 'end': 3},
                'column': {'start': 22, 'end': None},
                'path': ['index.js'],
            },
        ]


class ESLintValidFatalTester(ESLintTester):
    def run_test(self):
        self.run_wrapper('', '**/*.js')

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


class ESLintInvalidTester(ESLintTester):
    @property
    def expected_output(self):
        return None


class ESLintInvalidExtendsTester(ESLintInvalidTester):
    def run_test(self):
        config = self.get_fixture('test_linter', 'eslint_invalid_extends.json')
        _, _, err = self.run_wrapper(config, '**/*.js', status=2)

        assert 'Cannot read config file' in err


class ESLintInvalidPluginTester(ESLintInvalidTester):
    def run_test(self):
        config = self.get_fixture('test_linter', 'eslint_invalid_plugin.json')
        _, _, err = self.run_wrapper(config, '**/*.js', status=2)

        assert "ESLint couldn't find the plugin" in err


class ESLintInvalidEcmaVersionTester(ESLintInvalidTester):
    def run_test(self):
        config = self.get_fixture('test_linter', 'eslint_unknown_ecma.json')
        _, _, err = self.run_wrapper(config, '**/*.js', status=2)

        assert "couldn't find the plugin" in err


class ESLintInvalidNoFilesTester(ESLintInvalidTester):
    def run_test(self):
        _, _, err = self.run_wrapper(status=1)

        assert 'ESLint crashed' in err


wrapper_testers = [
    ESLintValidNoConfigTester,
    ESLintValidConfigTester,
    ESLintValidFatalTester,
    ESLintInvalidExtendsTester,
    ESLintInvalidPluginTester,
    ESLintInvalidEcmaVersionTester,
    ESLintInvalidNoFilesTester,
]
