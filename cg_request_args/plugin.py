"""This module implements the mypy plugin needed for the override decorators.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import itertools
from functools import partial
from collections import OrderedDict

# For some reason pylint cannot find these... I've found a lot of people also
# disabling this pylint error, but haven't found an explanation why...
from mypy.nodes import TypeInfo  # pylint: disable=no-name-in-module
from mypy.types import (  # pylint: disable=no-name-in-module
    Type, Instance, TypeType, UnionType, LiteralType, CallableType,
    TypedDictType
)
from mypy.plugin import (  # pylint: disable=no-name-in-module
    Plugin, MethodContext
)

from cg_request_args import MISSING


def add_argument_callback(ctx: MethodContext) -> Type:
    breakpoint()
    typeddict = ctx.type.args[0]
    assert isinstance(typeddict, TypedDictType)
    existing_items = typeddict.items

    (key, ), (value, ), doc, *optional = ctx.arg_types
    assert isinstance(key, Instance)
    assert isinstance(key.last_known_value, LiteralType)
    key_value = key.last_known_value.value
    if key_value in existing_items:
        ctx.api.fail(
            'This Arguments already has a key named {}'.format(key_value),
            ctx.context
        )
        return ctx.type

    new_type = value.items()[0].ret_type
    if optional and optional[0] and optional[0][0].value:
        new_type = UnionType(
            items=[
                new_type,
                LiteralType(
                    value='MISSING',
                    fallback=ctx.api.named_generic_type(
                        'cg_request_args.MissingType',
                        [],
                    ),
                )
            ]
        )

    return ctx.type.copy_modified(
        args=[
            TypedDictType(
                items=OrderedDict(
                    itertools.chain(
                        existing_items.items(),
                        [(key_value, new_type)],
                    )
                ),
                required_keys=set(
                    itertools.chain(existing_items.keys(), [key_value])
                ),
                line=typeddict.line,
                fallback=typeddict.fallback,
            )
        ]
    )
    # existing_items[key_value]


class CgRequestArgPlugin(Plugin):
    """Mypy plugin definition.
    """

    def get_method_hook(  # pylint: disable=no-self-use
        self,
        fullname: str,
    ) -> t.Optional[t.Callable[[MethodContext], Type]]:
        """Get the function to be called by mypy.
        """
        if fullname == 'cg_request_args.ArgumentParser.make_decorator':
            return add_argument_callback

        return None

    def get_method_hook(  # pylint: disable=no-self-use
        self,
        fullname: str,
    ) -> t.Optional[t.Callable[[MethodContext], Type]]:
        """Get the function to be called by mypy.
        """
        if fullname == 'cg_request_args.ArgumentParser.make_decorator':
            return add_argument_callback

        return None


def plugin(_: str) -> t.Type[CgRequestArgPlugin]:
    """Get the mypy plugin definition.
    """
    # ignore version argument if the plugin works with all mypy versions.
    return CgRequestArgPlugin
