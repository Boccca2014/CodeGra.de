"""This module implements the mypy plugin needed for the cg_request_args
module.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import itertools
from functools import partial
from collections import OrderedDict

# For some reason pylint cannot find these... I've found a lot of people also
# disabling this pylint error, but haven't found an explanation why...
from mypy.types import (  # pylint: disable=no-name-in-module
    Type, AnyType, Instance, UnionType, LiteralType, CallableType,
    TypedDictType
)
from mypy.plugin import (  # pylint: disable=no-name-in-module
    Plugin, MethodContext, FunctionContext, AttributeContext
)
from mypy.typeops import \
    make_simplified_union  # pylint: disable=no-name-in-module


def from_typeddict_callback(ctx: MethodContext) -> Type:
    """Callback for the ``from_typeddict`` method on ``BaseFixedMapping``.
    """
    assert isinstance(ctx.default_return_type, Instance)
    producer = ctx.arg_types[0][0]

    if (
        not isinstance(producer, CallableType) or
        not isinstance(producer.ret_type, Instance) or
        not isinstance(producer.ret_type.type.typeddict_type, TypedDictType)
    ):
        ctx.api.fail(
            'The argument to `from_typeddict` should be a typeddict type',
            ctx.context
        )
        return ctx.default_return_type

    return ctx.default_return_type.copy_modified(
        args=[producer.ret_type.type.typeddict_type]
    )


def dict_getter_attribute_callback(ctx: AttributeContext, attr: str) -> Type:
    """Callback for ``getattr`` in ``_DictGetter``.
    """
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
                    'The _DictGetter[{}] does not have the attribute {!r},'
                    ' available attributes: {}'
                ).format(typeddict, attr, ', '.join(items.keys())),
                ctx.context,
            )
            return ctx.default_attr_type

        return items[attr]

    if isinstance(ctx.type, Instance):
        return make_simplified_union([get_for_typeddict(ctx.type.args[0])])
    elif isinstance(ctx.type, UnionType):
        items = []
        for item in ctx.type.items:
            assert isinstance(item, Instance)
            items.append(get_for_typeddict(item.args[0]))
        return make_simplified_union(items)
    else:  # pragma: no cover
        raise AssertionError('Got strange type: {}'.format(ctx.type))


def string_enum_callback(ctx: FunctionContext) -> Type:
    """Callback to infer the correct type for ``StringEnum`` parsers.
    """
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


def combine_callback(ctx: MethodContext) -> Type:
    """Callback for the ``combine`` method on ``FixedMapping``.
    """
    assert isinstance(ctx.type, Instance)
    own_typeddict, = ctx.type.args
    (other, ), = ctx.arg_types

    assert isinstance(other, Instance)
    other_typeddict, = other.args
    assert isinstance(other_typeddict, TypedDictType)
    assert isinstance(own_typeddict, TypedDictType)

    for new_key in other_typeddict.items.keys():
        if new_key in own_typeddict.items:
            ctx.api.fail(
                'Cannot combine typeddict, got overlapping key {!r}'.
                format(new_key), ctx.context
            )
            return ctx.default_return_type
    items = list(
        itertools.chain(
            own_typeddict.items.items(),
            other_typeddict.items.items(),
        )
    )
    new_typeddict = TypedDictType(
        items=OrderedDict(items),
        required_keys={
            *own_typeddict.required_keys, *other_typeddict.required_keys
        },
        fallback=own_typeddict.fallback,
        line=own_typeddict.line,
        column=own_typeddict.column
    )
    assert isinstance(ctx.default_return_type, Instance)
    return ctx.default_return_type.copy_modified(args=[new_typeddict])


def add_tag_callback(ctx: MethodContext) -> Type:
    """Callback for the ``add_tag`` method of ``FixedMapping``.
    """
    (key, ), (value, ) = ctx.arg_types
    if not isinstance(key, Instance
                      ) or not isinstance(key.last_known_value, LiteralType):
        ctx.api.fail(
            'The key to FixedMapping.add_tag should be a literal',
            ctx.context,
        )
        return ctx.default_return_type

    dict_type = value
    if isinstance(value, Instance) and isinstance(
        value.last_known_value, LiteralType
    ):
        dict_type = value.last_known_value

    key_value = key.last_known_value.value
    if not isinstance(key_value, str):  # pragma: no cover
        return ctx.default_return_type

    assert isinstance(ctx.default_return_type, Instance)
    typeddict = ctx.default_return_type.args[0]
    assert isinstance(typeddict, TypedDictType)

    items = OrderedDict(typeddict.items.items())
    items[key_value] = dict_type
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
    """Callback to fix the type arguments to ``_Argument`` classes.
    """
    key = ctx.arg_types[0][0]
    if (
        not isinstance(key, Instance) or
        not isinstance(key.last_known_value, LiteralType)
    ):
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
    """The callback to infer a better type for ``FixedMapping``.
    """
    fallback = ctx.api.named_generic_type('typing_extensions._TypedDict', [])

    required_keys = set()
    items = OrderedDict()

    for idx, arg in enumerate(ctx.arg_types[0]):
        if isinstance(arg, AnyType):
            ctx.api.fail((
                'Argument {} was an "Any" which is not allowed as an'
                ' argument to FixedMapping'
            ).format(idx + 1), ctx.context)
            continue
        if isinstance(arg, Instance):
            typ = arg.type.fullname
        else:  # pragma: no cover
            typ = '????'

        if typ not in (
            'cg_request_args.RequiredArgument',
            'cg_request_args.OptionalArgument'
        ):
            ctx.api.fail((
                'Argument {} provided was of wrong type, expected'
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
                ' {}.'
            ).format(type(key).__name__, idx + 1), ctx.context)
            continue

        if key in items:
            ctx.api.fail((
                'Key {!r} was already present, but given again as argument {}.'
            ).format(key, idx + 1), ctx.context)
            continue

        required_keys.add(key)

        value_type = arg.args[0]
        if typ == 'cg_request_args.OptionalArgument':
            value_type = make_simplified_union([
                ctx.api.named_generic_type(
                    'cg_maybe.Just',
                    [value_type],
                ),
                ctx.api.named_generic_type(
                    'cg_maybe._Nothing',
                    [value_type],
                ),
            ])

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
        if fullname == 'cg_request_args.FixedMapping.combine':
            return combine_callback
        if fullname == 'cg_request_args.BaseFixedMapping.from_typeddict':
            return from_typeddict_callback
        return None

    def get_function_hook(  # pylint: disable=no-self-use
        self,
        fullname: str,
    ) -> t.Optional[t.Callable[[FunctionContext], Type]]:
        """Get the function to be called by mypy.
        """
        if fullname in (
            'cg_request_args.RequiredArgument',
            'cg_request_args.OptionalArgument',
        ):
            return argument_callback
        if fullname in (
            'cg_request_args.BaseFixedMapping', 'cg_request_args.FixedMapping',
            'cg_request_args._BaseFixedMapping'
        ):
            return fixed_mapping_callback
        if fullname == 'cg_request_args.StringEnum':
            return string_enum_callback

        return None

    @staticmethod
    def get_attribute_hook(
        fullname: str
    ) -> t.Optional[t.Callable[[AttributeContext], Type]]:
        """Get the function hook for getattr for ``_DictGetter``.
        """
        path = fullname.split('.')
        if path[:-1] == ['cg_request_args', '_DictGetter']:
            return partial(dict_getter_attribute_callback, attr=path[-1])

        return None


def plugin(_: str) -> t.Type[CgRequestArgPlugin]:
    """Get the mypy plugin definition.
    """
    # ignore version argument if the plugin works with all mypy versions.
    return CgRequestArgPlugin
