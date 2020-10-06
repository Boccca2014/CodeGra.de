import typing as t

from cg_request_args import (
    SimpleValue, FixedMapping, OptionalArgument, RequiredArgument
)

map1 = FixedMapping(RequiredArgument('a', SimpleValue(int), ''))
map2 = FixedMapping(OptionalArgument('a', SimpleValue(int), ''))
map3 = FixedMapping(RequiredArgument('b', SimpleValue(str), ''))

map1.combine(map2)  # E:r Cannot combine typeddict, got overlapping key 'a'.*
map4 = map1.combine(map3)
reveal_type(
    map4  # N: Revealed type is 'cg_request_args.FixedMapping[TypedDict({'a': builtins.int*, 'b': builtins.str*})]'
)
