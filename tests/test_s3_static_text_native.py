from __future__ import annotations

import pytest

from bootstrap.s3.assembly import AssemblyType, parse_assembly
from bootstrap.s3.backends.x86_64 import NativeBackendError, generate_native_assembly, layout_frame
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_native_backend_emits_static_strings_in_rodata_and_loads_private_labels() -> None:
    assembly = compile_source(
        "fn identity(value: string) -> string:\n"
        "    return value\n"
        "fn main() -> tryte:\n"
        '    mut current: string = "hello"\n'
        '    current = identity("world")\n'
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    ).assembly
    native = generate_native_assembly(assembly)

    assert ".Ls0:\n    .asciz \"hello\"\n" in native
    assert ".Ls1:\n    .asciz \"world\"\n" in native
    assert "    lea rax, [rip + .Ls0]" in native
    assert "    lea rax, [rip + .Ls1]" in native
    assert "mov qword ptr" in native


def test_native_layout_stores_string_memory_slots_as_private_pointers() -> None:
    assembly = compile_source(
        "fn main() -> tryte:\n"
        '    mut current: string = "hello"\n'
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    ).assembly
    main = assembly.functions[0]
    string_memory = next(
        memory
        for memory in main.memory_objects
        if memory.element_type is AssemblyType.STRING
    )
    layout = layout_frame(main)
    slot = layout.memory(string_memory.index)

    assert slot.element_size == 8
    assert slot.data.size == 8
    assert layout.logical_memory_trits == 6


def test_native_backend_rejects_public_main_string_return() -> None:
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

    with pytest.raises(NativeBackendError, match="main' cannot return string"):
        generate_native_assembly(program)
