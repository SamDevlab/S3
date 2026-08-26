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


def _fixed_point_contract() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (
            root
            / "reports"
            / "selfhost"
            / "stage2"
            / "stage2-stage3-fixed-point-contract.json"
        ).read_text(encoding="utf-8")
    )


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
    contract = _fixed_point_contract()
    assert contract["schema"] == "s3.selfhost.stage2-stage3-fixed-point-contract.v2"
    determinism = contract["determinism"]
    assert determinism["stage2_stage3_elf_bytes_equal"] is True
    assert determinism["stage2_stage3_elf_sha_equal"] is True
    assert "DIAGNOSTIC" in determinism["stage2_stage3_assembly_bytes_equal"]


def test_intermediate_harness_can_never_authorize_full_self_hosting() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "tools" / "qualify_stage2_stage3_fixed_point.py").read_text(encoding="utf-8")
    assert '"authority": "INTERMEDIATE_ONLY_STRICT_SANDBOX_WRAPPER_REQUIRED_FOR_FULL_SELF_HOSTING"' in source
    assert '"full_self_hosting": False' in source
    assert '"next": "RUN_STRICT_PROCESS_AND_FILESYSTEM_SANDBOX_WRAPPER"' in source
    contract = _fixed_point_contract()
    assert contract["authority_rule"]["intermediate_fixed_point_harness_may_authorize_full_self_hosting"] is False
    assert contract["authority_rule"]["strict_sandbox_v3_is_required_for_full_self_hosting"] is True


def test_final_contract_requires_strict_process_file_and_embedded_python_trace() -> None:
    contract = _fixed_point_contract()
    assert contract["final_gate"]["stage2_pythonless_compiler"] == "PASS_STRICT_PROCESS_AND_FILE_TRACE"
    runtime = contract["pythonless_compiler_runtime"]
    assert runtime["required_strict_sandbox_schema"] == "s3.selfhost.stage2-stage3-strict-sandbox.v3"
    assert runtime["embedded_python_runtime_allowed"] is False
    assert runtime["trace_syscalls"] == ["execve", "open", "openat", "openat2"]
    proof = runtime["strict_runtime_proof"]
    assert "bootstrap" in proof
    assert "libpython" in proof
    assert "Relative file opens fail closed" in proof
