from __future__ import annotations

import json
from pathlib import Path

import tools.qualify_stage1_codegen_ir_v2_chain as chain


def _static(pass_gate: bool) -> dict[str, object]:
    return {
        "native_chain_allowed": pass_gate,
        "storage_reuse_audit": {
            "status": "STATIC_STORAGE_AUDIT_PASS" if pass_gate else "STATIC_STORAGE_AUDIT_FAIL",
            "event_overwrite_frontier": (
                "AFTER_LEGACY_EVENT_VERIFIER_BEFORE_REMAINING_VERIFIER_AND_PIPELINE_DECISION"
                if pass_gate
                else "NOT_PROVEN"
            ),
        },
        "parameter_candidate_storage_reuse_audit": {
            "status": "STATIC_STORAGE_AUDIT_PASS" if pass_gate else "STATIC_STORAGE_AUDIT_FAIL",
            "event_overwrite_frontier": (
                "AFTER_LEGACY_EVENT_VERIFIER_BEFORE_REMAINING_VERIFIER_AND_PIPELINE_DECISION"
                if pass_gate
                else "NOT_PROVEN"
            ),
        },
        "block_capacity_audit": {
            "status": (
                "STATIC_BLOCK_CAPACITY_DESIGN_PASS"
                if pass_gate
                else "STATIC_BLOCK_CAPACITY_DESIGN_FAIL"
            ),
            "projected_parameter_blocks": 362 if pass_gate else None,
            "strict_additional_control_budget": 0 if pass_gate else None,
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


def _parameter(pass_gate: bool, *, blocks: int = 320, full_provenance: bool = False) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "canonical_source_mutated": False,
        "self_source": {
            "audit": {
                "parameter_count": 64,
                "local_count": 23,
                "ir_instruction_count": 900,
                "ir_value_count": 1300,
                "ir_block_count": blocks,
                "ast_call_count": 670,
            }
        },
        "qualification": {
            "parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE" if pass_gate else "FAIL"
        },
    }
    if full_provenance:
        result["candidate"] = {
            "source_sha256": "a" * 64,
            "source_bytes": 123,
        }
    return result


def _run(
    tmp_path: Path,
    *,
    static_preflight_report: str = "static.json",
) -> dict[str, object]:
    return chain.run_chain(
        capacity_report_path=tmp_path / "capacity.json",
        parameter_report_path=tmp_path / "parameter.json",
        next_phase_report_path=tmp_path / "next.json",
        local_preflight_report_path=tmp_path / "locals.json",
        chain_report_path=tmp_path / "chain.json",
        static_preflight_report_path=tmp_path / static_preflight_report,
        run_tooling_tests=False,
    )


def test_chain_stops_before_static_preflight_when_tooling_tests_fail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        chain,
        "_run_tooling_tests",
        lambda: {"status": "FAIL", "returncode": 1, "files": []},
    )

    def unexpected_static(**_):
        raise AssertionError("static preflight must not run after tooling-test failure")

    monkeypatch.setattr(chain, "run_static_preflight", unexpected_static)
    result = chain.run_chain(
        capacity_report_path=tmp_path / "capacity.json",
        parameter_report_path=tmp_path / "parameter.json",
        next_phase_report_path=tmp_path / "next.json",
        local_preflight_report_path=tmp_path / "locals.json",
        chain_report_path=tmp_path / "chain.json",
        static_preflight_report_path=tmp_path / "static.json",
        run_tooling_tests=True,
    )
    assert result["chain_status"] == "BLOCKED_AT_TOOLING_TESTS"
    assert result["tooling_tests"]["status"] == "FAIL"
    assert result["static_preflight"]["status"] == "NOT_RUN"
    assert result["capacity_gate"]["status"] == "NOT_RUN"
    assert result["local_candidate_preflight"]["status"] == "NOT_RUN_PARAMETER_GATE_NOT_PASS"
    assert result["canonical_source_mutated"] is False


def test_chain_stops_before_native_when_static_preflight_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(False))

    def unexpected_capacity(**_):
        raise AssertionError("native capacity qualifier must not run after static preflight failure")

    monkeypatch.setattr(chain, "qualify_capacity", unexpected_capacity)
    result = _run(tmp_path)
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
    result = _run(tmp_path)
    assert result["chain_status"] == "BLOCKED_AT_CAPACITY_CANDIDATE"
    assert result["parameter_gate"]["status"] == "NOT_RUN"
    assert result["next_phase_budget"]["status"] == "WAITING_FOR_NATIVE_PARAMETER_REPORT"
    assert result["canonical_source_mutated"] is False


