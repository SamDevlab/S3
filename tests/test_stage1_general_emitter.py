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
    assert "ir_function_return_type[general_scan] == 2" in source
    assert "function_statements[general_literal_scan] == 1" in source
    assert "function_count > 1" in source
    assert "s3_stage1_exit(0)" in source
    assert "parameter_count < 64" in source


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
