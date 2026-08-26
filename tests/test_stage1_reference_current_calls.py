from __future__ import annotations

import pytest

from tools.audit_stage1_reference_current_calls import (
    CurrentCallInventoryError,
    audit_source,
    validate_inventory_for_source,
)


pytestmark = pytest.mark.s3_fast


def _contract() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.reference-current-call-inventory-contract.v1",
        "output_schema": "s3.selfhost.reference-current-call-inventory.v1",
    }


def _source() -> bytes:
    return (
        "foreign fn host_value(x: i64) -> i64\n"
        "\n"
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
        "\n"
        "fn main() -> tryte:\n"
        "    mut value: i64 = add(host_value(1), 2)\n"
        "    return to_tryte(value)\n"
    ).encode("utf-8")


def test_ast_inventory_counts_nested_internal_foreign_and_conversion_calls() -> None:
    report = audit_source(_source(), contract=_contract())
    assert report["status"] == "PASS_HOSTED_CURRENT_SOURCE_CALL_INVENTORY"
    ast = report["ast"]
    assert ast["total_call_expressions"] == 3
    assert ast["total_argument_occurrences"] == 4
    assert ast["max_arity"] == 2
    assert ast["arity_histogram"] == {"1": 2, "2": 1}
    assert ast["internal_calls"] == 1
    assert ast["foreign_calls"] == 1
    assert ast["builtin_or_other_calls"] == 1
    assert ast["dynamic_or_nonidentifier_callees"] == 0
    assert ast["per_callee"]["add"] == 1
    assert ast["per_callee"]["host_value"] == 1
    assert ast["per_callee"]["to_tryte"] == 1
    assert ast["per_caller"] == {"main": 3}


def test_o0_ir_does_not_require_ast_call_count_equality() -> None:
    report = audit_source(_source(), contract=_contract())
    ir = report["o0_ir"]
    # to_tryte is represented by typed IR conversion rather than a CALL.
    assert ir["total_call_instructions"] == 2
    assert ir["internal_calls"] == 1
    assert ir["foreign_calls"] == 1
    assert ir["builtin_or_other_calls"] == 0
    assert ir["total_operand_uses"] == 3
    assert ir["total_result_definitions"] == 2
    assert report["cross_view"]["call_counts_equal"] is False
    assert report["cross_view"]["argument_operand_counts_equal"] is False
    assert report["cross_view"]["equality_required"] is False


def test_historical_656_736_never_becomes_authority() -> None:
    report = audit_source(_source(), contract=_contract())
    assert report["historical_closure"]["calls_656_arguments_736_authoritative_for_this_source"] is False
    assert report["qualification"]["physical_capacity_selected_by_this_report"] is False
    assert report["qualification"]["native_stage1_call_high_water_required"] is True
    assert report["qualification"]["native_stage1_call_argument_high_water_required"] is True
    assert report["native_evidence"] is False


def test_report_is_bound_to_exact_source_bytes() -> None:
    source = _source()
    report = audit_source(source, contract=_contract())
    validate_inventory_for_source(report, source)
    with pytest.raises(CurrentCallInventoryError, match="stale"):
        validate_inventory_for_source(report, source + b"\n")


def test_contract_schema_mismatch_fails_closed() -> None:
    with pytest.raises(CurrentCallInventoryError, match="schema mismatch"):
        audit_source(_source(), contract={"schema": "wrong"})
