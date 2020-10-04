import typing as t

from cg_request_args import (
    SimpleValue, FixedMapping, OptionalArgument, RequiredArgument
)

arg1 = RequiredArgument('help', SimpleValue(int), '')
reveal_type(arg1)  # N: Revealed type is 'cg_request_args.RequiredArgument[builtins.int*, Literal['help']]'
arg2 = OptionalArgument('help2', SimpleValue(str), '')
reveal_type(arg2)  # N: Revealed type is 'cg_request_args.OptionalArgument[builtins.str*, Literal['help2']]'
parser = FixedMapping(arg1, arg2)
reveal_type(parser)  # N: Revealed type is 'cg_request_args.FixedMapping[TypedDict({'help': builtins.int*, 'help2': Union[cg_maybe.Just[builtins.str*], cg_maybe._Nothing[builtins.str*]]})]'
parsed = parser.try_parse({})

parsed.help3  # E:r The _DictGetter\[.*\] does not have the attribute 'help3', available attributes:.*
reveal_type(parsed.help)  # N: Revealed type is 'builtins.int*'
reveal_type(parsed.help2)  # N: Revealed type is 'Union[cg_maybe.Just[builtins.str*], cg_maybe._Nothing[builtins.str*]]'
