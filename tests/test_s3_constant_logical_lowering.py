from __future__ import annotations

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_lowering_constant_logical_and_or_not_to_const() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    v1: tryte = -1 & -1\n"
        "    v2: tryte = -1 | 0\n"
        "    v3: tryte = ~(-1)\n"
        "    return 0\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    instructions = result.ir.functions[0].instructions

    opcodes = [instruction.opcode for instruction in instructions]
    assert IROpcode.MINIMUM not in opcodes
    assert IROpcode.MAXIMUM not in opcodes
    assert IROpcode.INVERT not in opcodes

    immediates = [
        instruction.immediate
        for instruction in instructions
        if instruction.opcode is IROpcode.CONST
    ]
    assert -1 in immediates
    assert 0 in immediates
    assert 1 in immediates


def test_lowering_partially_constant_logical_preserves_opcodes() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 1\n"
        "    v1: tryte = x & -1\n"
        "    v2: tryte = x | 0\n"
        "    v3: tryte = ~x\n"
        "    return 0\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    instructions = result.ir.functions[0].instructions

    opcodes = [instruction.opcode for instruction in instructions]
    assert IROpcode.MINIMUM in opcodes
    assert IROpcode.MAXIMUM in opcodes
    assert IROpcode.INVERT in opcodes
