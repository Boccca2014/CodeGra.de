"""This module implements the mypy plugin needed for the special ``is_...``
methods

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from mypy.nodes import Var, MemberExpr  # pylint: disable=no-name-in-module
from mypy.types import (  # pylint: disable=no-name-in-module
    Type, Instance, LiteralType
)
from mypy.plugin import (  # pylint: disable=no-name-in-module
    Plugin, AttributeContext
)


def _enum_has(enum: t.Any, attr: str) -> bool:
    try:
        return isinstance(enum.names[attr].node, Var)
    except KeyError:
        return False


def analyze_is_method_for_db(ctx: AttributeContext) -> Type:
    """Callback to analyze the ``is_*`` methods on ``CGEnum``s.
    """
    typ = ctx.type
    assert isinstance(ctx.context, MemberExpr)
    assert isinstance(
        typ,
        Instance,
    ), f'Got strange type: {typ} ({type(typ)})'

    name = ctx.context.name
    first_arg = typ.args[0]
    assert isinstance(first_arg, Instance)
    enum_type = first_arg.type
    if not name.startswith('is_'):
        ctx.api.fail(
            f'The enum {enum_type.name} has no attribute "{name}"', ctx.context
        )

    enum_value = name[len('is_'):]

    if not _enum_has(enum_type, enum_value):
        ctx.api.fail((
            f'The enum {enum_type.name} has no attribute "{name}" as the enum'
            f' has no member "{enum_value}"'
        ), ctx.context)

    return ctx.api.named_generic_type(
        'cg_sqlalchemy_helpers.types.DbColumn',
        [ctx.api.named_generic_type('builtins.bool', [])]
    )


def analyze_is_method(ctx: AttributeContext) -> Type:
    """Callback to analyze the ``is_*`` methods on ``CGEnum``s.
    """
    typ = ctx.type
    assert isinstance(ctx.context, MemberExpr)
    name = ctx.context.name
    enum_value = name[len('is_'):]

    assert isinstance(
        typ,
        Instance,
    ), f'Got strange type: {typ} ({type(typ)})'

    bool_type = ctx.api.named_generic_type('builtins.bool', [])
    last_known_value = typ.last_known_value
    if isinstance(last_known_value, LiteralType):
        is_value = last_known_value.value == enum_value
        enum_type = last_known_value.fallback.type
        if not is_value and not _enum_has(enum_type, enum_value):
            ctx.api.fail((
                f'The enum {enum_type.name} has no attribute "{name}" as'
                f' the enum has no member "{enum_value}"'
            ), ctx.context)
        literal_type = LiteralType(is_value, fallback=bool_type)
        return bool_type.copy_modified(last_known_value=literal_type)

    enum_type = typ.type
    if not _enum_has(enum_type, enum_value):
        ctx.api.fail((
            f'The enum {enum_type.name} has no attribute "{name}" as the enum'
            f' has no member "{enum_value}"'
        ), ctx.context)

    return bool_type


class CgEnumPlugin(Plugin):
    """Plugin class for ``CGEnum``.
    """
    def get_attribute_hook(  # pylint: disable=no-self-use,missing-function-docstring
        self, fullname: str
    ) -> t.Optional[t.Callable[[AttributeContext], Type]]:
        if fullname.startswith('cg_enum.CGEnum.is_'):
            return analyze_is_method
        if fullname.startswith(r'cg_sqlalchemy_helpers.types.CGEnumDbColumn'):
            return analyze_is_method_for_db
        return None


def plugin(version: str) -> t.Type[CgEnumPlugin]:  # pylint: disable=unused-argument,missing-function-docstring
    # ignore version argument if the plugin works with all mypy versions.
    return CgEnumPlugin
