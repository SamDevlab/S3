from __future__ import annotations

import json
from pathlib import Path

from tools.audit_stage1_codegen_ir import audit


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "codegen-ir-v2-contract.json"


def test_codegen_ir_v2_contract_records_closed_pool_and_real_baseline() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "s3.selfhost.codegen-ir-v2-contract.v1"
    assert contract["closed_prerequisite"]["status"] == "RESOLVED"
    assert contract["closed_prerequisite"]["required"] == 736
    assert contract["closed_prerequisite"]["capacity"] == 746
    assert contract["closed_prerequisite"]["banks"] == [365, 365, 16]
    observed = contract["observed_self_source"]
    assert observed["instructions_or_events"] == 1460
    assert observed["values"] == 1213
    assert observed["calls"] == 656
    assert observed["call_arguments"] == 736
    assert observed["discards"] == 699


def test_codegen_ir_v2_contract_requires_real_def_use_and_terminators() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    instruction = set(contract["required_lanes"]["instruction"])
    terminator = set(contract["required_lanes"]["terminator"])
    parameter = set(contract["required_lanes"]["parameter"])
    local = set(contract["required_lanes"]["local"])

    assert {"operand_a_value_id", "operand_b_value_id", "result_value_id"} <= instruction
    assert {"condition_value_id_or_none", "return_value_id_or_none"} <= terminator
    assert {"name_identity", "type_id", "value_id", "abi_index"} <= parameter
    assert {"name_identity", "type_id", "mutability", "value_id", "frame_slot"} <= local


def test_static_audit_fails_closed_on_current_pre_v2_source() -> None:
    result = audit(SOURCE, CONTRACT)
    assert result["static_status"] == "BLOCKED_MISSING_CODEGEN_IR_V2_LANES"
    assert result["native_linux_qualification_required"] is True
    assert result["self_emit_claimed"] is False
    assert result["stage2_claimed"] is False

    missing = set(result["missing_required_lane_markers"])
    assert "parameter_value_id" in missing
    assert "instruction_result" in missing
    assert "call_result" in missing
    assert "terminator_condition" in missing


def test_static_audit_detects_zero_event_headroom_at_native_baseline() -> None:
    result = audit(SOURCE, CONTRACT)
    capacity = result["capacity_observation"]
    assert capacity["native_baseline_events"] == 1460
    assert capacity["native_baseline_discard_events"] == 699
    assert capacity["static_event_slots"] == 1460
    assert capacity["static_event_headroom_against_native_baseline"] == 0
    assert capacity["preflight_required"] is True


def test_compaction_projection_is_explicitly_not_a_native_pass() -> None:
    result = audit(SOURCE, CONTRACT)
    projection = result["capacity_observation"]["compaction_projection"]
    assert projection["strategy"] == "DO_NOT_SERIALIZE_AGGREGATE_DISCARD_KEYWORD_EVENT"
    assert projection["projected_events"] == 761
    assert projection["projected_headroom"] == 699
    assert projection["status"] == "PROJECTION_ONLY_NATIVE_REMEASUREMENT_REQUIRED"
    assert "Calls/stores remain explicit instructions" in projection["side_effect_rule"]
