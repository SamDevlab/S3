from __future__ import annotations

import pytest

from bootstrap.s3.assembly import AssemblyType, parse_assembly
from bootstrap.s3.emulator import Emulator, EmulatorError, execute_assembly
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_emulator_executes_static_string_bindings_calls_and_returning_main_tryte() -> None:
    assembly = compile_source(
        "fn choose(left: string, right: string) -> string:\n"
        "    return right\n"
        "fn main() -> tryte:\n"
        '    mut current: string = "first"\n'
        '    current = choose(current, "second")\n'
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    ).assembly

    assert execute_assembly(assembly) == 0


def test_emulator_stores_static_string_handles_in_string_memory() -> None:
    assembly = compile_source(
        "fn main() -> tryte:\n"
        '    mut current: string = "first"\n'
        '    current = "second"\n'
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    ).assembly
    captured: list[dict[int, list[int | str | None]]] = []

    assert Emulator().execute(assembly, capture_memory=captured) == 0
    main = assembly.functions[0]
    string_memory = next(
        memory
        for memory in main.memory_objects
        if memory.element_type is AssemblyType.STRING
    )
    assert captured[0][string_memory.index] == ["s1"]


def test_emulator_can_return_string_handle_for_manual_assembly_entry() -> None:
    program = parse_assembly(
        ".s3asm 0.5.0\n"
        "\n"
        ".data\n"
        's0 "hello"\n'
        "\n"
        ".function main -> string\n"
        "    .register r0, string\n"
        ".label entry\n"
        "    TCONST_STR r0, s0\n"
        "    TRET r0\n"
        ".end\n"
    )

    assert Emulator().execute(program) == "s0"


def test_emulator_rejects_unknown_static_string_handle() -> None:
    program = parse_assembly(
        ".s3asm 0.5.0\n"
        "\n"
        ".data\n"
        's0 "hello"\n'
        "\n"
        ".function main -> tryte\n"
        "    .register r0, string\n"
        "    .register r1, tryte\n"
        ".label entry\n"
        "    TCONST_STR r0, s1\n"
        "    TCONST r1, 0\n"
        "    TRET r1\n"
        ".end\n"
    )

    with pytest.raises(EmulatorError, match="unknown static string 's1'"):
        Emulator().validate(program)


def test_emulator_rejects_numeric_opcodes_on_string_registers() -> None:
    program = parse_assembly(
        ".s3asm 0.5.0\n"
        "\n"
        ".data\n"
        's0 "hello"\n'
        "\n"
        ".function main -> string\n"
        "    .register r0, string\n"
        "    .register r1, string\n"
        ".label entry\n"
        "    TCONST_STR r0, s0\n"
        "    TADD r1, r0, r0\n"
        "    TRET r1\n"
        ".end\n"
    )

    with pytest.raises(EmulatorError, match="TADD does not support string values"):
        Emulator().validate(program)
