from __future__ import annotations

import pytest

import tools.preflight_stage1_final_certification as preflight


pytestmark = pytest.mark.s3_fast


def _pass_run(command: list[str]):
    return {
        "command": command,
        "returncode": 0,
        "stdout": "ok",
        "stderr": "",
        "status": "PASS",
    }


def test_tooling_failure_blocks_before_native_evidence_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preflight,
        "_validate_contracts",
        lambda: {"status": "FAIL", "contracts": {}},
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str]):
        calls.append(command)
        return {
            "command": command,
            "returncode": 1,
            "stdout": "",
            "stderr": "syntax error",
            "status": "FAIL",
        }

    monkeypatch.setattr(preflight, "_run", fake_run)
    monkeypatch.setattr(
        preflight,
        "_evidence_readiness",
        lambda: {"all_present": False, "missing_roles": ["final_capacity"], "evidence": {}},
    )
    result = preflight.run_preflight(run_tests=True)
    assert result["status"] == "BLOCKED_FINAL_CERTIFICATION_TOOLING"
    assert result["qualification"]["tooling_preflight"] == "FAIL"
    assert result["qualification"]["stage1_certified_for_stage2"] is False
    assert result["starts_stage2"] is False
    assert result["runs_t4"] is False
    # Only py_compile may be attempted; pytest is not run after an earlier gate fails.
    assert len(calls) == 1
    assert "py_compile" in calls[0]


def test_green_tooling_with_missing_evidence_routes_to_evidence_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preflight,
        "_validate_contracts",
        lambda: {"status": "PASS", "contracts": {}},
    )
    monkeypatch.setattr(preflight, "_run", _pass_run)
    monkeypatch.setattr(
        preflight,
        "_evidence_readiness",
        lambda: {
            "all_present": False,
            "missing_roles": ["final_capacity", "final_self_emit"],
            "evidence": {},
        },
    )
    result = preflight.run_preflight(run_tests=True)
    assert result["status"] == "PASS_TOOLING_FINAL_EVIDENCE_PENDING"
    assert result["qualification"]["tooling_preflight"] == "PASS"
    assert result["final_evidence_readiness"]["missing_roles"] == [
        "final_capacity",
        "final_self_emit",
    ]
    assert result["qualification"]["stage1_certified_for_stage2"] is False
    assert result["qualification"]["full_self_hosting"] is False


def test_all_evidence_present_routes_only_to_gate_emission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preflight,
        "_validate_contracts",
        lambda: {"status": "PASS", "contracts": {}},
    )
    monkeypatch.setattr(preflight, "_run", _pass_run)
    monkeypatch.setattr(
        preflight,
        "_evidence_readiness",
        lambda: {"all_present": True, "missing_roles": [], "evidence": {}},
    )
    result = preflight.run_preflight(run_tests=True)
    assert result["status"] == "PASS_TOOLING_ALL_FINAL_EVIDENCE_PRESENT"
    assert result["qualification"]["next"] == "EMIT_STAGE1_CERTIFICATION_GATE_V2"
    assert result["qualification"]["stage1_certified_for_stage2"] is False


def test_skip_tests_never_turns_preflight_into_native_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preflight,
        "_validate_contracts",
        lambda: {"status": "PASS", "contracts": {}},
    )
    monkeypatch.setattr(preflight, "_run", _pass_run)
    monkeypatch.setattr(
        preflight,
        "_evidence_readiness",
        lambda: {"all_present": False, "missing_roles": ["native_source_coverage"], "evidence": {}},
    )
    result = preflight.run_preflight(run_tests=False)
    assert result["qualification"]["tooling_preflight"] == "PASS"
    assert result["focused_hosted_tests"]["status"] == "SKIPPED"
    assert result["native_execution_evidence"] is False


def test_preflight_final_semantic_ir_path_is_call_bound() -> None:
    final_semantic = preflight.FINAL_EVIDENCE["final_semantic_ir_verifier"]
    assert final_semantic.endswith("stage1-final-semantic-ir-verifier-call-bound.json")
    assert final_semantic != "reports/selfhost/stage1/stage1-final-semantic-ir-verifier.json"
    assert "native_call_reconciliation" in preflight.FINAL_EVIDENCE


def test_preflight_compiles_and_tests_call_boundary_tooling() -> None:
    assert "tools/bind_stage1_semantic_ir_native_calls.py" in preflight.TOOL_FILES
    assert "tools/qualify_stage1_final_self_emit_static.py" in preflight.TOOL_FILES
    assert "tests/test_stage1_semantic_ir_native_call_boundary.py" in preflight.TEST_FILES
    assert "tests/test_stage1_final_self_emit_call_bound.py" in preflight.TEST_FILES
