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


def _const_immediates(source: str) -> list[int]:
    module = _lower(source)
    function = module.functions[0]
    return [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
        and instruction.immediate is not None
    ]


def test_lowering_static_text_len_literal_to_numeric_const() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    return len("abc")\n'
    )

    function = module.functions[0]
    assert module.static_strings == ()
    assert IROpcode.CONST_STR not in {
        instruction.opcode for instruction in function.instructions
    }
    assert [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
    ] == [3]


def test_lowering_static_text_len_concatenation_to_single_numeric_const() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    return len("hello" + " world")\n'
    )

    function = module.functions[0]
    assert module.static_strings == ()
    assert IROpcode.ADD not in {
        instruction.opcode for instruction in function.instructions
    }
    assert IROpcode.CONST_STR not in {
        instruction.opcode for instruction in function.instructions
    }
    assert [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
    ] == [11]


def test_lowering_static_text_len_grouped_empty_escapes_and_unicode() -> None:
    assert _const_immediates(
        "fn main() -> tryte:\n"
        '    return len(("a" + "b") + "c")\n'
    ) == [3]
    assert _const_immediates(
        "fn main() -> tryte:\n"
        '    return len("")\n'
    ) == [0]
    assert _const_immediates(
        "fn main() -> tryte:\n"
        r'    return len("\n")'
        "\n"
    ) == [1]
    assert _const_immediates(
        "fn main() -> tryte:\n"
        r'    return len("\"")'
        "\n"
    ) == [1]
    assert _const_immediates(
        "fn main() -> tryte:\n"
        r'    return len("\\")'
        "\n"
    ) == [1]
    assert _const_immediates(
        "fn main() -> tryte:\n"
        '    return len("é")\n'
    ) == [1]


def test_lowering_does_not_intern_text_used_only_for_len() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    kept: string = "kept"\n'
        '    return len("hidden" + " text")\n'
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "kept"),
    ]
