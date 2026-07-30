from __future__ import annotations

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_lowering_constant_if_true_eliminates_dead_branch() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    match -1:\n"
        "        -1:\n"
        "            mut a: tryte = 10\n"
        "        else:\n"
        "            mut b: tryte = 20\n"
        "    return 0\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    opcodes = [
        instruction.opcode
        for function in result.ir.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    assert IROpcode.BRANCH3 not in opcodes


def test_lowering_constant_if_false_eliminates_dead_branch() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    match 0:\n"
        "        -1:\n"
        "            mut a: tryte = 10\n"
        "        else:\n"
        "            mut b: tryte = 20\n"
        "    return 0\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    opcodes = [
        instruction.opcode
        for function in result.ir.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    assert IROpcode.BRANCH3 not in opcodes
