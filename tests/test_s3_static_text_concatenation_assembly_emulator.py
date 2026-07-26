from __future__ import annotations

from bootstrap.s3.assembly import AssemblyOpcode, parse_assembly
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def _compile(source: str):
    return compile_source(source, mode=SyntaxMode.V0_6)


def test_folded_text_assembly_contains_only_final_static_entry() -> None:
    result = _compile(
        "fn main() -> tryte:\n"
        '    value: string = "TRET " + "r1"\n'
        "    return 0\n"
    )

    assert 's0 "TRET r1"' in result.assembly_text
    assert '"TRET "' not in result.assembly_text
    assert '"r1"' not in result.assembly_text
    assert "TADD" not in result.assembly_text
    assert "TCONST_STR" in result.assembly_text

    program = parse_assembly(result.assembly_text)
    assert [(entry.id, entry.value) for entry in program.static_strings] == [
        ("s0", "TRET r1"),
    ]
    assert any(
        instruction.opcode is AssemblyOpcode.TCONST_STR
        and instruction.static_string == "s0"
        for function in program.functions
        for instruction in function.instructions
    )


def test_folded_text_assembly_round_trip_preserves_static_data() -> None:
    result = _compile(
        "fn main() -> tryte:\n"
        '    first: string = "a" + "b"\n'
        '    second: string = "ab"\n'
        "    return 0\n"
    )

    program = parse_assembly(result.assembly_text)
    rendered = program.render()
    reparsed = parse_assembly(rendered)

    assert [(entry.id, entry.value) for entry in reparsed.static_strings] == [
        ("s0", "ab"),
    ]
    assert sum(
        1
        for function in reparsed.functions
        for instruction in function.instructions
        if instruction.opcode is AssemblyOpcode.TCONST_STR
    ) == 2


def test_folded_text_executes_through_hosted_calls_and_returns() -> None:
    result = _compile(
        "fn identity(value: string) -> string:\n"
        "    return value\n"
        "fn make() -> string:\n"
        '    return "TRET " + "r1"\n'
        "fn main() -> tryte:\n"
        '    mut value: string = identity("a" + "b")\n'
        "    value = make()\n"
        "    return 0\n"
    )

    program = parse_assembly(result.assembly_text)
    assert [(entry.id, entry.value) for entry in program.static_strings] == [
        ("s0", "TRET r1"),
        ("s1", "ab"),
    ]
    assert execute_assembly(result.assembly_text) == 0


def test_folded_empty_unicode_and_escaped_text_execute_in_hosted_emulator() -> None:
    result = _compile(
        "fn main() -> tryte:\n"
        '    empty: string = "" + ""\n'
        '    unicode: string = "á" + "β"\n'
        r'    escaped: string = "line\n" + "next"'
        "\n"
        "    return 0\n"
    )

    program = parse_assembly(result.assembly_text)
    assert [(entry.id, entry.value) for entry in program.static_strings] == [
        ("s0", ""),
        ("s1", "áβ"),
        ("s2", "line\nnext"),
    ]
    assert execute_assembly(result.assembly_text) == 0
