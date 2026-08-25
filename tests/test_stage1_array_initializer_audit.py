from __future__ import annotations

from tools.audit_stage1_array_initializers import SOURCE, audit


def test_current_stage1_array_initializers_are_statically_well_formed() -> None:
    result = audit(SOURCE.read_text(encoding="utf-8"))
    assert result["status"] == "STATIC_ARRAY_INITIALIZER_AUDIT_PASS"
    assert result["guards"]["found_fixed_arrays"] is True
    assert result["guards"]["all_matched_array_initializers_have_declared_item_count"] is True
    assert result["summary"]["zero_initializer_items"] > 0
    assert result["ir_v2_implication"]["static_zero_count_is_not_ir_value_headroom"] is True


def test_audit_detects_initializer_size_mismatch() -> None:
    source = "fn main() -> tryte:\n    mut values: i64[3] = [0, 0]\n    return 0\n"
    result = audit(source)
    assert result["status"] == "STATIC_ARRAY_INITIALIZER_AUDIT_FAIL"
    assert result["summary"]["malformed_array_names"] == ["values"]


def test_audit_does_not_call_nonzero_numeric_array_all_zero() -> None:
    source = "fn main() -> tryte:\n    mut values: i64[3] = [0, 1, 0]\n    return 0\n"
    result = audit(source)
    assert result["summary"]["matched_fixed_arrays"] == 1
    assert result["summary"]["all_zero_arrays"] == 0
    assert result["summary"]["non_zero_numeric_arrays"] == 1
    assert result["arrays"][0]["zero_items"] == 2
