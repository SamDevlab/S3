from __future__ import annotations

import pytest

from tools.audit_stage1_ir_v2_storage_reuse import (
    BLOCK_RADIX,
    OPCODE_RADIX,
    SIGNED_I64_MAX,
    VALUE_ID_RADIX,
    SOURCE,
    audit,
    instruction_record_limit,
    pack_instruction,
    unpack_instruction,
)


def test_instruction_mixed_radix_boundary_round_trip() -> None:
    fields = (
        BLOCK_RADIX - 1,
        OPCODE_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )
    record = pack_instruction(*fields)
    assert record == instruction_record_limit()
    assert record <= SIGNED_I64_MAX
    assert unpack_instruction(record) == fields


def test_instruction_zero_record_round_trip() -> None:
    fields = (0, 0, 0, 0, 0, 0)
    assert unpack_instruction(pack_instruction(*fields)) == fields


@pytest.mark.parametrize(
    ("index", "bad_value"),
    [
        (0, BLOCK_RADIX),
        (1, OPCODE_RADIX),
        (2, VALUE_ID_RADIX),
        (3, VALUE_ID_RADIX),
        (4, VALUE_ID_RADIX),
        (5, VALUE_ID_RADIX),
    ],
)
def test_instruction_mixed_radix_rejects_overflow(index: int, bad_value: int) -> None:
    fields = [0, 0, 0, 0, 0, 0]
    fields[index] = bad_value
    with pytest.raises(ValueError, match="outside mixed-radix domain"):
        pack_instruction(*fields)


def test_current_source_exposes_reusable_bounded_banks_and_lifetime() -> None:
    result = audit(SOURCE.read_text(encoding="utf-8"))
    assert result["status"] == "STATIC_STORAGE_AUDIT_PASS"
    assert result["guards"]["event_bank_layout"] is True
    assert result["guards"]["value_bank_layout"] is True
    assert result["guards"]["call_table_layout"] is True
    assert result["guards"]["call_argument_layout"] is True
    assert result["guards"]["legacy_block_layout"] is True
    assert result["guards"]["ownerless_instruction_record_fits_signed_i64"] is True
    assert result["guards"]["instruction_block_domain_supports_730_blocks"] is True
    assert result["guards"]["event_bank_safe_overwrite_frontier"] is True
    assert result["instruction_record"]["owner_field"] == (
        "NOT_STORED_DERIVED_FROM_PACKED_BLOCK_RECORD"
    )
    assert result["instruction_record"]["block_capacity"] == 730
    assert result["event_bank_lifetime"]["event_bank_refs_after_frontier"] == 0
    assert result["event_bank_lifetime"]["frontier"] == (
        "AFTER_LEGACY_EVENT_VERIFIER_BEFORE_REMAINING_VERIFIER_AND_PIPELINE_DECISION"
    )
    assert result["structural_markers"]["event_count_drives_instruction_count"] is True
    assert result["storage_decision"]["new_four_bank_instruction_arrays"] == "NOT_SELECTED"
    assert result["storage_decision"]["new_call_result_array"] == "NOT_SELECTED"


def test_storage_audit_fails_if_event_bank_is_read_after_overwrite_frontier() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    mutated = source + "\nfn forbidden_late_event_read() -> i64:\n    return ir_ast_event_records_0[0]\n"
    result = audit(mutated)
    assert result["status"] == "STATIC_STORAGE_AUDIT_FAIL"
    assert result["event_bank_lifetime"]["event_bank_refs_after_frontier"] > 0
    assert result["guards"]["event_bank_safe_overwrite_frontier"] is False


def test_storage_audit_fails_if_second_call_bank_layout_drifts() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    mutated = source.replace(
        "mut ir_call_flags_1: tryte[365]",
        "mut ir_call_flags_1: tryte[364]",
        1,
    )
    assert mutated != source
    result = audit(mutated)
    assert result["status"] == "STATIC_STORAGE_AUDIT_FAIL"
    assert result["guards"]["call_table_layout"] is False


def test_aux_domain_is_id_sized_not_arbitrary_i64() -> None:
    with pytest.raises(ValueError, match="aux outside mixed-radix domain"):
        pack_instruction(1, 1, 1, 1, 1, VALUE_ID_RADIX)


def test_boolean_instruction_field_is_rejected() -> None:
    with pytest.raises(ValueError, match="block outside mixed-radix domain"):
        pack_instruction(True, 1, 1, 1, 1, 1)
