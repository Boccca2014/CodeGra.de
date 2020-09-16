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
    Plugin, MethodContext, FunctionContext, AttributeContext
)

import cg_request_args


def dict_getter_attribute_callback(ctx: AttributeContext, attr: str) -> Type:
    if attr == '__data':
        return ctx.default_attr_type

    def get_for_typeddict(typeddict: Type) -> Type:
        assert isinstance(
            typeddict, TypedDictType
        ), 'Variable has strange value: {}'.format(typeddict)
        items = typeddict.items

        if attr not in items:
            ctx.api.fail(
                (
                    'The _DictGetter[{}] does not have the attribute {},'
                    ' available attributes: {}'
                ).format(typeddict, attr, ', '.join(items.keys())),
                ctx.context,
            )
            return ctx.default_attr_type

        return items[attr]

    if isinstance(ctx.type, Instance):
        return get_for_typeddict(ctx.type.args[0])
    elif isinstance(ctx.type, UnionType):
        items = []
        for item in ctx.type.items:
            assert isinstance(item, Instance)
            items.append(get_for_typeddict(item.args[0]))
        return UnionType(items)
    else:
        raise AssertionError('Got strange type: {}'.format(ctx.type))


def string_enum_callback(ctx: FunctionContext) -> Type:
    literals = []
    for idx, arg in enumerate(ctx.arg_types[0]):
        assert isinstance(arg, Instance)
        if not isinstance(arg.last_known_value, LiteralType):
            ctx.api.fail(
                (
                    'The arguments to "StringEnum" should all be literals'
                    f' (this is not the case for arg {idx + 1})'
                ),
                ctx.context,
            )
            return ctx.default_return_type
        literals.append(arg.last_known_value)

    assert isinstance(ctx.default_return_type, Instance)
    return ctx.default_return_type.copy_modified(args=[UnionType(literals)])


def add_tag_callback(ctx: MethodContext) -> Type:
    (key, ), (value, ) = ctx.arg_types
    if not isinstance(key, Instance
                      ) or not isinstance(key.last_known_value, LiteralType):
        ctx.api.fail(
            'The key to the FixedMapping.add_tag should be a literal',
            ctx.context,
        )
        return ctx.default_return_type
    if not isinstance(value, Instance) or not isinstance(
        value.last_known_value, LiteralType
    ):
        ctx.api.fail(
            'The value to the FixedMapping.add_tag should be a literal',
            ctx.context,
        )
        return ctx.default_return_type

    key_value = key.last_known_value.value
    if not isinstance(key_value, str):
        ctx.api.fail(
            'The key to the FixedMapping.add_tag should be a string',
            ctx.context,
        )
        return ctx.default_return_type

    assert isinstance(ctx.default_return_type, Instance)
    typeddict = ctx.default_return_type.args[0]
    assert isinstance(typeddict, TypedDictType)

    items = OrderedDict(typeddict.items.items())
    items[key_value] = value.last_known_value
    required = set([*typeddict.required_keys, key_value])

    args = [
        TypedDictType(
            items=items,
            required_keys=required,
            fallback=typeddict.fallback,
            line=typeddict.line,
            column=typeddict.column
        )
    ]

    return ctx.default_return_type.copy_modified(args=args)


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

        if typ == 'cg_request_args.RequiredArgument':
            required = True
        elif typ != 'cg_request_args.OptionalArgument':
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
                    ctx.api.named_generic_type(
                        'cg_maybe.Just',
                        [value_type],
                    ),
                    ctx.api.named_generic_type(
                        'cg_maybe._Nothing',
                        [],
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


class CgRequestArgPlugin(Plugin):
    """Mypy plugin definition.
    """

    def get_method_hook(  # pylint: disable=no-self-use
        self,
        fullname: str,
    ) -> t.Optional[t.Callable[[MethodContext], Type]]:
        """Get the function to be called by mypy.
        """
        if fullname == 'cg_request_args.FixedMapping.add_tag':
            return add_tag_callback
        return None

    def get_function_hook(  # pylint: disable=no-self-use
        self,
        fullname: str,
    ) -> t.Optional[t.Callable[[FunctionContext], Type]]:
        """Get the function to be called by mypy.
        """
        if fullname == 'cg_request_args.RequiredArgument':
            return argument_callback
        if fullname == 'cg_request_args.OptionalArgument':
            return argument_callback
        if fullname == 'cg_request_args.FixedMapping':
            return fixed_mapping_callback
        if fullname == 'cg_request_args.StringEnum':
            return string_enum_callback

        return None

    def get_attribute_hook(
        self, fullname: str
    ) -> t.Optional[t.Callable[[AttributeContext], Type]]:
        path = fullname.split('.')
        if path[:-1] == ['cg_request_args', '_DictGetter']:
            return partial(dict_getter_attribute_callback, attr=path[-1])

        return None


def plugin(_: str) -> t.Type[CgRequestArgPlugin]:
    """Get the mypy plugin definition.
    """
    # ignore version argument if the plugin works with all mypy versions.
    return CgRequestArgPlugin
