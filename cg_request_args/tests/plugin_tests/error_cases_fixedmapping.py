import typing as t

from typing_extensions import Literal

from cg_request_args import (
    SimpleValue, FixedMapping, OptionalArgument, RequiredArgument
)

FixedMapping(  # E:r Key 'a' was already present, but given again as argument 2\..*
    RequiredArgument('a', SimpleValue.int, ''),
    RequiredArgument('a', SimpleValue.int, ''),
)

arg: RequiredArgument[int, Literal[5]] = ...  # type: ignore
FixedMapping(  # E:r Key should be of type string, but was of type int for argument 1.*
    arg
)

arg2: RequiredArgument[int, int] = ...  # type: ignore
FixedMapping(  # E:r Second parameter of the argument should be a literal, this was not the case for argument 1.*
    arg2
)
FixedMapping(  # E:r Argument 1 was an "Any" which is not allowed as an argument to FixedMapping.*
    t.cast(t.Any, ...)
)

non_literal = 'hell' + 'o'
RequiredArgument(  # E:r The key to the _Argument constructor should be a literal.*
    non_literal, SimpleValue.str, ''
)

map1 = FixedMapping(RequiredArgument('b', SimpleValue.str, ''))
map1.add_tag(  # E:r The key to FixedMapping.add_tag should be a literal.*
    non_literal, 'literal'
)
map1.add_tag('literal', non_literal)
map1.add_tag(  # E:r The key to FixedMapping.add_tag should be a literal.*
    t.cast(Literal[5], 5), 'literal'  # E:r Argument 1 to "add_tag" of "FixedMapping" has incompatible type "Literal\[5\]".*
)
