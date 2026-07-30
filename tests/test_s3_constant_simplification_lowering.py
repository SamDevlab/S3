from __future__ import annotations

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_lowering_constant_simplification_addition_no_add_op() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    a: tryte = x + 0\n"
        "    return a\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    opcodes = [
        instruction.opcode
        for function in result.ir.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    assert IROpcode.ADD not in opcodes


def test_lowering_constant_simplification_double_negate_no_invert() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    a: tryte = -(-x)\n"
        "    return a\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    opcodes = [
        instruction.opcode
        for function in result.ir.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    assert IROpcode.INVERT not in opcodes
