from __future__ import annotations

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_lowering_propagated_constants_emits_const() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    a: tryte = 5\n"
        "    b: tryte = a\n"
        "    c: tryte = b + 3\n"
        "    return c\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    instructions = result.ir.functions[0].instructions

    opcodes = [instruction.opcode for instruction in instructions]
    assert IROpcode.ADD not in opcodes

    immediates = [
        instruction.immediate
        for instruction in instructions
        if instruction.opcode is IROpcode.CONST
    ]
    assert 8 in immediates


def test_lowering_mutable_variable_does_not_propagate_const() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 5\n"
        "    b: tryte = a\n"
        "    return b\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    instructions = result.ir.functions[0].instructions

    opcodes = [instruction.opcode for instruction in instructions]
    assert IROpcode.LOAD in opcodes or IROpcode.MOVE in opcodes
