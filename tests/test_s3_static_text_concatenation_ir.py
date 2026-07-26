from __future__ import annotations

from bootstrap.s3.ir import IROpcode, IRType
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


def test_folded_static_text_ir_contains_only_final_const_str() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    value: string = "TRET " + "r1"\n'
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "TRET r1"),
    ]
    opcodes = _opcodes(module)
    assert opcodes.count(IROpcode.CONST_STR) == 1
    assert IROpcode.ADD not in opcodes
    assert set(IROpcode) == {
        IROpcode.CONST,
        IROpcode.CONST_STR,
        IROpcode.MOVE,
        IROpcode.INVERT,
        IROpcode.ADD,
        IROpcode.MINIMUM,
        IROpcode.MAXIMUM,
        IROpcode.COMPARE,
        IROpcode.CALL,
        IROpcode.LOAD,
        IROpcode.STORE,
        IROpcode.RETURN,
        IROpcode.JUMP,
        IROpcode.BRANCH3,
    }


def test_folded_static_text_ir_metadata_is_final_utf8_content() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    text: string = "á" + "β"\n'
        "    return 0\n"
    )

    entry = module.static_strings[0]
    assert entry.value == "áβ"
    assert entry.utf8_bytes == (195, 161, 206, 178)
    assert entry.byte_count == 4
    assert (
        entry.sha256
        == "394946a39f6be5bcde40e7802ce19425370220b8556c19f1131b1a9112568273"
    )


def test_folded_static_text_ir_deduplicates_across_functions() -> None:
    module = _lower(
        "fn left() -> string:\n"
        '    return "a" + "b"\n'
        "fn right() -> string:\n"
        '    return "ab"\n'
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "ab"),
    ]
    assert [
        instruction.static_string
        for function in module.functions
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST_STR
    ] == ["s0", "s0"]


def test_folded_static_text_ir_register_type_is_string() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    value: string = ("a" + "b") + "c"\n'
        "    return 0\n"
    )

    main = module.functions[0]
    const_str = next(
        instruction
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CONST_STR
    )
    assert const_str.result is not None
    assert main.registers[const_str.result].type is IRType.STRING
