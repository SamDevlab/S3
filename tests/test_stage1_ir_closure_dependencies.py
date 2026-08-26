from __future__ import annotations

from tools.audit_stage1_ir_closure_dependencies import (
    EXPECTED_MISSING_LANES,
    build_matrix,
)


def _requirements() -> dict[str, object]:
    return {
        "status": "BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP",
        "missing_lossless_typed_lanes": sorted(EXPECTED_MISSING_LANES),
        "storage_evidence": {
            "semantic_relationships": {
                "typed_value_definitions": False,
                "instruction_operand_value_ids": False,
                "instruction_result_value_ids": False,
                "call_argument_value_ids": False,
                "call_result_value_ids": False,
                "complete_terminator_values": False,
                "canonical_serialized_ir": False,
            }
        },
    }


def test_parallel_matrix_preserves_all_seven_missing_lanes() -> None:
    result = build_matrix(_requirements())
    covered = {
        lane
        for stream in result["workstreams"].values()
        for lane in stream["covers"]
    }

    assert result["status"] == "STATIC_PARALLEL_WORKSTREAM_MATRIX_PASS"
    assert result["missing_lane_count"] == 7
    assert covered == EXPECTED_MISSING_LANES


def test_parallel_matrix_exposes_five_non_promoting_workstreams() -> None:
    result = build_matrix(_requirements())

    assert len(result["workstreams"]) == 5
    assert all(
        stream["can_prepare_in_parallel"] is True
        for stream in result["workstreams"].values()
    )
    assert all(
        stream["can_promote_without_native_candidate"] is False
        for stream in result["workstreams"].values()
    )


def test_terminator_workstream_waits_for_current_compact_block_native_result() -> None:
    result = build_matrix(_requirements())
    terminator = result["workstreams"]["W4_terminator_dataflow"]

    assert "CURRENT_COMPACT_BLOCK_CAPACITY_NATIVE_RESULT" in terminator["depends_on"]
    assert "branch_conditions_and_complete_terminators" in terminator["currently_missing"]


def test_stage2_serialization_is_last_dependency_layer() -> None:
    result = build_matrix(_requirements())
    stage2 = result["workstreams"]["W5_canonical_stage2_serialization"]

    assert set(stage2["depends_on"]) == {
        "W1_symbol_and_value_identity",
        "W2_instruction_def_use_and_order",
        "W3_call_dataflow_and_abi",
        "W4_terminator_dataflow",
    }
    assert result["stage2"] == "NOT_CREATED"
    assert result["full_self_hosting"] is False
