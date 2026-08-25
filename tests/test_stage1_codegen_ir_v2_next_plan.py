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
    assert plan["local_ir_v2_design_possible"] is False
    assert plan["local_ir_v2_start_allowed"] is False
    assert plan["unified_value_namespace_start_allowed"] is False


def test_good_native_parameter_report_reserves_logical_symbol_ranges_but_requires_migration() -> None:
    plan = build_plan(_parameter_report())
    assert plan["status"] == "READY_FOR_LOCAL_IR_V2_DESIGN"
    assert plan["local_ir_v2_design_possible"] is True
    assert plan["local_ir_v2_start_allowed"] is True
    assert plan["block_capacity_expansion_required_before_local_metadata"] is False
    assert plan["unified_value_namespace_start_allowed"] is False

    ranges = plan["value_id_reservations"]
    assert ranges["status"] == "LOGICAL_RESERVATION_PENDING_NAMESPACE_REBUILD"
    assert ranges["parameter_domain"] == {"start": 0, "end_exclusive": 64}
    assert ranges["parameters_used"] == {"start": 0, "end_exclusive": 64}
    assert ranges["unused_parameter_domain"] == {"start": 64, "end_exclusive": 64}
    assert ranges["local_storage"] == {"start": 64, "end_exclusive": 87}
    assert ranges["first_instruction_constant_or_result_id"] == 87
    assert ranges["parameter_and_local_ranges_nonoverlapping"] is True
    assert ranges["local_ids_assignable_single_pass"] is True
    assert ranges["collision_free_with_legacy_value_stream"] is False

    transition = plan["namespace_transition"]
    assert transition["legacy_structural_value_stream"]["end_exclusive"] == 1300
    assert transition["planned_symbol_value_domain"]["end_exclusive"] == 87
    assert transition["overlap_count"] == 87
    assert transition["migration_required"] is True
    assert transition["conservative_no_compaction_required_slots"] == 1387
    assert transition["conservative_no_compaction_fits_value_capacity"] is True

    assert plan["headroom"]["events"] == 560
    assert plan["headroom"]["legacy_values"] == 160
    assert plan["headroom"]["conservative_values_after_symbol_reservation"] == 73
    assert plan["headroom"]["blocks_physical"] == 45
    assert plan["headroom"]["blocks_strict_pass"] == 44
    assert plan["headroom"]["legacy_additional_structural_control_budget"] == 14
    assert plan["headroom"]["local_records"] == 41


def test_near_full_legacy_block_pool_routes_to_730_block_candidate() -> None:
    plan = build_plan(_parameter_report(ir_block_count=362))
    assert plan["local_ir_v2_design_possible"] is True
    assert plan["headroom"]["blocks_strict_pass"] == 2
    assert plan["headroom"]["legacy_additional_structural_control_budget"] == 0
    assert plan["local_ir_v2_start_allowed"] is False
    assert plan["block_capacity_expansion_required_before_local_metadata"] is True
    assert plan["status"] == "READY_FOR_BLOCK_CAPACITY_EXPANSION_BEFORE_LOCAL_IR_V2"
    assert plan["next"] == "PACKED_730_BLOCK_CAPACITY_CANDIDATE"
    assert plan["block_capacity_route"]["candidate_capacity"] == 730


def test_one_additional_control_event_is_enough_to_keep_direct_local_route_open() -> None:
    plan = build_plan(_parameter_report(ir_block_count=361))
    assert plan["headroom"]["blocks_strict_pass"] == 3
    assert plan["headroom"]["legacy_additional_structural_control_budget"] == 1
    assert plan["local_ir_v2_start_allowed"] is True
    assert plan["block_capacity_expansion_required_before_local_metadata"] is False


def test_locals_start_after_fixed_parameter_domain_even_when_few_parameters_are_used() -> None:
    plan = build_plan(_parameter_report(parameter_count=2, local_count=3))
    ranges = plan["value_id_reservations"]
    assert ranges["parameter_domain"] == {"start": 0, "end_exclusive": 64}
    assert ranges["parameters_used"] == {"start": 0, "end_exclusive": 2}
    assert ranges["unused_parameter_domain"] == {"start": 2, "end_exclusive": 64}
    assert ranges["local_storage"] == {"start": 64, "end_exclusive": 67}
    assert ranges["first_instruction_constant_or_result_id"] == 67


def test_conservative_value_overflow_does_not_fake_unified_namespace_readiness() -> None:
    plan = build_plan(_parameter_report(ir_value_count=1400))
    assert plan["local_ir_v2_design_possible"] is True
    assert plan["local_ir_v2_start_allowed"] is True
    assert plan["unified_value_namespace_start_allowed"] is False
    transition = plan["namespace_transition"]
    assert transition["conservative_no_compaction_required_slots"] == 1487
    assert transition["conservative_no_compaction_fits_value_capacity"] is False
    assert transition["value_compaction_required_before_unified_rebuild"] is True


def test_native_capacity_exhaustion_blocks_local_design() -> None:
    plan = build_plan(_parameter_report(ir_block_count=365))
    assert plan["status"] == "BLOCKED_BY_NATIVE_CAPACITY"
    assert plan["guards"]["block_count_currently_below_legacy_limit"] is False
    assert plan["local_ir_v2_design_possible"] is False
    assert plan["local_ir_v2_start_allowed"] is False


def test_too_many_locals_blocks_packed_lane() -> None:
    plan = build_plan(_parameter_report(local_count=65))
    assert plan["guards"]["local_count_fits_packed_lane"] is False
    assert plan["local_ir_v2_design_possible"] is False


def test_too_many_parameters_blocks_fixed_parameter_domain() -> None:
    plan = build_plan(_parameter_report(parameter_count=65))
    assert plan["guards"]["parameter_count_fits_fixed_value_id_domain"] is False
    assert plan["local_ir_v2_design_possible"] is False


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


def test_boolean_native_count_is_rejected_as_non_integer_evidence() -> None:
    report = _parameter_report()
    report["self_source"]["audit"]["ir_value_count"] = True
    with pytest.raises(PlanError, match="missing or invalid native audit field"):
        build_plan(report)
