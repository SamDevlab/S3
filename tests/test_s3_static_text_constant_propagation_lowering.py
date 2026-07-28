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


def test_lowering_len_of_static_text_binding_to_const() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    message: string = "hello"\n'
        "    return len(message)\n"
    )

    main = module.functions[0]
    assert [
        instruction.immediate
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CONST
    ][-1] == 5
    assert IROpcode.COMPARE not in {instruction.opcode for instruction in main.instructions}


def test_lowering_static_text_binding_equality_to_const_trit() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        '    message: string = "hello"\n'
        '    return message == "hello"\n'
    )

    main = module.functions[0]
    assert [
        instruction.immediate
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CONST
    ][-1] == -1
    assert IROpcode.COMPARE not in {instruction.opcode for instruction in main.instructions}


def test_lowering_static_text_binding_inequality_to_const_trit() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        '    left: string = "hel"\n'
        '    right: string = "lo"\n'
        "    message: string = left + right\n"
        '    return message != "world"\n'
    )

    main = module.functions[0]
    assert [
        instruction.immediate
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CONST
    ][-1] == -1
    assert IROpcode.COMPARE not in {instruction.opcode for instruction in main.instructions}


def test_lowering_static_text_binding_concat_has_no_add_opcode() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    left: string = "hel"\n'
        '    right: string = "lo"\n'
        "    message: string = left + right\n"
        "    return len(message)\n"
    )

    main = module.functions[0]
    assert IROpcode.ADD not in {instruction.opcode for instruction in main.instructions}
    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "hel"),
        ("s1", "lo"),
        ("s2", "hello"),
    ]


def test_lowering_static_text_used_only_in_len_or_equality_is_not_interned() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    message: string = "hello"\n'
        '    same: trit = message == "hello"\n'
        "    return len(message)\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "hello"),
    ]


def test_lowering_numeric_and_array_behavior_remains_available() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        "    values: tryte[3] = [1, 2, 3]\n"
        "    same: trit = 1 == 1\n"
        "    return len(values)\n"
    )

    main = module.functions[0]
    assert IROpcode.COMPARE in {instruction.opcode for instruction in main.instructions}
    assert [
        instruction.immediate
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CONST
    ][-1] == 3
