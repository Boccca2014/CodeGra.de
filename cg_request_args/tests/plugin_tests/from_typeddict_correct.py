import typing as t

from typing_extensions import TypedDict

from cg_request_args import BaseFixedMapping


class Base(TypedDict):
    a: int

class Inner(Base):
    b: t.List[int]

parser = BaseFixedMapping.from_typeddict(Inner)

reveal_type(parser)  # N: Revealed type is 'cg_request_args.BaseFixedMapping[TypedDict({'a': builtins.int, 'b': builtins.list[builtins.int]})]'
