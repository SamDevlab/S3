from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.audit_stage1_codegen_ir import audit
from tools.patch_stage1_codegen_ir_v2_capacity import (
    BASELINE_SOURCE_SHA256,
    transform,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "codegen-ir-v2-contract.json"


def test_codegen_ir_v2_contract_records_closed_pool_and_real_baseline() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "s3.selfhost.codegen-ir-v2-contract.v2"
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


def test_codegen_ir_v2_contract_requires_current_packed_def_use_shape() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    instruction = set(contract["required_lanes"]["instruction"])
    terminator = set(contract["required_lanes"]["block_terminator"])
    parameter = set(contract["required_lanes"]["parameter"])
    local = set(contract["required_lanes"]["local"])
    call = set(contract["required_lanes"]["call"])

    assert {"operand_a_value_id_or_none", "operand_b_value_id_or_none", "result_value_id_or_none"} <= instruction
    assert "owner_function_id" not in instruction
    assert {"condition_value_id_or_none", "return_value_id_or_none", "owner_function_id"} <= terminator
    assert {"name_identity", "type_id", "value_id", "abi_index"} <= parameter
    assert {
        "name_identity",
        "type_id",
        "mutability",
        "storage_kind",
        "local_ordinal",
        "fixed_extent",
        "value_id",
    } <= local
    assert "result_value_id_or_no_result" not in call
    assert contract["representation_rules"]["instruction_owner"].startswith("Do not duplicate")
    assert contract["representation_rules"]["call_result"].startswith("Do not add")


def test_contract_owns_source_markers_instead_of_auditor_hardcoding() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    markers = contract["required_source_markers"]
    assert markers["parameter_packed_metadata"] == "ir_parameter_records"
    assert markers["local_packed_metadata"] == "ir_local_records"
    assert markers["semantic_value_namespace"] == "ir_semantic_value"
    assert markers["instruction_v2_pack"] == "pack_ir_v2_instruction"
    assert markers["packed_block_v2"] == "pack_ir_v2_block"


def test_static_audit_fails_closed_on_current_pre_v2_source() -> None:
    result = audit(SOURCE, CONTRACT)
    assert result["static_status"] == "BLOCKED_MISSING_CODEGEN_IR_V2_LANES"
    assert result["contract_schema"] == "s3.selfhost.codegen-ir-v2-contract.v2"
    assert result["native_linux_qualification_required"] is True
    assert result["self_emit_claimed"] is False
    assert result["stage2_claimed"] is False

    missing = set(result["missing_required_lane_markers"])
    assert "parameter_packed_metadata" in missing
    assert "local_packed_metadata" in missing
    assert "semantic_value_namespace" in missing
    assert "instruction_v2_pack" in missing
    assert "terminator_condition_linkage" in missing


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


def test_compaction_patch_matches_only_the_qualified_source_shape() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert hashlib.sha256(source.encode("utf-8")).hexdigest() == BASELINE_SOURCE_SHA256

    transformed = transform(source)
    assert transformed != source
    assert "ast_discard_count += 1" in transformed
    assert "ir_ast_event_opcode = 5" not in transformed
    assert "ir_ast_event_operand = value" in source
    assert len(transformed) < len(source)


def test_compaction_patch_rejects_already_transformed_source() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    transformed = transform(source)
    try:
        transform(transformed)
    except ValueError as error:
        assert "expected exactly one Stage1 discard-event block" in str(error)
    else:
        raise AssertionError("compaction patch must fail closed when applied twice")
