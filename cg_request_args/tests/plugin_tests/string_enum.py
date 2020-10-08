import typing as t

from cg_request_args import StringEnum

non_literal = 'Hel' + 'o'
StringEnum(  # E:r The arguments to "StringEnum" should all be literals.*
    non_literal
)
b = StringEnum('a', 'b', 'c')
reveal_type(
    b  # N: Revealed type is 'cg_request_args.StringEnum[Union[Literal['a'], Literal['b'], Literal['c']]]'
)
