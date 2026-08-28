from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

from tools.build_stage1_compiler import build_stage1


ROOT = Path(__file__).resolve().parents[1]
LINUX_NATIVE = platform.system() == "Linux" and platform.machine().lower() in {
    "x86_64",
    "amd64",
}


def _run_stage1(executable: Path, source: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )


def test_general_emitter_is_closed_over_preserved_ir() -> None:
    source = (ROOT / "selfhost" / "compiler" / "s3c_stage1.s3").read_text(
        encoding="utf-8"
    )
    assert "general_emitter_possible" in source
    assert "emit_general_literal_function" in source
    assert "function_flags[general_scan] == 2" in source
    assert "function_flags[general_kind_scan] == 2" in source
    assert "function_flags[general_literal_scan] == 2" in source
    assert "function_flags[general_parameter_scan] == 2" in source
    assert "function_flags[general_parameter_type_scan] == 2" in source
    assert "function_flags[general_emit_index] == 2" in source
    assert "ir_function_return_type[general_scan] == 2" in source
    assert "function_statements[general_literal_scan] == 1" in source
    assert "function_count > 1" in source
    assert "s3_stage1_exit(0)" in source
    assert "parameter_count < 70" in source
    assert "ir_parameter_owner" in source
    assert "ir_parameter_mutability" in source
    assert "ir_parameter_value_id" in source
    assert "ir_parameter_mutability[parameter_count] = 0" in source
    assert "ir_parameter_value_id[parameter_count] = parameter_count" in source
    assert "emit_general_parameter_function" in source
    assert "ir_return_operand[general_emit_index]" in source
    assert "ir_function_param_count[general_parameter_scan] < 7" in source
    assert "general_parameter_type_end <= 70" in source
    assert "ir_local_record_count == local_count" in source
    assert "ir_local_value_id[local_rebase_index] = parameter_count + local_rebase_index" in source
    assert "mut ir_semantic_value_records: i64[365]" in source
    assert "ir_semantic_value_records[parameter_type_slot] = pack_ir_record(1, ir_parameter_owner[parameter_type_slot]" in source
    assert "ir_semantic_value_records[parameter_count + local_rebase_index] = pack_ir_record(2, ir_local_owner[local_rebase_index]" in source
    assert "match parameter_count + ir_local_record_count < 365:" in source
    assert "match local_count > 0:" in source
    assert "local_verify_index = 0" in source
    assert "ir_semantic_value_records[parameter_count + local_verify_index]" in source


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_general_emitter_emits_multiple_literal_functions(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1")
    source = (
        b"fn helper() -> tryte:\n"
        b"    return 7\n"
        b"fn main() -> tryte:\n"
        b"    return 9\n"
    )
    compiled = _run_stage1(executable, source)
    assert compiled.returncode == 0
    assert compiled.stderr == b""
    assert b".globl s3_fn_" in compiled.stdout
    assert b"call s3_fn_36" in compiled.stdout
    assert b"mov eax, 7" in compiled.stdout
    assert b"mov eax, 9" in compiled.stdout


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_general_emitter_emits_first_parameter_return(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1")
    source = (
        b"fn identity(x: i64) -> i64:\n"
        b"    return x\n"
        b"fn main() -> tryte:\n"
        b"    return 9\n"
    )
    compiled = _run_stage1(executable, source)
    assert compiled.returncode == 0
    assert compiled.stderr == b""
    assert b"mov rax, rdi" in compiled.stdout
    assert b"mov eax, 9" in compiled.stdout


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_general_emitter_emits_selected_parameter_return(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1")
    source = (
        b"fn select(a: i64, b: i64, c: i64) -> i64:\n"
        b"    return c\n"
        b"fn main() -> tryte:\n"
        b"    return 9\n"
    )
    compiled = _run_stage1(executable, source)
    assert compiled.returncode == 0
    assert compiled.stderr == b""
    assert b"mov rax, rdx" in compiled.stdout
    assert b"mov eax, 9" in compiled.stdout
