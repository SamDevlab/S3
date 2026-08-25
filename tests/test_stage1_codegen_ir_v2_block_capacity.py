from __future__ import annotations

import pytest

from tools.audit_stage1_codegen_ir_v2_block_capacity import (
    BLOCK_ID_RADIX,
    CANDIDATE_BLOCK_CAPACITY,
    OWNER_RADIX,
    SIGNED_I64_MAX,
    TERMINATOR_KIND_RADIX,
    VALUE_ID_RADIX,
    SOURCE,
    audit,
    legacy_ownerful_instruction_record_limit_at_730_blocks,
    ownerless_instruction_record_limit,
    pack_block,
    packed_block_record_limit,
    unpack_block,
)


def test_packed_block_boundary_round_trip() -> None:
    fields = (
        OWNER_RADIX - 1,
        TERMINATOR_KIND_RADIX - 1,
        BLOCK_ID_RADIX - 1,
        BLOCK_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )
    record = pack_block(*fields)
    assert record == packed_block_record_limit()
    assert record <= SIGNED_I64_MAX
    assert unpack_block(record) == fields


def test_packed_block_rejects_out_of_domain_target() -> None:
    with pytest.raises(ValueError, match="target_a outside packed-block domain"):
        pack_block(1, 1, BLOCK_ID_RADIX, 1, 1, 1)


def test_owner_must_move_out_of_instruction_when_block_capacity_doubles() -> None:
    assert ownerless_instruction_record_limit() <= SIGNED_I64_MAX
    assert legacy_ownerful_instruction_record_limit_at_730_blocks() > SIGNED_I64_MAX


def test_current_source_supports_static_two_bank_block_design() -> None:
    result = audit(SOURCE.read_text(encoding="utf-8"))
    assert result["status"] == "STATIC_BLOCK_CAPACITY_DESIGN_PASS"
    assert result["candidate"]["capacity"] == CANDIDATE_BLOCK_CAPACITY
    assert result["candidate"]["new_large_arrays_required"] == 0
    assert result["guards"]["legacy_six_block_arrays_present"] is True
    assert result["guards"]["first_instruction_is_write_only_in_current_source"] is True
    assert result["guards"]["instruction_count_is_write_only_in_current_source"] is True
    assert result["guards"]["two_existing_arrays_can_physically_hold_730_packed_blocks"] is True
    assert result["candidate"]["instruction_record_v2"]["owner_field"] == (
        "REMOVED_OWNER_DERIVED_FROM_BLOCK_RECORD"
    )


def test_block_audit_fails_if_first_instruction_becomes_a_semantic_read() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    mutated = source + (
        "\nfn forbidden_block_index_read() -> i64:\n"
        "    return ir_block_first_instruction[0]\n"
    )
    result = audit(mutated)
    assert result["status"] == "STATIC_BLOCK_CAPACITY_DESIGN_FAIL"
    assert result["guards"]["first_instruction_is_write_only_in_current_source"] is False


def test_parameter_candidate_projection_is_reported_as_static_only() -> None:
    result = audit(SOURCE.read_text(encoding="utf-8"))
    projection = result["parameter_candidate_static_projection"]
    assert projection["projection_is_native_evidence"] is False
    assert projection["projected_blocks"] >= result["legacy"]["last_native_blocks"]
    assert projection["strict_additional_match_or_while_budget"] >= 0
