import typing as t

from cg_request_args import BaseFixedMapping

BaseFixedMapping.from_typeddict(t.Union[str, int])  # E:r The argument to `from_typeddict` should be a typeddict type.*; E:r Argument 1.* type "object". expected "Type\[Any\]".*
