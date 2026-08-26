from __future__ import annotations

import pytest

from tools.audit_stage1_compact_block_capacity import (
    BANK_COUNT,
    BANK_SIZE,
    BLOCK_CAPACITY,
    CHECKPOINT_REQUIRED_BLOCKS,
    FUNCTION_CAPACITY,
    SIGNED_I64_MAX,
    TERMINATOR_KIND_CAPACITY,
    audit,
    bank_slot,
    pack_block_record,
    unpack_block_record,
)


@pytest.mark.parametrize(
    ("block_index", "expected"),
    [
        (0, (0, 0)),
        (364, (0, 364)),
        (365, (1, 0)),
        (729, (1, 364)),
        (730, (2, 0)),
        (1094, (2, 364)),
        (1095, (3, 0)),
        (1333, (3, 238)),
        (1459, (3, 364)),
    ],
)
def test_four_bank_routing_boundaries(
    block_index: int, expected: tuple[int, int]
) -> None:
    assert bank_slot(block_index) == expected


def test_checkpoint_capacity_has_exact_bounded_headroom() -> None:
    assert BANK_SIZE == 365
    assert BANK_COUNT == 4
    assert BLOCK_CAPACITY == 1460
    assert CHECKPOINT_REQUIRED_BLOCKS == 1334
    assert BLOCK_CAPACITY - CHECKPOINT_REQUIRED_BLOCKS == 126


@pytest.mark.parametrize("owner", [0, FUNCTION_CAPACITY - 1])
@pytest.mark.parametrize("terminator", range(TERMINATOR_KIND_CAPACITY))
@pytest.mark.parametrize("target_a", [0, 364, 365, 1095, 1333, BLOCK_CAPACITY - 1])
@pytest.mark.parametrize("target_b", [0, 364, 365, 1095, 1333, BLOCK_CAPACITY - 1])
def test_packed_block_record_roundtrip(
    owner: int, terminator: int, target_a: int, target_b: int
) -> None:
    record = pack_block_record(owner, terminator, target_a, target_b)
    assert 0 < record <= SIGNED_I64_MAX
    assert unpack_block_record(record) == (owner, terminator, target_a, target_b)


def test_maximum_record_is_far_inside_signed_i64() -> None:
    record = pack_block_record(
        FUNCTION_CAPACITY - 1,
        TERMINATOR_KIND_CAPACITY - 1,
        BLOCK_CAPACITY - 1,
        BLOCK_CAPACITY - 1,
    )
    assert record == 415661999
    assert record < SIGNED_I64_MAX


@pytest.mark.parametrize(
    "call",
    [
        lambda: bank_slot(-1),
        lambda: bank_slot(BLOCK_CAPACITY),
        lambda: pack_block_record(FUNCTION_CAPACITY, 0, 0, 0),
        lambda: pack_block_record(0, TERMINATOR_KIND_CAPACITY, 0, 0),
        lambda: pack_block_record(0, 0, BLOCK_CAPACITY, 0),
        lambda: pack_block_record(0, 0, 0, BLOCK_CAPACITY),
    ],
)
def test_out_of_domain_values_fail_closed(call) -> None:
    with pytest.raises(ValueError):
        call()


def test_current_source_contract_detects_verifier_relationships() -> None:
    source = (
        "mut ir_block_function: i64[365] = [0]\n"
        "mut ir_block_first_instruction: i64[365] = [0]\n"
        "mut ir_block_instruction_count: i64[365] = [0]\n"
        "mut ir_block_terminator: i64[365] = [0]\n"
        "mut ir_block_target_a: i64[365] = [0]\n"
        "mut ir_block_target_b: i64[365] = [0]\n"
        "ir_block_function[verifier_block] < function_count\n"
        "ir_block_terminator[verifier_block] > 0\n"
        "ir_block_target_a[verifier_block] < ir_block_count\n"
        "ir_block_target_b[verifier_block] < ir_block_count\n"
    )
    result = audit(source)
    assert result["status"] == "STATIC_COMPACT_BLOCK_CAPACITY_CONTRACT_PASS"
    assert result["native_evidence"] is False
    assert result["canonical_source_mutated"] is False
