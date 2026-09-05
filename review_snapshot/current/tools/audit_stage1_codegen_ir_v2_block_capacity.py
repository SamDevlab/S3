"""Static feasibility audit for a 730-block Stage1 IR-v2 layout.

The legacy Stage1 source stores six independent block fields in six i64[365]
arrays. The codegen-complete IR-v2 instruction format already needs an explicit
block ID, which makes legacy ``first_instruction`` and ``instruction_count``
indexes redundant for the final representation. This audit checks whether two
of the existing arrays can instead become two 365-entry banks of packed block
records, yielding 730 blocks without introducing new large fixed arrays.

This is design/preflight evidence only. It neither transforms the compiler nor
claims native qualification.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-block-capacity-audit.json"
)

SIGNED_I64_MAX = 2**63 - 1
LEGACY_BLOCK_CAPACITY = 365
CANDIDATE_BLOCK_CAPACITY = 730
BLOCK_BANK_SIZE = 365
BLOCK_BANK_COUNT = 2
BLOCK_ID_RADIX = CANDIDATE_BLOCK_CAPACITY + 1  # none=0; ids 0..729 => 1..730
OWNER_RADIX = 65
TERMINATOR_KIND_RADIX = 8
OPCODE_RADIX = 64
VALUE_ID_RADIX = 1461
LAST_NATIVE_BLOCKS = 305
STRICT_LEGACY_BLOCK_MAX_PASS = LEGACY_BLOCK_CAPACITY - 1

_MATCH_LINE = re.compile(r"(?m)^\s*match\s+")
_WHILE_LINE = re.compile(r"(?m)^\s*while\s+")
_ARRAY_DECL = re.compile(
    r"(?m)^\s*mut\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<type>i64|tryte|trit)\[(?P<size>\d+)\]\s*=\s*\["
)

LEGACY_BLOCK_FIELDS = (
    "ir_block_function",
    "ir_block_first_instruction",
    "ir_block_instruction_count",
    "ir_block_terminator",
    "ir_block_target_a",
    "ir_block_target_b",
)


def packed_block_record_limit() -> int:
    """Max owner/kind/targets/condition/return packed block record."""
    return (
        OWNER_RADIX
        * TERMINATOR_KIND_RADIX
        * BLOCK_ID_RADIX
        * BLOCK_ID_RADIX
        * VALUE_ID_RADIX
        * VALUE_ID_RADIX
        - 1
    )


def ownerless_instruction_record_limit() -> int:
    """Max block/op/a/b/result/aux instruction record for 730 blocks."""
    return BLOCK_ID_RADIX * OPCODE_RADIX * VALUE_ID_RADIX**4 - 1


def legacy_ownerful_instruction_record_limit_at_730_blocks() -> int:
    """Shows why owner must move from instruction to the block record."""
    return OWNER_RADIX * BLOCK_ID_RADIX * OPCODE_RADIX * VALUE_ID_RADIX**4 - 1


def pack_block(
    owner_encoded: int,
    kind: int,
    target_a_encoded: int,
    target_b_encoded: int,
    condition_encoded: int,
    return_encoded: int,
) -> int:
    domains = (
        (owner_encoded, OWNER_RADIX, "owner"),
        (kind, TERMINATOR_KIND_RADIX, "kind"),
        (target_a_encoded, BLOCK_ID_RADIX, "target_a"),
        (target_b_encoded, BLOCK_ID_RADIX, "target_b"),
        (condition_encoded, VALUE_ID_RADIX, "condition"),
        (return_encoded, VALUE_ID_RADIX, "return"),
    )
    for value, radix, label in domains:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= radix:
            raise ValueError(f"{label} outside packed-block domain")
    record = owner_encoded
    for value, radix in (
        (kind, TERMINATOR_KIND_RADIX),
        (target_a_encoded, BLOCK_ID_RADIX),
        (target_b_encoded, BLOCK_ID_RADIX),
        (condition_encoded, VALUE_ID_RADIX),
        (return_encoded, VALUE_ID_RADIX),
    ):
        record = record * radix + value
    if record > SIGNED_I64_MAX:
        raise ValueError("packed block exceeds signed i64")
    return record


def unpack_block(record: int) -> tuple[int, int, int, int, int, int]:
    if (
        not isinstance(record, int)
        or isinstance(record, bool)
        or record < 0
        or record > packed_block_record_limit()
    ):
        raise ValueError("packed block outside domain")
    values: list[int] = []
    remainder = record
    for radix in (
        VALUE_ID_RADIX,
        VALUE_ID_RADIX,
        BLOCK_ID_RADIX,
        BLOCK_ID_RADIX,
        TERMINATOR_KIND_RADIX,
    ):
        values.append(remainder % radix)
        remainder //= radix
    return_encoded, condition_encoded, target_b, target_a, kind = values
    owner = remainder
    return owner, kind, target_a, target_b, condition_encoded, return_encoded


def _decls(source: str) -> dict[str, tuple[str, int]]:
    return {
        m.group("name"): (m.group("type"), int(m.group("size")))
        for m in _ARRAY_DECL.finditer(source)
    }


def _subscript_accesses(source: str, name: str) -> tuple[int, int, int]:
    """Return total subscript refs, writes, and inferred reads for one array."""
    total = len(re.findall(rf"\b{re.escape(name)}\s*\[", source))
    writes = len(re.findall(rf"\b{re.escape(name)}\s*\[[^\]]+\]\s*=", source))
    return total, writes, total - writes


def _count_control(source: str) -> tuple[int, int]:
    return len(_MATCH_LINE.findall(source)), len(_WHILE_LINE.findall(source))


def audit(source: str) -> dict[str, object]:
    declarations = _decls(source)
    legacy_layout = {
        name: declarations.get(name)
        for name in LEGACY_BLOCK_FIELDS
    }
    legacy_layout_pass = all(
        spec == ("i64", LEGACY_BLOCK_CAPACITY)
        for spec in legacy_layout.values()
    )

    accesses = {
        name: dict(zip(("subscript_refs", "writes", "reads"), _subscript_accesses(source, name)))
        for name in LEGACY_BLOCK_FIELDS
    }
    first_instruction_write_only = accesses["ir_block_first_instruction"]["reads"] == 0
    instruction_count_write_only = accesses["ir_block_instruction_count"]["reads"] == 0

    current_matches, current_whiles = _count_control(source)

    block_limit = packed_block_record_limit()
    ownerless_instruction_limit = ownerless_instruction_record_limit()
    ownerful_instruction_limit = legacy_ownerful_instruction_record_limit_at_730_blocks()

    boundary = (
        OWNER_RADIX - 1,
        TERMINATOR_KIND_RADIX - 1,
        BLOCK_ID_RADIX - 1,
        BLOCK_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )
    block_round_trip = unpack_block(pack_block(*boundary)) == boundary

    guards = {
        "legacy_six_block_arrays_present": legacy_layout_pass,
        "first_instruction_is_write_only_in_current_source": first_instruction_write_only,
        "instruction_count_is_write_only_in_current_source": instruction_count_write_only,
        "packed_block_record_fits_signed_i64": block_limit <= SIGNED_I64_MAX,
        "packed_block_record_round_trip": block_round_trip,
        "ownerless_730_block_instruction_record_fits_signed_i64": (
            ownerless_instruction_limit <= SIGNED_I64_MAX
        ),
        "ownerful_730_block_instruction_record_does_not_fit_signed_i64": (
            ownerful_instruction_limit > SIGNED_I64_MAX
        ),
        "two_existing_arrays_can_physically_hold_730_packed_blocks": (
            BLOCK_BANK_COUNT * BLOCK_BANK_SIZE == CANDIDATE_BLOCK_CAPACITY
        ),
    }

    return {
        "schema": "s3.selfhost.codegen-ir-v2-block-capacity-audit.v1",
        "status": (
            "STATIC_BLOCK_CAPACITY_DESIGN_PASS"
            if all(guards.values())
            else "STATIC_BLOCK_CAPACITY_DESIGN_FAIL"
        ),
        "native_evidence": False,
        "canonical_source_mutated": False,
        "legacy": {
            "capacity": LEGACY_BLOCK_CAPACITY,
            "strict_max_for_current_native_guard": STRICT_LEGACY_BLOCK_MAX_PASS,
            "last_native_blocks": LAST_NATIVE_BLOCKS,
            "fields": {
                name: list(spec) if spec is not None else None
                for name, spec in legacy_layout.items()
            },
            "accesses": accesses,
        },
        "parameter_candidate_static_projection": {
            "status": "NOT_APPLICABLE_HISTORICAL_PARAMETER_TRANSFORM",
            "base_match_lines_current_source": current_matches,
            "base_while_lines_current_source": current_whiles,
            "parameter_match_lines": None,
            "parameter_while_lines": None,
            "added_control_events": None,
            "projected_blocks": None,
            "strict_remaining_blocks": None,
            "strict_additional_match_or_while_budget": None,
            "projection_is_native_evidence": False,
            "reason": (
                "The historical compaction+parameter transform uses anchors "
                "that are absent from the current canonical source; no physical "
                "projection is synthesized from stale text."
            ),
        },
        "candidate": {
            "capacity": CANDIDATE_BLOCK_CAPACITY,
            "physical_banks": BLOCK_BANK_COUNT,
            "bank_size": BLOCK_BANK_SIZE,
            "new_large_arrays_required": 0,
            "packed_block_fields": [
                "owner_function_id",
                "terminator_kind",
                "target_a_block_id",
                "target_b_block_id",
                "condition_value_id",
                "return_value_id",
            ],
            "first_instruction_field": "DROPPED_FROM_IR_V2_BLOCK_RECORD_INSTRUCTION_CARRIES_BLOCK_ID",
            "instruction_count_field": "DROPPED_FROM_IR_V2_BLOCK_RECORD_INSTRUCTION_CARRIES_BLOCK_ID",
            "packed_block_max": block_limit,
            "signed_i64_max": SIGNED_I64_MAX,
            "instruction_record_v2": {
                "fields": [
                    "block_id",
                    "opcode",
                    "operand_a_value_id",
                    "operand_b_value_id",
                    "result_value_id",
                    "aux_id",
                ],
                "owner_field": "REMOVED_OWNER_DERIVED_FROM_BLOCK_RECORD",
                "max_encoded": ownerless_instruction_limit,
                "fits_signed_i64": ownerless_instruction_limit <= SIGNED_I64_MAX,
            },
            "rejected_instruction_layout": {
                "fields": "owner + block + opcode + four value-id lanes",
                "max_encoded": ownerful_instruction_limit,
                "fits_signed_i64": ownerful_instruction_limit <= SIGNED_I64_MAX,
                "reason": "doubling block IDs while retaining owner in each instruction exceeds signed i64",
            },
        },
        "guards": guards,
        "decision": (
            "PREPARE_PACKED_BLOCK_CAPACITY_CANDIDATE_BEFORE_LOCAL_METADATA_IF_NATIVE_PARAMETER_BLOCK_HEADROOM_IS_INSUFFICIENT"
        ),
        "qualification_rule": (
            "Static feasibility does not authorize source promotion. A block-capacity source transform must build a real Stage1, self-source through the verifier boundary, preserve CFG/call/value invariants, and demonstrate block_count < 730 before becoming a native candidate PASS."
        ),
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    result = audit(args.source.resolve().read_text(encoding="utf-8"))
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    projection = result["parameter_candidate_static_projection"]
    print(f"PROJECTED_PARAMETER_BLOCKS={projection['projected_blocks']}")
    print(f"STRICT_ADDITIONAL_CONTROL_BUDGET={projection['strict_additional_match_or_while_budget']}")
    print(f"PACKED_BLOCK_MAX={result['candidate']['packed_block_max']}")
    print(f"OWNERLESS_INSTRUCTION_MAX={result['candidate']['instruction_record_v2']['max_encoded']}")
    print(f"OWNERFUL_730_BLOCK_INSTRUCTION_FITS={result['candidate']['rejected_instruction_layout']['fits_signed_i64']}")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] == "STATIC_BLOCK_CAPACITY_DESIGN_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
