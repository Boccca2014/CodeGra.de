import typing as t

from typing_extensions import Literal

from cg_request_args import (
    SimpleValue, FixedMapping, OptionalArgument, RequiredArgument
)

FixedMapping(  # E:r Key 'a' was already present, but given again as argument 2\..*
    RequiredArgument('a', SimpleValue(int), ''),
    RequiredArgument('a', SimpleValue(int), ''),
)

arg: RequiredArgument[int, Literal[5]] = ...  # type: ignore
FixedMapping(arg)  # E:r Key should be of type string, but was of type int for argument 1.*

arg2: RequiredArgument[int, int] = ...  # type: ignore
FixedMapping(arg2)  # E:r Second parameter of the argument should be a literal, this was not the case for argument 1.*
FixedMapping(t.cast(t.Any, ...))  # E:r Argument 1 was an "Any" which is not allowed as an argument to FixedMapping.*

non_literal = 'hell' + 'o'
RequiredArgument(non_literal, SimpleValue(str), '')  # E:r The key to the _Argument constructor should be a literal.*

map1 = FixedMapping(RequiredArgument('b', SimpleValue(str), ''))
map1.add_tag(non_literal, 'literal')  # E:r The key to FixedMapping.add_tag should be a literal.*
map1.add_tag('literal', non_literal)  # E:r The value to FixedMapping.add_tag should be a literal.*
map1.add_tag(t.cast(Literal[5], 5), 'literal')  # E:r The key to FixedMapping.add_tag should be a literal.*; E:r Argument 1 to "add_tag" of "FixedMapping" has incompatible type "Literal\[5\]".*
