"""Mypy plugin to make it possible to type safely extend a type dict.

SPDX-License-Identifier: AGPL-3.0-only
"""
from mypy.nodes import ARG_NAMED  # pylint: disable=no-name-in-module
from mypy.types import (  # pylint: disable=no-name-in-module
    Type, CallableType, TypedDictType
)
from mypy.plugin import (  # pylint: disable=no-name-in-module
    Plugin, FunctionContext
)


def callback(ctx: FunctionContext) -> Type:
    """Get the callback for ``extend_typed_dict``
    """
    base_dict, (extends_to, ), *_ = ctx.arg_types
    ret = ctx.default_return_type
    if not isinstance(base_dict[0], TypedDictType):
        ctx.api.fail(
            (
                'Argument 1 to "extend_typed_dict" has incompatible type "{}";'
                ' expected "TypedDict"'
            ).format(base_dict[0].name),
            ctx.context,
        )
        return ret
    if (
        not isinstance(extends_to, CallableType) or
        not extends_to.is_type_obj() or
        extends_to.ret_type.type.typeddict_type is None
    ):
        ctx.api.fail(
            (
                'Argument 2 to "extend_typed_dict" has incompatible type "{}";'
                ' expected "Type[TypedDict]"'
            ).format(extends_to.name),
            ctx.context,
        )
        return ret

    base_items = dict(base_dict[0].items)
    extends_items = dict(extends_to.ret_type.type.typeddict_type.items)
    for name, typ in base_items.items():
        if name not in extends_items:
            ctx.api.fail(
                '{} does not extend {}, item {} misses'.format(
                    extends_to.ret_type, base_dict[0], name
                ), ctx.context
            )
            return ret

        if typ != extends_items[name]:
            ctx.api.fail(
                (
                    '{} does not extend {}, item {} has a different type (found'
                    ' {}, expected {})'
                ).format(
                    extends_to.type.name, base_dict[0].name, name,
                    extends_items[name], typ
                ),
                ctx.context,
            )
            return ret

        del extends_items[name]

    arg_names_types = list(extends_items.items())
    return ret.copy_modified(
        arg_kinds=[ARG_NAMED for _ in arg_names_types],
        arg_types=[typ for _, typ in arg_names_types],
        arg_names=[name for name, _ in arg_names_types],
        ret_type=extends_to.ret_type.type.typeddict_type,
    )


class CgTypedDictPlugin(Plugin):
    """Class implementing the  ``make_typed_dict_extender`` plugin.
    """

    def get_function_hook(self, fullname: str):  # pylint: disable=no-self-use,missing-function-docstring
        if fullname == 'cg_typing_extensions.make_typed_dict_extender':
            return callback
        return None


def plugin(version: str):  # pylint: disable=unused-argument,missing-function-docstring
    # ignore version argument if the plugin works with all mypy versions.
    return CgTypedDictPlugin
