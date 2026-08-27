from __future__ import annotations

from tools.audit_stage1_ir_closure_surfaces import (
    SURFACES,
    build_surface_report,
)


def _requirements(relationships: dict[str, bool]) -> dict[str, object]:
    return {
        "status": "BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP",
        "stage1_self_emit": "BLOCKED_UNTIL_MISSING_LANES_EXIST_AND_VERIFY",
        "missing_lossless_typed_lanes": [
            "legacy_lane_a",
            "legacy_lane_b",
            "legacy_lane_c",
            "legacy_lane_d",
            "legacy_lane_e",
            "legacy_lane_f",
            "legacy_lane_g",
        ],
        "storage_evidence": {"semantic_relationships": relationships},
    }


def _all_relationships(value: bool) -> dict[str, bool]:
    return {
        "typed_value_definitions": value,
        "instruction_operand_value_ids": value,
        "instruction_result_value_ids": value,
        "call_argument_value_ids": value,
        "call_result_value_ids": value,
        "complete_terminator_values": value,
        "canonical_serialized_ir": value,
    }


def test_historical_seven_lane_count_does_not_define_surface_count() -> None:
    result = build_surface_report(_requirements(_all_relationships(False)))
    assert result["status"] == "STATIC_FIVE_SURFACE_MODEL_PASS"
    assert result["historical_missing_lane_count"] == 7
    assert result["semantic_surface_count"] == 5
    assert result["missing_surface_count"] == 5
    assert set(result["missing_surfaces"]) == set(SURFACES)
    assert result["native_evidence"] is False
    assert result["canonical_source_mutated"] is False


def test_two_closed_relationship_groups_reduce_missing_surfaces_without_stale_guard_failure() -> None:
    relationships = _all_relationships(False)
    relationships["typed_value_definitions"] = True
    relationships["complete_terminator_values"] = True
    result = build_surface_report(_requirements(relationships))
    assert result["status"] == "STATIC_FIVE_SURFACE_MODEL_PASS"
    assert result["surfaces"]["S1_typed_value_definitions"]["state"] == "CLOSED"
    assert result["surfaces"]["S4_complete_terminators"]["state"] == "CLOSED"
    assert result["missing_surface_count"] == 3


def test_split_relationship_surface_stays_missing_until_every_relationship_is_closed() -> None:
    relationships = _all_relationships(True)
    relationships["instruction_result_value_ids"] = False
    result = build_surface_report(_requirements(relationships))
    assert result["surfaces"]["S2_instruction_def_use"]["state"] == "MISSING"
    assert result["missing_surfaces"] == ["S2_instruction_def_use"]


def test_missing_relationship_evidence_is_fail_closed_as_unknown() -> None:
    relationships = _all_relationships(True)
    del relationships["call_result_value_ids"]
    result = build_surface_report(_requirements(relationships))
    assert result["status"] == "STATIC_FIVE_SURFACE_MODEL_RECONCILE"
    assert result["surfaces"]["S3_call_dataflow"]["state"] == "UNKNOWN"
    assert result["self_emit"] == "NOT_AUTHORIZED_BY_STATIC_AUDIT"
    assert result["stage2"] == "NOT_AUTHORIZED_BY_STATIC_AUDIT"
