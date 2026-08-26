from __future__ import annotations

import pytest

from tools.audit_stage1_final_capacity_measurement_readiness import assess


pytestmark = pytest.mark.s3_fast


def _chain(*, native_pass: bool = True, plan_pass: bool = True) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.pre-ir-v2-token-lane-chain.v2",
        "native_token_lane": {
            "qualification": {
                "token_lane_candidate": (
                    "PASS_NATIVE_CANDIDATE" if native_pass else "FAIL"
                )
            }
        },
        "full_source_capacity_plan": {
            "schema": "s3.selfhost.full-source-capacity-plan.v2",
            "status": (
                "STATIC_PLAN_NATIVE_REMEASUREMENT_REQUIRED"
                if plan_pass
                else "FAIL"
            ),
            "requirements": {
                "calls": 700,
                "call_arguments": 900,
                "events_after_discard_compaction": 1500,
                "blocks_after_discard_compaction": 400,
            },
            "minimum_physical_plan": {
                "call_capacity_bank_multiple": 730,
                "call_argument_capacity": 900,
                "event_capacity_bank_multiple": 1825,
                "block_capacity_bank_multiple": 730,
            },
        },
    }


def test_green_pre_ir_chain_is_still_not_final_capacity_evidence() -> None:
    result = assess(_chain())
    assert result["status"] == "PASS_PRE_IR_BRIDGE_FINAL_CAPACITY_MEASUREMENT_STILL_BLOCKED"
    assert result["native_pre_ir_token_lane_pass"] is True
    assert result["static_full_source_plan_valid"] is True
    assert result["provisional_full_source_capacity_facts"]["calls"]["required_static_full_source"] == 700
    assert result["can_emit_stage1_capacity_measurement_v1"] is False
    assert result["can_emit_stage1_final_capacity_v1"] is False
    assert result["stage2_allowed"] is False
    assert result["full_self_hosting"] is False
    for lane in ("instructions", "semantic_values", "parameters", "locals", "storage_objects"):
        assert result["lane_readiness"][lane]["status"] == "WAITING_FOR_FINAL_IR_V2_NATIVE_MEASUREMENT"


def test_native_token_lane_failure_blocks_bridge() -> None:
    result = assess(_chain(native_pass=False))
    assert result["status"] == "BLOCKED_PRE_IR_NATIVE_TOKEN_LANE"
    assert result["next"] == "RUN_OR_REPAIR_PRE_IR_V2_TOKEN_LANE_CHAIN"
    assert result["can_emit_stage1_capacity_measurement_v1"] is False


def test_static_plan_failure_blocks_bridge_even_after_native_token_pass() -> None:
    result = assess(_chain(plan_pass=False))
    assert result["status"] == "BLOCKED_PRE_IR_FULL_SOURCE_CAPACITY_PLAN"
    assert result["next"] == "REPAIR_FULL_SOURCE_CAPACITY_PLAN"
    assert result["can_emit_stage1_final_capacity_v1"] is False
