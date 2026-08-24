from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import generate_native_assembly
from bootstrap.s3.pipeline import compile_source
from tools.build_stage1_compiler import build_stage1


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
HOST_IO_PATH = ROOT / "selfhost" / "compiler" / "stage1_host_io.c"
MANIFEST_PATH = ROOT / "selfhost" / "compiler" / "compiler-sources.json"
LINUX_NATIVE = platform.system() == "Linux" and platform.machine().lower() in {
    "x86_64",
    "amd64",
}


def _stage1_source(value: int) -> bytes:
    return f"fn main() -> tryte:\n    return {value}\n".encode("ascii")


def _expected_assembly(value: int) -> bytes:
    return (
        ".intel_syntax noprefix\n"
        ".section .text\n"
        ".globl _start\n"
        ".type _start, @function\n"
        "_start:\n"
        "    mov eax, 60\n"
        f"    mov edi, {value}\n"
        "    syscall\n"
        "    ud2\n"
        ".size _start, .-_start\n"
        ".section .note.GNU-Stack,\"\",@progbits\n"
    ).encode("ascii")


def _run_stage1(executable: Path, source: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )


def test_canonical_source_manifest_is_deterministic_and_exact() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["schema"] == "s3.compiler.sources.v1"
    assert manifest["source_count"] == 1
    source = SOURCE_PATH.read_bytes()
    entry = manifest["sources"][0]
    assert entry["path"] == "selfhost/compiler/s3c_stage1.s3"
    assert entry["ordering"] == 0
    assert manifest["total_bytes"] == len(source)
    assert entry["sha256"] == hashlib.sha256(source).hexdigest()


def test_stage1_source_is_s3_logic_not_a_python_or_candidate_wrapper() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "compile_source" not in source
    assert "run_source" not in source
    assert "bootstrap.s3" not in source
    assert "candidate" not in source
    assert "checksum" not in source
    assert "fingerprint" not in source
    assert "prefix_is_valid" not in source
    assert "source_is_valid" not in source
    assert "parsed_number" not in source
    assert "scan_token" in source
    assert "token_kind" in source
    assert "ir_opcode" in source
    assert "ir_value: i64[64]" in source
    assert "emit_ir_return" in source
    assert "foreign fn s3_stage1_read_byte" in source
    assert "foreign fn s3_stage1_write_byte" in source


def test_stage1_source_exposes_bounded_compiler_pipeline() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for marker in (
        "function_names:",
        "function_types:",
        "valid_type_name",
        "emit_blocked",
    ):
        assert marker in source


def test_stage1_emitter_consumes_verified_ir_records() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "emit_ir_return(ir_opcode[0], ir_type[0], ir_value[0])" in source
    assert "emit_assembly(simple_value)" not in source
    assert "emit_ir_return(simple_value" not in source


def test_stage0_compiles_real_stage1_source_and_preserves_io_calls() -> None:
    result = compile_source(SOURCE_PATH.read_text(encoding="utf-8"))
    assembly = generate_native_assembly(result.assembly, max_memory_trits=131072)
    assert ".globl s3_main" in assembly
    assert "call s3_stage1_source_length" in assembly
    assert "call s3_stage1_read_byte" in assembly
    assert "call s3_stage1_write_byte" in assembly
    assert "call s3_stage1_exit" in assembly
    assert "compile_source" not in assembly


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_stage1_trivial_compile_and_native_execution(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1", assembly_output=tmp_path / "stage1.s")
    compiled = _run_stage1(executable, _stage1_source(7))
    assert compiled.returncode == 0
    assert compiled.stderr == b""
    assert compiled.stdout == _expected_assembly(7)

    assembly = tmp_path / "trivial.s"
    assembly.write_bytes(compiled.stdout)
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    assert compiler is not None
    object_path = tmp_path / "trivial.o"
    executable_path = tmp_path / "trivial"
    subprocess.run(
        [compiler, "-x", "assembler", "-c", str(assembly), "-o", str(object_path)],
        check=True,
    )
    subprocess.run(
        [
            compiler,
            "-nostdlib",
            "-no-pie",
            "-Wl,--build-id=none",
            str(object_path),
            "-o",
            str(executable_path),
        ],
        check=True,
    )
    native = subprocess.run([str(executable_path)], check=False, capture_output=True)
    assert native.returncode == 7
    assert native.stdout == b""
    assert native.stderr == b""


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_stage1_bootstrap_corpus_changes_output_and_stays_deterministic(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1")
    outputs = {}
    for value in (0, 7, 8, 180, -1):
        first = _run_stage1(executable, _stage1_source(value))
        second = _run_stage1(executable, _stage1_source(value))
        assert first.returncode == 0
        assert second.returncode == 0
        assert first.stderr == b""
        assert first.stdout == second.stdout
        assert first.stdout == _expected_assembly(value)
        outputs[value] = first.stdout
    assert len(set(outputs.values())) == len(outputs)


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_stage1_rejects_invalid_source_with_real_diagnostic(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1")
    invalid = _run_stage1(
        executable,
        b"fn main() -> tryte:\n    return nope\n",
    )
    assert invalid.returncode == 1
    assert invalid.stdout == b""
    assert invalid.stderr == b"S3_STAGE1_ERROR\n"


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_stage1_self_compile_attempt_reaches_emitter_boundary(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1")
    result = _run_stage1(executable, SOURCE_PATH.read_bytes())
    assert result.returncode == 2
    assert result.stdout == b""
    lines = result.stderr.splitlines()
    assert lines[-1] == b"S3_STAGE1_EMITTER_BLOCKED"
    assert lines[0].startswith(b"S3_STAGE1_AUDIT ")
    audit_values = lines[0].split()[1:]
    assert len(audit_values) == 26
    assert all(value.lstrip(b"-").isdigit() for value in audit_values)
    assert tuple(map(int, audit_values)) == (
        30,
        5,
        64,
        23,
        75,
        366,
        103,
        94,
        6,
        4,
        155,
        92,
        0,
        409,
        25,
        5,
        64,
        23,
        325,
        1212,
        926,
        363,
        3,
        104,
        6,
        103,
    )
