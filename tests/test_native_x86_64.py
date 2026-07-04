from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.assembly import AssemblyOpcode, parse_assembly
from bootstrap.s3.backends.x86_64 import (
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
from bootstrap.s3.emulator import EmulatorError
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).parents[1]


def _compilation(filename: str):
    source = (ROOT / "examples" / filename).read_text(encoding="utf-8")
    return compile_source(source)


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
            """\
fn main() -> tryte {
    tryte left = -10;
    tryte right = 4;
    tryte minimum = left & right;
    return minimum | right;
}
"""
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
"""
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
"""
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
