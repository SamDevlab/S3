from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path

import pytest

from tools.build_stage1_compiler import build_stage1


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
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


def _typed_constant_lines(stderr: bytes) -> list[list[int]]:
    lines = []
    for line in stderr.splitlines():
        if line.startswith(b"S3_STAGE1_TYPED_CONSTANT "):
            fields = line.split()[1:]
            assert len(fields) == 7
            lines.append([int(field) for field in fields])
    return lines


def test_s12_canonical_keeps_semantic_constants_separate_from_storage() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for marker in (
        "s12_constant_count",
        "s12_stream_value_id",
        "s12_stream_cursor",
    ):
        assert marker in source
    assert "s12_constant_definition_records" not in source
    assert "ir_semantic_value_records" not in source
    assert "parameter_count + ir_local_record_count + s12_constant_count < 365" not in source
    assert "s12_constant_count = 365 - parameter_count - ir_local_record_count" not in source
    assert "pack_ir_record(3, s12_final_owner_quotient - 1" not in source
    assert "s12_verify_anchor" not in source
    assert "s12_verify_length" not in source


@pytest.fixture(scope="module")
def stage1_executable(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not LINUX_NATIVE:
        pytest.skip("requires Linux x86-64 native execution")
    root = tmp_path_factory.mktemp("stage1-typed-constants")
    return build_stage1(root / "s3c-stage1")


@pytest.mark.s3_native
def test_s12_numeric_literals_have_typed_ids_and_stable_anchors(
    stage1_executable: Path,
) -> None:
    source = b"fn main() -> tryte:\n    return 1 + 2\n"
    first = _run_stage1(stage1_executable, source)
    second = _run_stage1(stage1_executable, source)

    first_constants = _typed_constant_lines(first.stderr)
    second_constants = _typed_constant_lines(second.stderr)
    assert first_constants == second_constants
    assert hashlib.sha256(
        b"\n".join(b" ".join(str(value).encode() for value in row) for row in first_constants)
    ).hexdigest() == hashlib.sha256(
        b"\n".join(b" ".join(str(value).encode() for value in row) for row in second_constants)
    ).hexdigest()
    assert first_constants == [
        [0, 0, 2, 1, source.index(b"1"), 2, -1],
        [1, 0, 2, 2, source.index(b"2"), 2, -1],
    ]
    assert first.returncode != 0
    assert b"S3_STAGE1_EMITTER_BLOCKED" not in first.stderr


@pytest.mark.s3_native
def test_s12_initializer_constant_is_independent_of_local_storage(
    stage1_executable: Path,
) -> None:
    source = b"fn main() -> tryte:\n    mut value: tryte = 1\n    return value\n"
    result = _run_stage1(stage1_executable, source)
    assert _typed_constant_lines(result.stderr) == [
        [1, 0, 2, 1, source.index(b"1"), 2, -1],
    ]
    assert result.returncode != 0


@pytest.mark.s3_native
def test_s12_invalid_unresolved_constant_fails_closed(stage1_executable: Path) -> None:
    result = _run_stage1(
        stage1_executable,
        b"fn main() -> tryte:\n    return nope\n",
    )
    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr == b"S3_STAGE1_ERROR\n"
