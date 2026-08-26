from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.qualify_stage2_stage3_fixed_point import (
    FixedPointError,
    _execve_lines,
    _sanitized_compiler_env,
    validate_stage1_certification,
)


def _certificate(sha: str) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-certification-gate.v1",
        "canonical_source": {"sha256": sha, "bytes": 1, "commit": "deadbeef"},
        "qualification": {
            "stage1_certified_for_stage2": True,
            "self_emit": "PASS",
            "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
            "verifier_v2": "PASS",
            "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
        },
    }


def test_stage1_gate_requires_every_strict_prerequisite() -> None:
    sha = "a" * 64
    validate_stage1_certification(_certificate(sha), sha)

    broken = _certificate(sha)
    broken["qualification"]["verifier_v2"] = "FAIL"
    with pytest.raises(FixedPointError, match="verifier_v2"):
        validate_stage1_certification(broken, sha)


def test_stage1_gate_is_invalidated_by_canonical_source_change() -> None:
    with pytest.raises(FixedPointError, match="canonical SHA"):
        validate_stage1_certification(_certificate("a" * 64), "b" * 64)


def test_compiler_environment_hides_python_and_normalizes_determinism(tmp_path: Path) -> None:
    env = _sanitized_compiler_env(tmp_path)
    assert env["PATH"] == "/nonexistent"
    assert env["PYTHONPATH"] == ""
    assert env["PYTHONHOME"] == ""
    assert env["SOURCE_DATE_EPOCH"] == "0"
    assert env["LANG"] == "C"
    assert env["LC_ALL"] == "C"


def test_execve_trace_parser_exposes_descendant_execs(tmp_path: Path) -> None:
    trace = tmp_path / "trace.txt"
    trace.write_text(
        '123 execve("/tmp/s3c-stage2", ["/tmp/s3c-stage2"], 0x0) = 0\n'
        '124 execve("/usr/bin/python3", ["python3"], 0x0) = 0\n',
        encoding="utf-8",
    )
    lines = _execve_lines(trace)
    assert len(lines) == 2
    assert "python3" in lines[1]


def test_fixed_point_contract_keeps_elf_equality_mandatory_not_assembly_text() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads(
        (root / "reports" / "selfhost" / "stage2" / "stage2-stage3-fixed-point-contract.json").read_text(encoding="utf-8")
    )
    determinism = contract["determinism"]
    assert determinism["stage2_stage3_elf_bytes_equal"] is True
    assert determinism["stage2_stage3_elf_sha_equal"] is True
    assert "DIAGNOSTIC" in determinism["stage2_stage3_assembly_bytes_equal"]
