"""This module implements the mypy plugin needed for cg_maybe

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

# For some reason pylint cannot find these... I've found a lot of people also
# disabling this pylint error, but haven't found an explanation why...
from mypy.types import (  # pylint: disable=no-name-in-module
    Type, UnionType, UnboundType
)
from mypy.plugin import (  # pylint: disable=no-name-in-module
    Plugin, AnalyzeTypeContext
)


def cg_maybe_callback(ctx: AnalyzeTypeContext) -> Type:
    return UnionType(
        items=[
            ctx.api.analyze_type(
                UnboundType(
                    'cg_maybe.Just',
                    ctx.type.args,
                ),
            ),
            ctx.api.analyze_type(
                UnboundType(
                    'cg_maybe._Nothing',
                    ctx.type.args,
                ),
            ),
        ]
    )


class CgMaybePlugin(Plugin):
    """Mypy plugin definition.
    """

    def get_type_analyze_hook(  # pylint: disable=no-self-use
        self,
        fullname: str,
    ) -> t.Optional[t.Callable[[AnalyzeTypeContext], Type]]:
        """Get the function to be called by mypy.
        """
        if fullname == 'cg_maybe.Maybe':
            return cg_maybe_callback
        return None


def plugin(_: str) -> t.Type[CgMaybePlugin]:
    """Get the mypy plugin definition.
    """
    # ignore version argument if the plugin works with all mypy versions.
    return CgMaybePlugin
