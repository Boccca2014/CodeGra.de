"""
This module contains all plagiarism providers.

A plagiarism provider is a class that extends and implements the missing
functions from :class:`psef.plagiarism.PlagiarismProvider`.

SPDX-License-Identifier: AGPL-3.0-only
"""


def init_app(_: object) -> None:
    from . import \
        jplag  # pylint: disable=unused-import, import-outside-toplevel
