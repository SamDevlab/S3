from __future__ import annotations

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_lowering_while_false_eliminates_body() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    while 0:\n"
        "        mut a: tryte = 10\n"
        "        a = a + 1\n"
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


def test_lowering_constant_match_statement_eliminates_dead_branches() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    match 0:\n"
        "        -1:\n"
        "            mut x: tryte = 1\n"
        "        0:\n"
        "            mut y: tryte = 2\n"
        "        1:\n"
        "            mut z: tryte = 3\n"
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


def test_lowering_constant_match_expression_eliminates_dead_branches() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    val: tryte = match 1:\n"
        "        -1: 10\n"
        "        0: 20\n"
        "        1: 30\n"
        "    return val\n"
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
