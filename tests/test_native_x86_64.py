from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.assembly import AssemblyOpcode, parse_assembly
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativePlatformError,
    NativeToolchain,
    generate_native_assembly,
    layout_frame,
)
from bootstrap.s3.backends.x86_64.emitter import (
    mangle_block,
    mangle_function,
)
from bootstrap.s3.cli import main as cli_main
from bootstrap.s3.emulator import Emulator, EmulatorError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).parents[1]


def _ordered_entry_program(order: tuple[str, ...]):
    blocks = {
        "before": """\
.label before
    TCONST r0, 99
    TRET r0
""",
        "entry": """\
.label entry
    TCONST r0, 6
    TRET r0
""",
        "after": """\
.label after
    TCONST r0, 77
    TRET r0
""",
    }
    body = "".join(blocks[label] for label in order)
    return parse_assembly(
        """\
.function main -> tryte
    .register r0, tryte
"""
        + body
        + ".end\n"
    )


def _compilation(filename: str):
    source = (ROOT / "examples" / filename).read_text(encoding="utf-8")
    return compile_source(source, mode=SyntaxMode.V0_6)


def test_native_generation_is_deterministic() -> None:
    program = _compilation("recursive_memory.s3").assembly
    assert generate_native_assembly(program) == generate_native_assembly(program)


def test_frame_layout_is_aligned_deterministic_and_non_overlapping() -> None:
    function = _compilation("static_array.s3").assembly.functions[0]
    first = layout_frame(function)
    second = layout_frame(function)
    assert first == second
    assert first.frame_size % 16 == 0
    occupied: set[int] = set()
    for region in first.regions:
        assert region.offset < 0
        assert region.offset % region.alignment == 0
        addresses = set(region.addresses())
        assert not occupied.intersection(addresses)
        occupied.update(addresses)


def test_frame_layout_accounts_for_array_sizes_and_logical_cost() -> None:
    program = parse_assembly(
        """\
.function main -> tryte
    .register r0, tryte
    .register r1, trit
    .memory m0, trit, 5, mutable
    .memory m1, tryte, 7, immutable
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    )
    layout = layout_frame(program.functions[0])
    assert layout.memory(0).data.size == 5
    assert layout.memory(0).initialized.size == 5
    assert layout.memory(1).data.size == 14
    assert layout.memory(1).initialized.size == 7
    assert layout.logical_memory_trits == 5 + 7 * 6
    assert {slot.index for slot in layout.registers} == {0, 1}


def test_native_backend_emits_every_current_opcode() -> None:
    programs = [
        _compilation(path.name).assembly
        for path in sorted((ROOT / "examples").glob("*.s3"))
    ]
    programs.append(
        compile_source(
            "fn main() -> tryte:\n"
            '    text: string = "native"\n'
            "    return 0\n",
            mode=SyntaxMode.V0_6,
        ).assembly
    )
    programs.append(
        compile_source(
            """\
fn main() -> tryte {
    tryte left = -10;
    tryte right = 4;
    tryte minimum = left & right;
    return minimum | right;
}
""",
            mode=SyntaxMode.V0_5,
        ).assembly
    )
    seen = {
        instruction.opcode
        for program in programs
        for function in program.functions
        for instruction in function.instructions
    }
    assert seen == set(AssemblyOpcode)
    native = "\n".join(generate_native_assembly(program) for program in programs)
    assert "__s3_tryte_min" in native
    assert "__s3_tryte_max" in native
    assert "__s3_fail_bounds" in native
    assert "__s3_fail_uninitialized_memory" in native
    assert "__s3_fail_immutable_memory" in native
    assert "TSUB" not in native


def test_more_than_six_arguments_use_system_v_stack_slots() -> None:
    program = compile_source(
        """\
fn eighth(
    a: tryte, b: tryte, c: tryte, d: tryte,
    e: tryte, f: tryte, g: tryte, h: tryte
) -> tryte {
    return h;
}
fn main() -> tryte {
    return eighth(0, 1, 2, 3, 4, 5, 6, 7);
}
""",
        mode=SyntaxMode.V0_5,
    ).assembly
    native = generate_native_assembly(program)
    assert "mov rax, qword ptr [rbp + 16]" in native
    assert "mov rax, qword ptr [rbp + 24]" in native
    assert native.count("    push rax") >= 2
    assert "    call s3_eighth" in native
    assert "    add rsp, 16" in native


def test_seventh_argument_inserts_alignment_padding() -> None:
    program = compile_source(
        """\
fn seventh(
    a: tryte, b: tryte, c: tryte, d: tryte,
    e: tryte, f: tryte, g: tryte
) -> tryte {
    return g;
}
fn main() -> tryte {
    return seventh(0, 1, 2, 3, 4, 5, 6);
}
""",
        mode=SyntaxMode.V0_5,
    ).assembly
    native = generate_native_assembly(program)
    call = native.index("    call s3_seventh")
    assert "    sub rsp, 8" in native[:call]
    assert "    add rsp, 16" in native[call:]


def test_symbols_and_block_labels_are_safe_and_unambiguous() -> None:
    assert mangle_function("main") == "s3_main"
    assert (
        mangle_block("a_b", "c")
        != mangle_block("a", "b_c")
    )


def test_backend_rejects_memory_over_configured_limit_before_emission() -> None:
    program = parse_assembly(
        """\
.function main -> tryte
    .register r0, tryte
    .memory m0, tryte, 2
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    )
    with pytest.raises(
        EmulatorError,
        match=r"function 'main' requires 12 logical trits.*limit is 11",
    ):
        generate_native_assembly(program, max_memory_trits=11)


