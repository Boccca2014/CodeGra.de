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
    Type, AnyType, Instance, TypeType, TupleType, UnionType, LiteralType,
    CallableType, TypedDictType
)
from mypy.plugin import (  # pylint: disable=no-name-in-module
    Plugin, MethodContext, FunctionContext
)

from cg_request_args import MissingType


def argument_callback(ctx: FunctionContext) -> Type:
    key = ctx.arg_types[0][0]
    if not isinstance(key, Instance):
        return ctx.default_return_type

    if not isinstance(key.last_known_value, LiteralType):
        ctx.api.fail(
            'The key to the _Argument constructor should be a literal',
            ctx.context,
        )
        return ctx.default_return_type

    # if isinstance(ctx.default_return_type.args[0], AnyType):
    #     assert False
    # For some reason mypy doesn't pick up the first argument correctly when
    # using a pattern like: `_FixedMapping(_RequiredArgument(...))` so we
    # simply add the argument back in here.
    assert isinstance(ctx.default_return_type, Instance)
    return ctx.default_return_type.copy_modified(
        args=[ctx.default_return_type.args[0], key.last_known_value]
    )


def fixed_mapping_callback(ctx: FunctionContext) -> Type:
    fallback = ctx.api.named_generic_type('typing_extensions._TypedDict', [])

    required_keys = set()
    items = OrderedDict()

    for idx, arg in enumerate(ctx.arg_types[0]):
        required = False

        if isinstance(arg, AnyType):
            ctx.api.fail((
                'Argument number {} was an "Any" which is not allowed as an'
                ' argument to _FixedMapping'
            ).format(idx + 1), ctx.context)
            continue
        try:
            assert isinstance(arg, Instance)
            typ = arg.type.fullname
        except:
            typ = '????'

        if typ == 'cg_request_args._RequiredArgument':
            required = True
        elif typ != 'cg_request_args._OptionalArgument':
            ctx.api.fail((
                'Argument number {} provided was of wrong type, expected'
                ' cg_request_args._RequiredArgument or'
                ' cg_request_args._OptionalArgument, but got {}.'
            ).format(idx + 1, typ), ctx.context)
            continue

        assert isinstance(arg, Instance)
        key_typevar = arg.args[1]
        if not isinstance(key_typevar, LiteralType):
            ctx.api.fail((
                'Second parameter of the argument should be a literal, this'
                ' was not the case for argument {}'
            ).format(idx + 1), ctx.context)
            continue

        key = key_typevar.value
        if not isinstance(key, str):
            ctx.api.fail((
                'Key should be of type string, but was of type {} for argument'
                ' number {}.'
            ).format(type(key), idx + 1), ctx.context)
            continue

        if key in items:
            ctx.api.fail((
                'Key {} was already present, but given again as argument {}.'
            ).format(key, idx + 1), ctx.context)
            continue

        required_keys.add(key)

        value_type = arg.args[0]
        if not required:
            # Use literal here
            value_type = UnionType(
                items=[
                    value_type,
                    LiteralType(
                        MissingType.token.name,
                        ctx.api.named_type('cg_request_args.MissingType'),
                    ),
                ]
            )

        items[key] = value_type

    assert isinstance(ctx.default_return_type, Instance)
    return ctx.default_return_type.copy_modified(
        args=[
            TypedDictType(OrderedDict(items), required_keys, fallback),
        ]
    )


# def add_argument_callback(ctx: MethodContext) -> Type:
#     breakpoint()
#     typeddict = ctx.type.args[0]
#     assert isinstance(typeddict, TypedDictType)
#     existing_items = typeddict.items

#     (key, ), (value, ), doc, *optional = ctx.arg_types
#     assert isinstance(key, Instance)
#     assert isinstance(key.last_known_value, LiteralType)
#     key_value = key.last_known_value.value
#     if key_value in existing_items:
#         ctx.api.fail(
#             'This Arguments already has a key named {}'.format(key_value),
#             ctx.context
#         )
#         return ctx.type

#     new_type = value.items()[0].ret_type
#     if optional and optional[0] and optional[0][0].value:
#         new_type = UnionType(
#             items=[
#                 new_type,
#                 LiteralType(
#                     value='MISSING',
#                     fallback=ctx.api.named_generic_type(
#                         'cg_request_args.MissingType',
#                         [],
#                     ),
#                 )
#             ]
#         )

#     return ctx.type.copy_modified(
#         args=[
#             TypedDictType(
#                 items=OrderedDict(
#                     itertools.chain(
#                         existing_items.items(),
#                         [(key_value, new_type)],
#                     )
#                 ),
#                 required_keys=set(
#                     itertools.chain(existing_items.keys(), [key_value])
#                 ),
#                 line=typeddict.line,
#                 fallback=typeddict.fallback,
#             )
#         ]
#     )
# existing_items[key_value]


class CgRequestArgPlugin(Plugin):
    """Mypy plugin definition.
    """

    # def get_method_hook(  # pylint: disable=no-self-use
    #     self,
    #     fullname: str,
    # ) -> t.Optional[t.Callable[[MethodContext], Type]]:
    #     """Get the function to be called by mypy.
    #     """
    #     if fullname == 'cg_request_args.ArgumentParser.make_decorator':
    #         return add_argument_callback

    #     return None

    def get_function_hook(  # pylint: disable=no-self-use
        self,
        fullname: str,
    ) -> t.Optional[t.Callable[[FunctionContext], Type]]:
        """Get the function to be called by mypy.
        """
        if fullname == 'cg_request_args._RequiredArgument':
            return argument_callback
        if fullname == 'cg_request_args._OptionalArgument':
            return argument_callback
        if fullname == 'cg_request_args._FixedMapping':
            return fixed_mapping_callback

        return None


def plugin(_: str) -> t.Type[CgRequestArgPlugin]:
    """Get the mypy plugin definition.
    """
    # ignore version argument if the plugin works with all mypy versions.
    return CgRequestArgPlugin
