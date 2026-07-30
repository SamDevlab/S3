from __future__ import annotations

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_lowering_constant_arithmetic_emits_const() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    a: tryte = 10 + 5\n"
        "    b: tryte = 10 - 5\n"
        "    return 0\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    instructions = result.ir.functions[0].instructions

    opcodes = [instruction.opcode for instruction in instructions]
    assert IROpcode.ADD not in opcodes
    assert IROpcode.INVERT not in opcodes

    immediates = [
        instruction.immediate
        for instruction in instructions
        if instruction.opcode is IROpcode.CONST
    ]
    assert 15 in immediates
    assert 5 in immediates


def test_lowering_partially_constant_arithmetic_preserves_opcodes() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    a: tryte = x + 10\n"
        "    return 0\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    instructions = result.ir.functions[0].instructions

    opcodes = [instruction.opcode for instruction in instructions]
    assert IROpcode.ADD in opcodes
