"""Static contract for the compact Stage1 block-capacity candidate.

This module is intentionally host-only.  It does not rewrite the canonical
compiler and it does not claim native qualification.  Its purpose is to freeze
the reversible packing and bank-routing rules used by the current PR #268
scratch candidate while native Linux qualification proceeds independently.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "compact-block-capacity-static-contract.json"
)

BANK_SIZE = 365
BANK_COUNT = 4
BLOCK_CAPACITY = BANK_SIZE * BANK_COUNT
CHECKPOINT_REQUIRED_BLOCKS = 1334
FUNCTION_CAPACITY = 64
TERMINATOR_KIND_CAPACITY = 3
SIGNED_I64_MAX = 2**63 - 1

LEGACY_BLOCK_ARRAYS = (
    "ir_block_function",
    "ir_block_first_instruction",
    "ir_block_instruction_count",
    "ir_block_terminator",
    "ir_block_target_a",
    "ir_block_target_b",
)
SEMANTIC_BLOCK_FIELDS = (
    "ir_block_function",
    "ir_block_terminator",
    "ir_block_target_a",
    "ir_block_target_b",
)
STRUCTURAL_ONLY_FIELDS = (
    "ir_block_first_instruction",
    "ir_block_instruction_count",
)


def _validate_int(value: object, *, minimum: int, maximum: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{label} outside [{minimum},{maximum}]")
    return value


def bank_slot(block_index: int) -> tuple[int, int]:
    index = _validate_int(
        block_index, minimum=0, maximum=BLOCK_CAPACITY - 1, label="block_index"
    )
    return index // BANK_SIZE, index % BANK_SIZE


def pack_block_record(
    owner_function: int,
    terminator_kind: int,
    target_a: int,
    target_b: int,
) -> int:
    """Pack the four currently verified block relationships into one i64.

    owner_function is encoded as owner+1 so zero remains available as an
    uninitialized physical record.  The remaining domains are direct encodings.
    """

    owner = _validate_int(
        owner_function, minimum=0, maximum=FUNCTION_CAPACITY - 1, label="owner_function"
    )
    terminator = _validate_int(
        terminator_kind,
        minimum=0,
        maximum=TERMINATOR_KIND_CAPACITY - 1,
        label="terminator_kind",
    )
    first = _validate_int(
        target_a, minimum=0, maximum=BLOCK_CAPACITY - 1, label="target_a"
    )
    second = _validate_int(
        target_b, minimum=0, maximum=BLOCK_CAPACITY - 1, label="target_b"
    )

    value = owner + 1
    value = value * TERMINATOR_KIND_CAPACITY + terminator
    value = value * BLOCK_CAPACITY + first
    value = value * BLOCK_CAPACITY + second
    if value > SIGNED_I64_MAX:
        raise ValueError("packed block record exceeds signed i64")
    return value


def unpack_block_record(record: int) -> tuple[int, int, int, int]:
    value = _validate_int(
        record, minimum=1, maximum=SIGNED_I64_MAX, label="record"
    )
    target_b = value % BLOCK_CAPACITY
    value //= BLOCK_CAPACITY
    target_a = value % BLOCK_CAPACITY
    value //= BLOCK_CAPACITY
    terminator = value % TERMINATOR_KIND_CAPACITY
    value //= TERMINATOR_KIND_CAPACITY
    owner = value - 1
    _validate_int(
        owner, minimum=0, maximum=FUNCTION_CAPACITY - 1, label="decoded_owner"
    )
    return owner, terminator, target_a, target_b


def _array_capacity(source: str, name: str) -> int | None:
    match = re.search(
        rf"(?m)^\s*mut\s+{re.escape(name)}:\s*i64\[(\d+)\]\s*=",
        source,
    )
    return int(match.group(1)) if match else None


def _lhs_write_count(source: str, name: str) -> int:
    return len(
        re.findall(
            rf"(?m)^\s*{re.escape(name)}\[[^\]]+\]\s*=",
            source,
        )
    )


def _indexed_occurrence_count(source: str, name: str) -> int:
    return len(re.findall(rf"{re.escape(name)}\[[^\]]+\]", source))


def audit(source: str) -> dict[str, Any]:
    arrays = {name: _array_capacity(source, name) for name in LEGACY_BLOCK_ARRAYS}
    writes = {name: _lhs_write_count(source, name) for name in LEGACY_BLOCK_ARRAYS}
    indexed = {
        name: _indexed_occurrence_count(source, name) for name in LEGACY_BLOCK_ARRAYS
    }
    reads = {name: max(0, indexed[name] - writes[name]) for name in LEGACY_BLOCK_ARRAYS}

    maximum_record = pack_block_record(
        FUNCTION_CAPACITY - 1,
        TERMINATOR_KIND_CAPACITY - 1,
        BLOCK_CAPACITY - 1,
        BLOCK_CAPACITY - 1,
    )
    required_last_bank, required_last_slot = bank_slot(CHECKPOINT_REQUIRED_BLOCKS - 1)
    capacity_last_bank, capacity_last_slot = bank_slot(BLOCK_CAPACITY - 1)

    guards = {
        "legacy_block_arrays_present": all(arrays[name] is not None for name in LEGACY_BLOCK_ARRAYS),
        "legacy_block_arrays_are_single_365_banks": all(
            arrays[name] == BANK_SIZE for name in LEGACY_BLOCK_ARRAYS
        ),
        "checkpoint_requirement_fits_four_banks": CHECKPOINT_REQUIRED_BLOCKS <= BLOCK_CAPACITY,
        "checkpoint_requires_fourth_bank": required_last_bank == 3,
        "packing_fits_signed_i64": maximum_record <= SIGNED_I64_MAX,
        "verifier_reads_owner": "ir_block_function[verifier_block]" in source,
        "verifier_reads_terminator": "ir_block_terminator[verifier_block]" in source,
        "verifier_reads_target_a": "ir_block_target_a[verifier_block]" in source,
        "verifier_reads_target_b": "ir_block_target_b[verifier_block]" in source,
        "structural_fields_not_read_by_verifier": (
            "ir_block_first_instruction[verifier_block]" not in source
            and "ir_block_instruction_count[verifier_block]" not in source
        ),
    }
    status = (
        "STATIC_COMPACT_BLOCK_CAPACITY_CONTRACT_PASS"
        if all(guards.values())
        else "STATIC_COMPACT_BLOCK_CAPACITY_CONTRACT_FAIL"
    )
    return {
        "schema": "s3.selfhost.stage1-compact-block-capacity-static-contract.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "checkpoint_input": {
            "required_blocks": CHECKPOINT_REQUIRED_BLOCKS,
            "origin": "PR_268_CURRENT_NATIVE_SCRATCH_CHECKPOINT",
            "promotion_authority": False,
        },
        "physical_capacity": {
            "bank_size": BANK_SIZE,
            "bank_count": BANK_COUNT,
            "total_blocks": BLOCK_CAPACITY,
            "headroom_at_checkpoint": BLOCK_CAPACITY - CHECKPOINT_REQUIRED_BLOCKS,
            "required_last_bank": required_last_bank,
            "required_last_slot": required_last_slot,
            "capacity_last_bank": capacity_last_bank,
            "capacity_last_slot": capacity_last_slot,
        },
        "packing": {
            "fields": [
                "owner_function",
                "terminator_kind",
                "target_a",
                "target_b",
            ],
            "owner_encoding": "owner_plus_one",
            "terminator_domain": [0, TERMINATOR_KIND_CAPACITY - 1],
            "target_domain": [0, BLOCK_CAPACITY - 1],
            "maximum_packed_record": maximum_record,
            "signed_i64_max": SIGNED_I64_MAX,
            "reversible": True,
        },
        "canonical_legacy_storage": {
            "array_capacities": arrays,
            "indexed_occurrences": indexed,
            "lhs_writes": writes,
            "estimated_non_lhs_reads": reads,
            "semantic_fields_for_current_verifier": list(SEMANTIC_BLOCK_FIELDS),
            "structural_only_fields_in_current_verifier": list(STRUCTURAL_ONLY_FIELDS),
        },
        "guards": guards,
        "next": (
            "NATIVE_COMPACT_BLOCK_ROUNDTRIP_AND_SELF_SOURCE_QUALIFICATION"
            if status == "STATIC_COMPACT_BLOCK_CAPACITY_CONTRACT_PASS"
            else "RECONCILE_COMPACT_BLOCK_STATIC_CONTRACT"
        ),
        "general_emitter": "BLOCKED_REMAINING_TYPED_RELATIONSHIPS",
        "self_emit": "NOT_AUTHORIZED_BY_STATIC_CONTRACT",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = audit(args.source.resolve().read_text(encoding="utf-8"))
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"REQUIRED_BLOCKS={CHECKPOINT_REQUIRED_BLOCKS}")
    print(f"BLOCK_CAPACITY={BLOCK_CAPACITY}")
    print(f"HEADROOM={BLOCK_CAPACITY - CHECKPOINT_REQUIRED_BLOCKS}")
    print(f"MAX_PACKED_RECORD={result['packing']['maximum_packed_record']}")
    print("NATIVE_EVIDENCE=False")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if result["status"] == "STATIC_COMPACT_BLOCK_CAPACITY_CONTRACT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
