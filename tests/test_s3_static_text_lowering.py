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


def test_lowering_emits_static_string_table_and_const_str() -> None:
    module = _lower(
        "fn pick(left: string, right: string) -> string:\n"
        "    return right\n"
        "fn main() -> tryte:\n"
        '    first: string = "hello"\n'
        '    second: string = pick(first, "olá")\n'
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "hello"),
        ("s1", "olá"),
    ]
    main = module.functions[1]
    const_str = [
        instruction
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CONST_STR
    ]
    assert [instruction.static_string for instruction in const_str] == ["s0", "s1"]
    assert all(
        main.registers[instruction.result].type is IRType.STRING
        for instruction in const_str
        if instruction.result is not None
    )


def test_lowering_preserves_string_parameter_and_return_types() -> None:
    module = _lower(
        "fn identity(value: string) -> string:\n"
        "    return value\n"
        "fn main() -> tryte:\n"
        '    text: string = identity("x")\n'
        "    return 0\n"
    )

    identity = module.functions[0]
    assert identity.return_type is IRType.STRING
    assert identity.parameters[0].type is IRType.STRING
    assert identity.registers[0].type is IRType.STRING


def test_lowering_mutable_string_binding_uses_string_memory_slot() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    mut current: string = "first"\n'
        '    current = "second"\n'
        "    return 0\n"
    )

    main = module.functions[0]
    string_memories = [
        memory
        for memory in main.memory_objects
        if memory.element_type is IRType.STRING
    ]
    assert [(memory.length, memory.mutable) for memory in string_memories] == [
        (1, True),
    ]
    assert sum(
        1
        for instruction in main.instructions
        if instruction.opcode is IROpcode.STORE
        and instruction.memory == string_memories[0].index
    ) == 2


def test_lowering_match_expression_can_select_static_string_value() -> None:
    module = _lower(
        "fn select(selector: trit) -> string:\n"
        "    return match selector:\n"
        '        -1: "negative"\n'
        '        0: "zero"\n'
        '        1: "positive"\n'
        "fn main() -> tryte:\n"
        '    value: string = select(0)\n'
        "    return 0\n"
    )



    main = module.functions[0]
    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "negative"),
        ("s1", "zero"),
        ("s2", "positive"),
    ]
    assert any(memory.element_type is IRType.STRING for memory in main.memory_objects)
    assert any(
        instruction.opcode is IROpcode.LOAD
        and main.registers[instruction.result].type is IRType.STRING
        for instruction in main.instructions
        if instruction.result is not None
    )


def test_lowering_folds_constant_static_text_concatenation_to_const_str() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    value: string = "TRET " + "r1"\n'
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "TRET r1"),
    ]
    main = module.functions[0]
    assert [
        instruction.static_string
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CONST_STR
    ] == ["s0"]
    assert IROpcode.ADD not in {
        instruction.opcode for instruction in main.instructions
    }


def test_lowering_deduplicates_folded_text_with_direct_literal() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    first: string = "a" + "b"\n'
        '    second: string = "ab"\n'
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "ab"),
    ]
    main = module.functions[0]
    assert [
        instruction.static_string
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CONST_STR
    ] == ["s0", "s0"]


def test_lowering_folds_grouped_empty_unicode_and_escaped_text() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    grouped: string = "a" + ("b" + "c")\n'
        '    empty: string = "" + ""\n'
        '    unicode: string = "á" + "β"\n'
        r'    escaped: string = "line\n" + "next"'
        "\n"
        r'    quoted: string = "a\"" + "b"'
        "\n"
        r'    slash: string = "a\\" + "b"'
        "\n"
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "abc"),
        ("s1", ""),
        ("s2", "áβ"),
        ("s3", "line\nnext"),
        ("s4", 'a"b'),
        ("s5", "a\\b"),
    ]
