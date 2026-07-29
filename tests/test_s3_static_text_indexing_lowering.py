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


def _const_immediates(source: str) -> list[int]:
    function = _lower(source).functions[0]
    return [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
        and instruction.immediate is not None
    ]


def test_lowering_materialized_static_text_index_uses_final_const_str_only() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    letter: string = "abc"[1]\n'
        "    return len(letter)\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "b"),
    ]
    opcodes = _opcodes(module)
    assert opcodes.count(IROpcode.CONST_STR) == 1
    assert IROpcode.LOAD not in opcodes
    assert IROpcode.COMPARE not in opcodes
    const_str = next(
        instruction
        for instruction in module.functions[0].instructions
        if instruction.opcode is IROpcode.CONST_STR
    )
    assert const_str.static_string == "s0"
    assert const_str.result is not None
    assert module.functions[0].registers[const_str.result].type is IRType.STRING


def test_lowering_static_text_index_inside_len_to_numeric_const() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    return len("abc"[2])\n'
    )

    assert module.static_strings == ()
    assert IROpcode.CONST_STR not in _opcodes(module)
    assert IROpcode.LOAD not in _opcodes(module)
    assert _const_immediates(
        "fn main() -> tryte:\n"
        '    return len("abc"[2])\n'
    ) == [1]


def test_lowering_static_text_index_equality_to_trit_const() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        '    return "abc"[1] == "b"\n'
    )

    assert module.static_strings == ()
    opcodes = _opcodes(module)
    assert IROpcode.CONST_STR not in opcodes
    assert IROpcode.LOAD not in opcodes
    assert IROpcode.COMPARE not in opcodes
    assert [
        instruction.immediate
        for instruction in module.functions[0].instructions
        if instruction.opcode is IROpcode.CONST
    ] == [-1]


def test_lowering_static_text_index_feeds_compile_time_concatenation() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    middle: string = "abc"[1]\n'
        '    value: string = "x" + middle\n'
        "    return len(value)\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "b"),
        ("s1", "xb"),
    ]
    assert IROpcode.ADD not in _opcodes(module)


def test_lowering_array_indexing_still_uses_load() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        "    values: tryte[3] = [1, 2, 3]\n"
        "    index: tryte = 1\n"
        "    return values[index]\n"
    )

    assert IROpcode.LOAD in _opcodes(module)
