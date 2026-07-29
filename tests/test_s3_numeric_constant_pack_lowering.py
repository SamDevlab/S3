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


def _const_immediates(source: str) -> list[int]:
    function = _lower(source).functions[0]
    return [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
        and instruction.immediate is not None
    ]


def test_lowering_constant_arithmetic_emits_consts_without_runtime_add() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        "    base: tryte = 1\n"
        "    offset: tryte = 2\n"
        "    value: tryte = base + offset\n"
        "    return value\n"
    )

    opcodes = _opcodes(module)
    assert IROpcode.ADD not in opcodes
    assert 3 in _const_immediates(
        "fn main() -> tryte:\n"
        "    base: tryte = 1\n"
        "    offset: tryte = 2\n"
        "    value: tryte = base + offset\n"
        "    return value\n"
    )


def test_lowering_constant_comparison_emits_const_without_compare() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        "    value: trit = 2 == 2\n"
        "    return value\n"
    )

    assert IROpcode.COMPARE not in _opcodes(module)
    assert -1 in [
        instruction.immediate
        for instruction in module.functions[0].instructions
        if instruction.opcode is IROpcode.CONST
    ]


def test_lowering_constant_text_index_and_slice_do_not_lower_bounds() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    position: tryte = find("hello", "ll")\n'
        '    letter: string = "hello"[position]\n'
        "    start: tryte = 1\n"
        "    end: tryte = start + 3\n"
        '    part: string = "hello"[start:end]\n'
        "    return len(letter) + len(part)\n"
    )

    opcodes = _opcodes(module)
    assert IROpcode.CALL not in opcodes
    assert IROpcode.ADD not in opcodes
    assert IROpcode.LOAD not in opcodes
    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "l"),
        ("s1", "ell"),
    ]


def test_lowering_runtime_array_index_still_uses_load_and_store() -> None:
    module = _lower(
        "fn choose(index: tryte) -> tryte:\n"
        "    mut values: tryte[3] = [1, 2, 3]\n"
        "    values[index] = 5\n"
        "    return values[index]\n"
        "fn main() -> tryte:\n"
        "    return choose(1)\n"
    )

    opcodes = _opcodes(module)
    assert IROpcode.LOAD in opcodes
    assert IROpcode.STORE in opcodes
