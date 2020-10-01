"""This module implements the provider for the JPlag plagiarism checker.

This provider only works with the codegrade fork of JPlag as other versions do
not output the needed csv file.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

import psef.helpers

from .. import app
from .. import plagiarism as plag


class JPlag(plag.PlagiarismProvider):
    """This class implements the JPlag plagiarism provider.
    """

    def __init__(self) -> None:
        self.lang: t.Optional[str] = None
        self.suffixes: t.Optional[str] = None
        self.simil: int = 50
        self.has_base_code: bool = False

    @property
    def matches_output(self) -> str:
        """The path were the result csv is placed.

        :returns: The specified path
        """
        return 'computer_matches.csv'

    @staticmethod
    def supports_progress() -> bool:
        return True

    @staticmethod
    def get_progress_from_line(prefix: str,
                               line: str) -> t.Optional[t.Tuple[int, int]]:
        line = line.rstrip()
        if not line.startswith(prefix):
            return None
        try:
            current, total, *_ = line[len(prefix) + 1:].split('/')
            return int(current.strip()), int(total.strip())
        # pylint: disable=broad-except
        except Exception:  # pragma: no cover
            return None

    @staticmethod
    def get_options() -> t.Sequence[plag.Option]:
        """Get all possible options for JPlag.

        :returns: The possible options.
        """
        return [
            plag.Option(
                "lang",
                "Language",
                "The language used to parse the files from the student",
                plag.OptionTypes.singleselect,
                True,
                list(app.config['JPLAG_SUPPORTED_LANGUAGES'].keys()),
            ),
            plag.Option(
                "suffixes",
                "Suffixes to include",
                (
                    "A comma separated list of suffixes. A file is only parsed"
                    " if it ends with one of the given suffixes exactly, no"
                    " regex is supported. If this value is left empty suitable"
                    " suffixes will be selected for the selected language."
                ),
                plag.OptionTypes.strvalue,
                False,
                None,
                placeholder='.xxx, .yyy',
            ),
            plag.Option(
                "simil",
                "Minimal similarity",
                (
                    "The minimal average similarity needed before a pair is "
                    "considered plagiarism. If this is set to 100 both "
                    "assignments need to be completely the same, when set to"
                    " 50 both submissions need to be 50% the same, or one 25%"
                    " and the other 75%. The default is 50."
                ),
                plag.OptionTypes.numbervalue,
                False,
                None,
                placeholder='default: 50',
            ),
        ]

    def _set_provider_values(
        self, values: t.Dict[str, psef.helpers.JSONType]
    ) -> None:
        """Set the options for JPlag.

        :param values: The values to be set.
        :returns: Nothing.
        """
        self.lang = app.config['JPLAG_SUPPORTED_LANGUAGES'][str(
            values['lang']
        )]
        self.has_base_code = bool(values['has_base_code'])

        if 'suffixes' in values:
            self.suffixes = str(values['suffixes'])
        if 'simil' in values:
            assert isinstance(values['simil'], (int, float))
            self.simil = int(values['simil'])

    def get_program_call(self) -> t.List[str]:
        """Get the program call for JPlag.

        :returns: A list as that can be used with
            :func:`subprocess.check_output` to run JPlag.
        """
        java = app.config['JAVA_PATH']
        jar = app.config['JPLAG_JAR']
        assert self.lang is not None

        # yapf: disable
        res = [
            java,
            '-jar', jar,
            '{restored_dir}',
            '-l', self.lang,
            '-s',
            '-r', '{result_dir}',
            '-m', f'{self.simil}%',
            '-a', '{archive_dir}',
            '-progress', '{progress_prefix}',
        ]
        # yapf: enable
        if self.has_base_code:
            res.extend(['-bc', '{base_code_dir}'])

        if self.suffixes is not None:
            res.extend(['-p', self.suffixes])

        return res
