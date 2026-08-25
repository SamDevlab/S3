from __future__ import annotations

import json
from pathlib import Path

import tools.qualify_stage1_codegen_ir_v2_chain as chain


def _static(pass_gate: bool) -> dict[str, object]:
    return {
        "native_chain_allowed": pass_gate,
        "storage_reuse_audit": {
            "status": "STATIC_STORAGE_AUDIT_PASS" if pass_gate else "STATIC_STORAGE_AUDIT_FAIL"
        },
        "array_initializer_audit": {
            "status": "STATIC_ARRAY_INITIALIZER_AUDIT_PASS" if pass_gate else "STATIC_ARRAY_INITIALIZER_AUDIT_FAIL",
            "zero_initializer_items": 100 if pass_gate else None,
        },
    }


def _capacity(pass_gate: bool) -> dict[str, object]:
    return {
        "qualification": {
            "capacity_candidate": "PASS_NATIVE_CANDIDATE" if pass_gate else "FAIL",
            "canonical_commit_allowed": pass_gate,
        }
    }


def _parameter(pass_gate: bool) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "canonical_source_mutated": False,
        "self_source": {
            "audit": {
                "parameter_count": 64,
                "local_count": 23,
                "ir_instruction_count": 900,
                "ir_value_count": 1300,
                "ir_block_count": 320,
                "ast_call_count": 670,
            }
        },
        "qualification": {
            "parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE" if pass_gate else "FAIL"
        },
    }


def test_chain_stops_before_native_when_static_preflight_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(False))

    def unexpected_capacity(**_):
        raise AssertionError("native capacity qualifier must not run after static preflight failure")

    monkeypatch.setattr(chain, "qualify_capacity", unexpected_capacity)
    result = chain.run_chain(
        capacity_report_path=tmp_path / "capacity.json",
        parameter_report_path=tmp_path / "parameter.json",
        next_phase_report_path=tmp_path / "next.json",
        chain_report_path=tmp_path / "chain.json",
        static_preflight_report_path=tmp_path / "static.json",
    )
    assert result["chain_status"] == "BLOCKED_AT_STATIC_PREFLIGHT"
    assert result["capacity_gate"]["status"] == "NOT_RUN"
    assert result["parameter_gate"]["status"] == "NOT_RUN"
    assert result["canonical_source_mutated"] is False


def test_chain_stops_before_parameter_when_capacity_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(True))
    monkeypatch.setattr(chain, "qualify_capacity", lambda **_: _capacity(False))

    def unexpected_parameter(**_):
        raise AssertionError("parameter qualifier must not run after capacity failure")

    monkeypatch.setattr(chain, "qualify_parameters", unexpected_parameter)
    result = chain.run_chain(
        capacity_report_path=tmp_path / "capacity.json",
        parameter_report_path=tmp_path / "parameter.json",
        next_phase_report_path=tmp_path / "next.json",
        chain_report_path=tmp_path / "chain.json",
        static_preflight_report_path=tmp_path / "static.json",
    )
    assert result["chain_status"] == "BLOCKED_AT_CAPACITY_CANDIDATE"
    assert result["parameter_gate"]["status"] == "NOT_RUN"
    assert result["next_phase_budget"]["status"] == "WAITING_FOR_NATIVE_PARAMETER_REPORT"
    assert result["canonical_source_mutated"] is False


def test_chain_parameter_pass_produces_local_budget(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(True))
    monkeypatch.setattr(chain, "qualify_capacity", lambda **_: _capacity(True))
    monkeypatch.setattr(chain, "qualify_parameters", lambda **_: _parameter(True))
    result = chain.run_chain(
        capacity_report_path=tmp_path / "capacity.json",
        parameter_report_path=tmp_path / "parameter.json",
        next_phase_report_path=tmp_path / "next.json",
        chain_report_path=tmp_path / "chain.json",
        static_preflight_report_path=tmp_path / "static.json",
    )
    assert result["chain_status"] == "PASS_THROUGH_PARAMETER_CANDIDATE"
    assert result["static_preflight"]["status"] == "PASS"
    assert result["next_phase_budget"]["status"] == "READY_FOR_LOCAL_IR_V2_DESIGN"
    assert result["next_phase_budget"]["local_ir_v2_start_allowed"] is True
    next_report = json.loads((tmp_path / "next.json").read_text(encoding="utf-8"))
    assert next_report["value_id_reservations"]["parameters"]["end_exclusive"] == 64
    assert next_report["value_id_reservations"]["local_storage"]["start"] == 64
    assert next_report["value_id_reservations"]["local_storage"]["end_exclusive"] == 87
    assert result["canonical_commit_allowed"] is False
    assert result["stage2"] == "NOT_STARTED"
    assert result["stage3"] == "NOT_STARTED"


def test_chain_parameter_failure_keeps_local_phase_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(True))
    monkeypatch.setattr(chain, "qualify_capacity", lambda **_: _capacity(True))
    monkeypatch.setattr(chain, "qualify_parameters", lambda **_: _parameter(False))
    result = chain.run_chain(
        capacity_report_path=tmp_path / "capacity.json",
        parameter_report_path=tmp_path / "parameter.json",
        next_phase_report_path=tmp_path / "next.json",
        chain_report_path=tmp_path / "chain.json",
        static_preflight_report_path=tmp_path / "static.json",
    )
    assert result["chain_status"] == "BLOCKED_AT_PARAMETER_CANDIDATE"
    assert result["next_phase_budget"]["local_ir_v2_start_allowed"] is False
    assert result["canonical_source_mutated"] is False
