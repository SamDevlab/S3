from __future__ import annotations

import pytest

from tools.plan_stage1_codegen_ir_v2_next import PlanError, build_plan


def _parameter_report(**audit_overrides: int) -> dict[str, object]:
    audit = {
        "parameter_count": 64,
        "local_count": 23,
        "ir_instruction_count": 900,
        "ir_value_count": 1300,
        "ir_block_count": 320,
        "ast_call_count": 670,
    }
    audit.update(audit_overrides)
    return {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "canonical_source_mutated": False,
        "self_source": {"audit": audit},
        "qualification": {"parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE"},
    }


def test_missing_native_parameter_report_stays_fail_closed() -> None:
    plan = build_plan(None)
    assert plan["status"] == "WAITING_FOR_NATIVE_PARAMETER_REPORT"
    assert plan["native_evidence"] is False
    assert plan["local_ir_v2_start_allowed"] is False


def test_good_native_parameter_report_reserves_non_colliding_value_ranges() -> None:
    plan = build_plan(_parameter_report())
    assert plan["status"] == "READY_FOR_LOCAL_IR_V2_DESIGN"
    assert plan["local_ir_v2_start_allowed"] is True
    ranges = plan["value_id_reservations"]
    assert ranges["parameters"] == {"start": 0, "end_exclusive": 64}
    assert ranges["local_storage"] == {"start": 64, "end_exclusive": 87}
    assert ranges["first_instruction_constant_or_result_id"] == 87
    assert ranges["collision_free"] is True
    assert plan["headroom"]["events"] == 560
    assert plan["headroom"]["values"] == 160
    assert plan["headroom"]["blocks"] == 45
    assert plan["headroom"]["local_records"] == 41


def test_native_capacity_exhaustion_blocks_local_phase() -> None:
    plan = build_plan(_parameter_report(ir_block_count=365))
    assert plan["status"] == "BLOCKED_BY_NATIVE_CAPACITY"
    assert plan["guards"]["block_headroom_positive"] is False
    assert plan["local_ir_v2_start_allowed"] is False


def test_too_many_locals_blocks_packed_lane() -> None:
    plan = build_plan(_parameter_report(local_count=65))
    assert plan["guards"]["local_count_fits_packed_lane"] is False
    assert plan["local_ir_v2_start_allowed"] is False


def test_non_pass_parameter_report_is_rejected() -> None:
    report = _parameter_report()
    report["qualification"]["parameter_ir_v2_candidate"] = "FAIL"
    with pytest.raises(PlanError, match="not a native PASS"):
        build_plan(report)


def test_mutated_canonical_report_is_rejected() -> None:
    report = _parameter_report()
    report["canonical_source_mutated"] = True
    with pytest.raises(PlanError, match="non-mutating"):
        build_plan(report)
