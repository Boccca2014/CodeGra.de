import typing as t

from cg_request_args import BaseFixedMapping

BaseFixedMapping.from_typeddict(  # E:r The argument to `from_typeddict` should be a typeddict type.*
    t.Union[str, int]  # E:r Argument 1.* type "object". expected "Type\[Any\]".*
)
