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


def _const_immediates(source: str) -> list[int]:
    module = _lower(source)
    function = module.functions[0]
    return [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
        and instruction.immediate is not None
    ]


def test_lowering_static_text_equal_true_to_trit_const() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        '    return "abc" == "abc"\n'
    )
    function = module.functions[0]
    assert module.static_strings == ()
    assert [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
    ] == [-1]
    assert function.registers[0].type is IRType.TRIT


def test_lowering_static_text_equal_false_to_trit_const() -> None:
    assert _const_immediates(
        "fn main() -> trit:\n"
        '    return "abc" == "xyz"\n'
    ) == [0]


def test_lowering_static_text_not_equal_results() -> None:
    assert _const_immediates(
        "fn main() -> trit:\n"
        '    return "abc" != "xyz"\n'
    ) == [-1]
    assert _const_immediates(
        "fn main() -> trit:\n"
        '    return "abc" != "abc"\n'
    ) == [0]


def test_lowering_static_text_equality_folds_concatenation_before_ir() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        '    return ("a" + "b") == "ab"\n'
    )
    function = module.functions[0]
    opcodes = {instruction.opcode for instruction in function.instructions}
    assert module.static_strings == ()
    assert IROpcode.CONST_STR not in opcodes
    assert IROpcode.ADD not in opcodes
    assert IROpcode.COMPARE not in opcodes
    assert [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
    ] == [-1]


def test_lowering_static_text_equality_handles_empty_escapes_and_unicode() -> None:
    assert _const_immediates(
        "fn main() -> trit:\n"
        '    return "" == ""\n'
    ) == [-1]
    assert _const_immediates(
        "fn main() -> trit:\n"
        r'    return "\n" == "\n"'
        "\n"
    ) == [-1]
    assert _const_immediates(
        "fn main() -> trit:\n"
        r'    return "\"" == "\""'
        "\n"
    ) == [-1]
    assert _const_immediates(
        "fn main() -> trit:\n"
        r'    return "\\" == "\\"'
        "\n"
    ) == [-1]
    assert _const_immediates(
        "fn main() -> trit:\n"
        '    return "é" == "é"\n'
    ) == [-1]


def test_lowering_preserves_interning_for_text_used_as_value() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    kept: string = "kept"\n'
        '    same: trit = ("a" + "b") == "ab"\n'
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "kept"),
    ]


def test_lowering_numeric_equality_still_uses_compare_path() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        "    return 1 == 1\n"
    )
    function = module.functions[0]
    assert IROpcode.COMPARE in {
        instruction.opcode for instruction in function.instructions
    }