def test_runtime_has_no_libc_or_python_entry_path() -> None:
    native = generate_native_assembly(_compilation("first.s3").assembly)
    assert ".globl _start" in native
    assert "call s3_main" in native
    assert "syscall" in native
    assert "program returned: " in native
    assert "libc" not in native.lower()
    assert "python" not in native.lower()


def test_toolchain_reports_unsupported_non_linux_host(monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    with pytest.raises(NativePlatformError, match="Linux x86-64"):
        NativeToolchain.detect()


def test_native_asm_cli_writes_requested_output(tmp_path: Path) -> None:
    output = tmp_path / "first.s"
    assert cli_main(
        [
            "--source-syntax", "0.6",
            "native-asm",
            str(ROOT / "examples" / "first.s3"),
            "-o",
            str(output),
        ]
    ) == 0
    native = output.read_text(encoding="utf-8")
    assert ".globl _start" in native
    assert "s3_main:" in native


def test_invalid_trit_control_state_is_rejected_before_emission() -> None:
    program = parse_assembly(
        """\
.function main -> trit
    .register r0, trit
.label entry
    TCONST r0, 2
    TBR3 r0, negative, zero, positive
.label negative
    TRET r0
.label zero
    TRET r0
.label positive
    TRET r0
.end
"""
    )
    with pytest.raises(EmulatorError, match="trit value 2 is outside"):
        generate_native_assembly(program)


@pytest.mark.parametrize(
    "order",
    (
        ("entry", "before", "after"),
        ("before", "entry", "after"),
        ("before", "after", "entry"),
    ),
)
def test_native_function_explicitly_enters_entry_block(
    order: tuple[str, ...],
) -> None:
    program = _ordered_entry_program(order)
    function = program.functions[0]
    assert tuple(block.label for block in function.blocks) == order
    Emulator().validate(program, entry="main")
    assert Emulator().execute(program) == 6

    native = generate_native_assembly(program)
    entry_jump = f"    jmp {mangle_block('main', 'entry')}"
    first_physical_label = f"{mangle_block('main', order[0])}:"
    assert native.index(entry_jump) < native.index(first_physical_label)


def test_each_native_function_enters_its_own_entry_block() -> None:
    program = parse_assembly(
        """\
.function helper -> tryte
    .register r0, tryte
.label helper_dead
    TCONST r0, 99
    TRET r0
.label entry
    TCONST r0, 6
    TRET r0
.end

.function main -> tryte
    .register r0, tryte
    .register r1, tryte
.label main_dead
    TCONST r0, 77
    TRET r0
.label entry
    TCALL r1, helper
    TRET r1
.end
"""
    )
    assert Emulator().execute(program) == 6
    native = generate_native_assembly(program)
    assert f"    jmp {mangle_block('helper', 'entry')}" in native
    assert f"    jmp {mangle_block('main', 'entry')}" in native


def test_native_backend_rejects_function_without_entry() -> None:
    program = parse_assembly(
        """\
.function main -> tryte
    .register r0, tryte
.label other
    TCONST r0, 6
    TRET r0
.end
"""
    )
    with pytest.raises(EmulatorError, match="has no entry label"):
        generate_native_assembly(program)


def test_native_frame_limit_is_configurable_and_counted_per_function() -> None:
    program = _compilation("simple_call.s3").assembly
    native = generate_native_assembly(program, max_frames=4)
    assert "inc qword ptr [rip + __s3_frame_count]" in native
    assert "cmp qword ptr [rip + __s3_frame_count], 4" in native
    assert "dec qword ptr [rip + __s3_frame_count]" in native
    assert "__s3_fail_frame_limit" in native
    assert "__s3_frame_count:" in native


def test_native_frame_limit_rejects_invalid_configuration() -> None:
    with pytest.raises(
        NativeBackendError,
        match="max_frames must be at least 1",
    ):
        generate_native_assembly(_compilation("first.s3").assembly, max_frames=0)


def test_native_asm_cli_accepts_max_frames(
    tmp_path: Path,
) -> None:
    output = tmp_path / "limited.s"
    assert cli_main(
        [
            "--source-syntax", "0.6",
            "native-asm",
            str(ROOT / "examples" / "first.s3"),
            "-o",
            str(output),
            "--max-frames",
            "8",
        ]
    ) == 0
    assert "cmp qword ptr [rip + __s3_frame_count], 8" in output.read_text(
        encoding="utf-8"
    )


def test_native_failure_sites_have_deterministic_source_context() -> None:
    source = """\
fn main() -> tryte {
    return 364 + 1;
}
"""
    program = compile_source(source, mode=SyntaxMode.V0_5).assembly
    first = generate_native_assembly(program)
    second = generate_native_assembly(program)
    assert first == second
    assert "runtime error [overflow] in function 'main'\\n" in first
    assert "at source 2:16 (block entry, TADD)" in first
    assert "tryte result " in first
    assert " outside [-364, 364]\\n" in first


def test_manual_assembly_failure_site_reports_unknown_source_and_line() -> None:
    program = parse_assembly(
        """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TLOAD r1, m0, r0
    TRET r1
.end
"""
    )
    native = generate_native_assembly(program)
    assert (
        "runtime error [uninitialized memory] in function 'main'\\n"
        in native
    )
    assert "at source unknown (block entry, TLOAD, assembly line 7)" in native
    assert " is uninitialized in m0\\n" in native
