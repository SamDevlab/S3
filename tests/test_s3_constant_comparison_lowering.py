from __future__ import annotations

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def _lower(source: str):
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    module = lower(program, model)
    verify_ir(module)
    return module


def _opcodes(module) -> list[IROpcode]:
    return [
        instruction.opcode
        for function in module.functions
        for block in function.blocks
        for instruction in block.instructions
    ]


def test_lowering_tryte_constant_comparison_emits_const_no_compare() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        "    return 10 > 5\n"
    )

    opcodes = _opcodes(module)
    assert IROpcode.COMPARE not in opcodes
    assert IROpcode.BRANCH3 not in opcodes
    assert IROpcode.CONST in opcodes


def test_lowering_string_constant_comparison_emits_const_no_compare() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        '    return "def" > "abc"\n'
    )

    opcodes = _opcodes(module)
    assert IROpcode.COMPARE not in opcodes
    assert IROpcode.BRANCH3 not in opcodes
    assert IROpcode.CONST in opcodes


def test_lowering_non_constant_comparison_emits_compare_instruction() -> None:
    module = _lower(
        "fn test(x: tryte) -> trit:\n"
        "    return x > 5\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    opcodes = _opcodes(module)
    assert IROpcode.COMPARE in opcodes
    assert IROpcode.BRANCH3 in opcodes
