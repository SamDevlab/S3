from __future__ import annotations

from tools.patch_stage1_compact_local_metadata import LOCAL_CAPACITY, SOURCE, transform


def test_compact_local_candidate_chains_parameter_semantic_values() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = transform(source)

    assert candidate != source
    assert "ir_return_operand[current_function] = parameter_scan" in candidate
    assert "ir_return_operand[current_function] = ir_parameter_ordinal[parameter_scan]" not in candidate
    assert "mut ir_parameter_records: i64[64]" not in candidate


def test_compact_local_candidate_adds_bounded_record_lane_without_extra_value_ids() -> None:
    candidate = transform(SOURCE.read_text(encoding="utf-8"))

    assert f"mut ir_local_records: i64[{LOCAL_CAPACITY}]" in candidate
    assert "ir_local_records[ir_local_record_count] =" in candidate
    assert "mut ir_local_value_id:" not in candidate
    assert "mut ir_parameter_value_id:" not in candidate
    assert "match parameter_count + ir_local_record_count < 1461:" in candidate


def test_compact_local_candidate_uses_existing_token_ring_for_scalar_and_array_suffixes() -> None:
    candidate = transform(SOURCE.read_text(encoding="utf-8"))

    assert "mut local_slot_2: i64 = slot - 2" in candidate
    assert "mut local_slot_7: i64 = slot - 7" in candidate
    assert "token_value[local_slot_4] == 87" in candidate
    assert "token_value[local_slot_7] == 87" in candidate
    assert "local_decl_kind = 1" in candidate
    assert "local_decl_kind = 2" in candidate
    assert "local_decl_extent = token_value[local_slot_2]" in candidate


def test_compact_local_candidate_fails_closed_on_incomplete_local_coverage() -> None:
    candidate = transform(SOURCE.read_text(encoding="utf-8"))

    assert "match ir_local_record_count == local_count:" in candidate
    assert "mut local_verify_index: i64 = 0" in candidate
    assert "match ir_local_records[local_verify_index] > 0:" in candidate
    assert candidate.count("verifier_ok = 0") > SOURCE.read_text(encoding="utf-8").count("verifier_ok = 0")


def test_compact_local_candidate_is_deterministic_and_non_destructive() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    first = transform(source)
    second = transform(source)

    assert first == second
    assert SOURCE.read_text(encoding="utf-8") == source
