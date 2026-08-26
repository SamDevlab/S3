from __future__ import annotations

from tools.patch_stage1_parameter_semantic_value_ids import SOURCE, transform


def test_parameter_semantic_value_candidate_uses_slot_identity_without_new_storage() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = transform(source)

    assert candidate != source
    assert transform(source) == candidate
    assert "ir_return_operand[current_function] = ir_parameter_ordinal[parameter_scan]" in source
    assert "ir_return_operand[current_function] = ir_parameter_ordinal[parameter_scan]" not in candidate
    assert "ir_return_operand[current_function] = parameter_scan" in candidate
    assert "mut ir_parameter_value_id:" not in candidate


def test_parameter_semantic_value_candidate_verifies_global_slot_owner() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = transform(source)

    assert candidate.count(
        "match ir_return_operand[general_parameter_scan] < parameter_count:"
    ) == 2
    assert candidate.count(
        "match ir_parameter_owner[ir_return_operand[general_parameter_scan]] == general_parameter_scan:"
    ) == 2
    assert "while general_parameter_type_scan < function_count:" in candidate
    assert "match valid_type_name(ir_parameter_type[general_parameter_type_index]):" in candidate


def test_parameter_semantic_value_candidate_resolves_value_id_to_abi_ordinal_only_at_emission() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = transform(source)

    lowering = (
        "emit_general_parameter_function(function_names[general_emit_index], "
        "ir_parameter_ordinal[ir_return_operand[general_emit_index]])"
    )
    assert candidate.count(lowering) == 2
    assert candidate.count(
        "emit_general_parameter_function(function_names[general_emit_index], ir_return_operand[general_emit_index])"
    ) == 0
