from __future__ import annotations

from tools.audit_stage1_local_namespace_rebase import audit


def _source() -> str:
    return (
        "mut ir_parameter_owner: i64[68] = [0]\n"
        "mut ir_parameter_name: i64[68] = [0]\n"
        "mut ir_parameter_ordinal: i64[68] = [0]\n"
        "mut ir_parameter_type: i64[68] = [0]\n"
    )


def _contract() -> dict[str, object]:
    return {
        "semantic_id_layout": {
            "parameter_domain": "[0,parameter_count)",
            "local_domain_start": "parameter_count",
            "dynamic_start": "parameter_count + local_record_count",
            "fixed_64_parameter_reservation": False,
        }
    }


def test_historical_local_transform_is_fail_closed_after_dynamic_rebase() -> None:
    result = audit(
        source=_source(),
        local_transform=(
            'if "mut ir_parameter_records: i64[64]" not in parameter_source:\n'
            "    pass\n"
            "record = 64 + local_capture_index + 1\n"
        ),
        value_contract=_contract(),
    )

    assert result["status"] == "LOCAL_TRANSFORM_REBASE_REQUIRED"
    assert result["local_transform_execution_allowed"] is False
    assert result["historical_local_transform_assumptions"]["requires_packed_parameter_records_64"] is True
    assert result["historical_local_transform_assumptions"]["packs_local_value_id_from_fixed_64"] is True


def test_rebased_local_transform_is_namespace_consistent() -> None:
    result = audit(
        source=_source(),
        local_transform="record = parameter_count + local_capture_index + 1\n",
        value_contract=_contract(),
    )

    assert result["status"] == "LOCAL_TRANSFORM_NAMESPACE_CONSISTENT"
    assert result["local_transform_execution_allowed"] is True
