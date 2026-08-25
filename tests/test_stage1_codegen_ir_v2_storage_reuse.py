from __future__ import annotations

import pytest

from tools.audit_stage1_ir_v2_storage_reuse import (
    BLOCK_RADIX,
    OPCODE_RADIX,
    OWNER_RADIX,
    SIGNED_I64_MAX,
    TERMINATOR_KIND_RADIX,
    VALUE_ID_RADIX,
    SOURCE,
    audit,
    instruction_record_limit,
    pack_instruction,
    pack_terminator,
    terminator_record_limit,
    unpack_instruction,
    unpack_terminator,
)


def test_instruction_mixed_radix_boundary_round_trip() -> None:
    fields = (
        OWNER_RADIX - 1,
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
    fields = (0, 0, 0, 0, 0, 0, 0)
    assert unpack_instruction(pack_instruction(*fields)) == fields


@pytest.mark.parametrize(
    ("index", "bad_value"),
    [
        (0, OWNER_RADIX),
        (1, BLOCK_RADIX),
        (2, OPCODE_RADIX),
        (3, VALUE_ID_RADIX),
        (4, VALUE_ID_RADIX),
        (5, VALUE_ID_RADIX),
        (6, VALUE_ID_RADIX),
    ],
)
def test_instruction_mixed_radix_rejects_overflow(index: int, bad_value: int) -> None:
    fields = [0, 0, 0, 0, 0, 0, 0]
    fields[index] = bad_value
    with pytest.raises(ValueError, match="outside mixed-radix domain"):
        pack_instruction(*fields)


def test_terminator_mixed_radix_boundary_round_trip() -> None:
    fields = (
        TERMINATOR_KIND_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )
    record = pack_terminator(*fields)
    assert record == terminator_record_limit()
    assert record <= SIGNED_I64_MAX
    assert unpack_terminator(record) == fields


def test_current_source_exposes_reusable_bounded_banks() -> None:
    result = audit(SOURCE.read_text(encoding="utf-8"))
    assert result["status"] == "STATIC_STORAGE_AUDIT_PASS"
    assert result["guards"]["event_bank_layout"] is True
    assert result["guards"]["value_bank_layout"] is True
    assert result["guards"]["call_argument_layout"] is True
    assert result["guards"]["block_layout"] is True
    assert result["structural_markers"]["event_count_drives_instruction_count"] is True
    assert result["storage_decision"]["new_four_bank_instruction_arrays"] == "NOT_SELECTED"
    assert result["storage_decision"]["new_call_result_array"] == "NOT_SELECTED"


def test_aux_domain_is_id_sized_not_arbitrary_i64() -> None:
    with pytest.raises(ValueError, match="aux outside mixed-radix domain"):
        pack_instruction(1, 1, 1, 1, 1, 1, VALUE_ID_RADIX)
