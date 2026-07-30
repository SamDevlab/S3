from __future__ import annotations

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_lowering_constant_match_statement_eliminates_branch3() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    match -1:\n"
        "        -1:\n"
        "            mut x: tryte = 10\n"
        "        0:\n"
        "            mut y: tryte = 20\n"
        "        else:\n"
        "            mut z: tryte = 30\n"
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


def test_lowering_constant_match_expression_eliminates_branch3() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    res: tryte = match 1:\n"
        "        -1: 100\n"
        "        0: 200\n"
        "        1: 300\n"
        "    return res\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    opcodes = [
        instruction.opcode
        for function in result.ir.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    assert IROpcode.BRANCH3 not in opcodes
    assert IROpcode.STORE not in opcodes
