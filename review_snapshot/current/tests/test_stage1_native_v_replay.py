"""Focused contract tests for the bounded native V replay observer."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

from tools.build_stage1_v_replay import build_stage1


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "selfhost" / "compiler" / "stage1_v_replay.s3"
CANONICAL_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
LINUX_NATIVE = platform.system() == "Linux" and platform.machine().lower() in {
    "x86_64",
    "amd64",
}


def _run(executable: Path, source: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )


def test_replay_source_is_streaming_and_bounded() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "while position < length" in source
    assert "value_id: i64[" not in source
    assert "value_records" not in source
    assert "__Z" not in source
    assert "S3_STAGE1_V_REPLAY" in source


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v_replay_matches_hosted_literal_value_contract(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v-replay")
    source = b"fn probe() -> tryte:\n    return 7\n"
    first = _run(executable, source)
    second = _run(executable, source)
    expected = f"V 0 0 3 2 {source.index(b'7')} 1 0 -1\n".encode("ascii")
    assert first.returncode == 0
    assert first.stdout == b""
    assert first.stderr == expected
    assert second.returncode == 0
    assert second.stderr == expected


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v_replay_fails_closed_for_canonical_source(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v-replay")
    result = _run(executable, CANONICAL_SOURCE.read_bytes())
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == b"S3_STAGE1_V_REPLAY_BLOCKED\n"