def test_chain_parameter_pass_requires_concrete_local_control_preflight_when_blocks_allow_design(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(True))
    monkeypatch.setattr(chain, "qualify_capacity", lambda **_: _capacity(True))
    monkeypatch.setattr(chain, "qualify_parameters", lambda **_: _parameter(True, blocks=320))
    result = _run(tmp_path)
    assert result["chain_status"] == "PASS_THROUGH_PARAMETER_CANDIDATE"
    assert result["static_preflight"]["status"] == "PASS"
    assert result["static_preflight"]["block_capacity_design"] == "STATIC_BLOCK_CAPACITY_DESIGN_PASS"
    assert result["next_phase_budget"]["status"] == "READY_FOR_LOCAL_IR_V2_CANDIDATE_PREFLIGHT"
    assert result["next_phase_budget"]["local_ir_v2_design_possible"] is True
    assert result["next_phase_budget"]["local_ir_v2_start_allowed"] is False
    assert result["next_phase_budget"]["local_candidate_control_preflight_required"] is True
    assert result["next_phase_budget"]["block_capacity_expansion_required"] is False
    assert result["next_phase_budget"]["next"] == "PREPARE_LOCAL_METADATA_CANDIDATE_AND_PROJECT_EXACT_CONTROL_DELTA"
    assert result["local_candidate_preflight"]["status"] == "NOT_RUN_TEST_HARNESS_INCOMPLETE_PARAMETER_REPORT"
    assert result["local_candidate_preflight"]["native_qualification_allowed"] is False
    next_report = json.loads((tmp_path / "next.json").read_text(encoding="utf-8"))
    assert next_report["value_id_reservations"]["parameter_domain"]["end_exclusive"] == 64
    assert next_report["value_id_reservations"]["local_storage"]["start"] == 64
    assert next_report["value_id_reservations"]["local_storage"]["end_exclusive"] == 87
    assert result["canonical_commit_allowed"] is False
    assert result["stage2"] == "NOT_STARTED"
    assert result["stage3"] == "NOT_STARTED"


def test_chain_full_parameter_provenance_runs_and_propagates_local_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(True))
    monkeypatch.setattr(chain, "qualify_capacity", lambda **_: _capacity(True))
    monkeypatch.setattr(
        chain,
        "qualify_parameters",
        lambda **_: _parameter(True, blocks=320, full_provenance=True),
    )
    observed: dict[str, object] = {}

    def fake_local(parameter, *, canonical_source):
        observed["parameter"] = parameter
        observed["canonical_source_nonempty"] = bool(canonical_source)
        return {
            "schema": "s3.selfhost.codegen-ir-v2-locals-static-preflight.v1",
            "status": "PASS_STATIC_LOCAL_CANDIDATE_NATIVE_QUALIFICATION_REQUIRED",
            "native_evidence": False,
            "native_parameter_evidence_consumed": True,
            "canonical_source_mutated": False,
            "local_candidate": {
                "required_records_including_candidate_self_source": 120,
                "selected_capacity": 120,
            },
            "native_headroom_projection": {
                "projected_candidate_counts": {
                    "events": 1100,
                    "values": 1400,
                    "blocks": 350,
                    "calls": 700,
                }
            },
            "local_native_qualification_allowed": True,
            "canonical_commit_allowed": False,
            "next": "NATIVE_LOCAL_METADATA_CANDIDATE",
        }

    monkeypatch.setattr(chain, "build_local_preflight", fake_local)
    result = _run(tmp_path)
    assert result["chain_status"] == "PASS_THROUGH_PARAMETER_CANDIDATE"
    assert observed["canonical_source_nonempty"] is True
    local = result["local_candidate_preflight"]
    assert local["status"] == "PASS_STATIC_LOCAL_CANDIDATE_NATIVE_QUALIFICATION_REQUIRED"
    assert local["native_parameter_evidence_consumed"] is True
    assert local["required_records"] == 120
    assert local["selected_capacity"] == 120
    assert local["projected_events"] == 1100
    assert local["projected_values"] == 1400
    assert local["projected_blocks"] == 350
    assert local["projected_calls"] == 700
    assert local["native_qualification_allowed"] is True
    assert local["next"] == "NATIVE_LOCAL_METADATA_CANDIDATE"
    assert local["canonical_commit_allowed"] is False
    assert json.loads((tmp_path / "locals.json").read_text(encoding="utf-8"))["status"] == (
        "PASS_STATIC_LOCAL_CANDIDATE_NATIVE_QUALIFICATION_REQUIRED"
    )


def test_chain_parameter_pass_routes_to_730_blocks_when_native_headroom_is_too_small(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(True))
    monkeypatch.setattr(chain, "qualify_capacity", lambda **_: _capacity(True))
    monkeypatch.setattr(chain, "qualify_parameters", lambda **_: _parameter(True, blocks=362))
    result = _run(tmp_path)
    assert result["chain_status"] == "PASS_THROUGH_PARAMETER_CANDIDATE"
    assert result["next_phase_budget"]["local_ir_v2_design_possible"] is True
    assert result["next_phase_budget"]["local_ir_v2_start_allowed"] is False
    assert result["next_phase_budget"]["local_candidate_control_preflight_required"] is False
    assert result["next_phase_budget"]["block_capacity_expansion_required"] is True
    assert result["next_phase_budget"]["next"] == "PACKED_730_BLOCK_CAPACITY_CANDIDATE"


def test_chain_parameter_failure_keeps_local_phase_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chain, "run_static_preflight", lambda **_: _static(True))
    monkeypatch.setattr(chain, "qualify_capacity", lambda **_: _capacity(True))
    monkeypatch.setattr(chain, "qualify_parameters", lambda **_: _parameter(False))
    result = _run(tmp_path)
    assert result["chain_status"] == "BLOCKED_AT_PARAMETER_CANDIDATE"
    assert result["next_phase_budget"]["local_ir_v2_start_allowed"] is False
    assert result["local_candidate_preflight"]["status"] == "NOT_RUN_PARAMETER_GATE_NOT_PASS"
    assert result["canonical_source_mutated"] is False
