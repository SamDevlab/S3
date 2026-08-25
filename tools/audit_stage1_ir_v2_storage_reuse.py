"""Static audit for Stage1 IR-v2 physical-storage reuse.

The codegen-complete storage contract is intentionally split by responsibility:
- packed block records own function identity, terminators and CFG targets;
- instruction records carry block ID, opcode, operands, result and auxiliary ID;
- value records own semantic values/literals;
- call tables keep callee/argument metadata.

Keeping function owner in the block record is required for the prepared 730-block
layout: owner+730-block instruction records exceed signed i64, while the
ownerless instruction record fits with wide margin.

This audit checks physical event/value/call storage, the ownerless instruction
encoding, and the safe event-bank overwrite frontier. Packed-block feasibility
is independently audited by ``audit_stage1_codegen_ir_v2_block_capacity.py``.
Static PASS never substitutes for native Stage1 qualification.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tools.audit_stage1_codegen_ir_v2_block_capacity import (
    BLOCK_ID_RADIX,
    CANDIDATE_BLOCK_CAPACITY,
    SIGNED_I64_MAX,
    ownerless_instruction_record_limit,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-storage-reuse-audit.json"
)

EVENT_BANK_SIZE = 365
EVENT_BANK_COUNT = 4
VALUE_BANK_SIZE = 365
VALUE_BANK_COUNT = 4
CALL_BANK_SIZE = 365
CALL_ARG_BANK_SIZES = (365, 365, 16)
LEGACY_BLOCK_CAPACITY = 365
VALUE_ID_RADIX = 1461  # none=0; value ids 0..1459 encode to 1..1460
BLOCK_RADIX = BLOCK_ID_RADIX
OPCODE_RADIX = 64

_ARRAY_DECL = re.compile(
    r"(?m)^\s*mut\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<type>i64|tryte|trit)\[(?P<size>\d+)\]\s*=\s*\["
)
_EVENT_BANK_REF = re.compile(r"\bir_ast_event_records_[0-3]\b")


def instruction_record_limit() -> int:
    return ownerless_instruction_record_limit()


def pack_instruction(
    block_encoded: int,
    opcode: int,
    operand_a_encoded: int,
    operand_b_encoded: int,
    result_encoded: int,
    aux_encoded: int,
) -> int:
    fields = (
        (block_encoded, BLOCK_RADIX, "block"),
        (opcode, OPCODE_RADIX, "opcode"),
        (operand_a_encoded, VALUE_ID_RADIX, "operand_a"),
        (operand_b_encoded, VALUE_ID_RADIX, "operand_b"),
        (result_encoded, VALUE_ID_RADIX, "result"),
        (aux_encoded, VALUE_ID_RADIX, "aux"),
    )
    for value, radix, label in fields:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= radix:
            raise ValueError(f"{label} outside mixed-radix domain")
    record = block_encoded
    for value, radix in (
        (opcode, OPCODE_RADIX),
        (operand_a_encoded, VALUE_ID_RADIX),
        (operand_b_encoded, VALUE_ID_RADIX),
        (result_encoded, VALUE_ID_RADIX),
        (aux_encoded, VALUE_ID_RADIX),
    ):
        record = record * radix + value
    if record > SIGNED_I64_MAX:
        raise ValueError("instruction record exceeds signed i64")
    return record


def unpack_instruction(record: int) -> tuple[int, int, int, int, int, int]:
    if (
        not isinstance(record, int)
        or isinstance(record, bool)
        or record < 0
        or record > instruction_record_limit()
    ):
        raise ValueError("instruction record outside mixed-radix domain")
    values: list[int] = []
    remainder = record
    for radix in (
        VALUE_ID_RADIX,
        VALUE_ID_RADIX,
        VALUE_ID_RADIX,
        VALUE_ID_RADIX,
        OPCODE_RADIX,
    ):
        values.append(remainder % radix)
        remainder //= radix
    aux, result, operand_b, operand_a, opcode = values
    block = remainder
    return block, opcode, operand_a, operand_b, result, aux


def _declarations(source: str) -> dict[str, tuple[str, int]]:
    return {
        match.group("name"): (match.group("type"), int(match.group("size")))
        for match in _ARRAY_DECL.finditer(source)
    }


def _numbered_banks(
    declarations: dict[str, tuple[str, int]], prefix: str
) -> dict[int, tuple[str, int]]:
    result: dict[int, tuple[str, int]] = {}
    pattern = re.compile(re.escape(prefix) + r"(\d+)$")
    for name, spec in declarations.items():
        match = pattern.fullmatch(name)
        if match:
            result[int(match.group(1))] = spec
    return result


def _call_table_layout(
    declarations: dict[str, tuple[str, int]],
) -> tuple[dict[str, tuple[str, int] | None], bool]:
    expected: dict[str, tuple[str, int]] = {
        "ir_call_callee": ("tryte", CALL_BANK_SIZE),
        "ir_call_arg_start": ("tryte", CALL_BANK_SIZE),
        "ir_call_arg_start_bank": ("tryte", CALL_BANK_SIZE),
        "ir_call_arg_count": ("i64", CALL_BANK_SIZE),
        "ir_call_flags": ("tryte", CALL_BANK_SIZE),
        "ir_call_callee_1": ("tryte", CALL_BANK_SIZE),
        "ir_call_arg_start_1": ("tryte", CALL_BANK_SIZE),
        "ir_call_arg_start_bank_1": ("tryte", CALL_BANK_SIZE),
        "ir_call_arg_count_1": ("i64", CALL_BANK_SIZE),
        "ir_call_flags_1": ("tryte", CALL_BANK_SIZE),
    }
    observed = {name: declarations.get(name) for name in expected}
    return observed, all(observed[name] == spec for name, spec in expected.items())


def _event_lifetime(source: str) -> dict[str, object]:
    writer = source.find("match ir_ast_event_count < 1460:")
    control_scan = source.find("mut control_scan_index: i64 = 0")
    legacy_event_verifier = source.find("mut event_verify_index: i64 = 0")
    post_event_verifier = (
        source.find("mut verify_index: i64 = 0", legacy_event_verifier)
        if legacy_event_verifier >= 0
        else -1
    )
    ordered = (
        writer >= 0
        and control_scan > writer
        and legacy_event_verifier > control_scan
        and post_event_verifier > legacy_event_verifier
    )
    refs_after_frontier = (
        _EVENT_BANK_REF.findall(source[post_event_verifier:])
        if post_event_verifier >= 0
        else []
    )
    proven = bool(ordered and not refs_after_frontier)
    return {
        "writer_anchor_found": writer >= 0,
        "control_scan_anchor_found": control_scan >= 0,
        "legacy_event_verifier_anchor_found": legacy_event_verifier >= 0,
        "post_event_verifier_anchor_found": post_event_verifier >= 0,
        "anchors_ordered": ordered,
        "event_bank_refs_after_frontier": len(refs_after_frontier),
        "safe_overwrite_frontier_proven": proven,
        "frontier": (
            "AFTER_LEGACY_EVENT_VERIFIER_BEFORE_REMAINING_VERIFIER_AND_PIPELINE_DECISION"
            if proven
            else "NOT_PROVEN"
        ),
        "required_v2_sequence": [
            "preserve legacy event records through control lowering",
            "preserve legacy event records through legacy event verifier",
            "rewrite event banks in place as ownerless IR-v2 instructions after the frontier",
            "derive instruction owner through instruction.block_id -> packed_block.owner_function_id",
            "run the new IR-v2 verifier",
            "allow general emitter only after IR-v2 verifier PASS",
        ],
    }


def audit(source: str) -> dict[str, object]:
    declarations = _declarations(source)
    event_banks = _numbered_banks(declarations, "ir_ast_event_records_")
    value_banks = _numbered_banks(declarations, "ir_value_records_")
    legacy_instruction_banks = _numbered_banks(declarations, "ir_instruction_records_")

    call_arg_specs = {
        name: declarations.get(name)
        for name in ("ir_call_args_0", "ir_call_args_1", "ir_call_args_2")
    }
    call_table_specs, call_table_layout_pass = _call_table_layout(declarations)
    block_fields = {
        name: declarations.get(name)
        for name in (
            "ir_block_function",
            "ir_block_first_instruction",
            "ir_block_instruction_count",
            "ir_block_terminator",
            "ir_block_target_a",
            "ir_block_target_b",
        )
    }

    event_layout_pass = (
        set(event_banks) == set(range(EVENT_BANK_COUNT))
        and all(spec == ("i64", EVENT_BANK_SIZE) for spec in event_banks.values())
    )
    value_layout_pass = (
        set(value_banks) == set(range(VALUE_BANK_COUNT))
        and all(spec == ("i64", VALUE_BANK_SIZE) for spec in value_banks.values())
    )
    call_arg_layout_pass = tuple(
        spec[1] if spec is not None else None for spec in call_arg_specs.values()
    ) == CALL_ARG_BANK_SIZES and all(
        spec is not None and spec[0] == "i64" for spec in call_arg_specs.values()
    )
    legacy_block_layout_pass = all(
        spec == ("i64", LEGACY_BLOCK_CAPACITY) for spec in block_fields.values()
    )

    instruction_limit = instruction_record_limit()
    boundary = (
        BLOCK_RADIX - 1,
        OPCODE_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )
    round_trip_pass = unpack_instruction(pack_instruction(*boundary)) == boundary

    event_lifetime = _event_lifetime(source)
    structural_markers = {
        "event_count_drives_instruction_count": "ir_instruction_count = ir_ast_event_count" in source,
        "events_currently_pack_owner_operand_offset": (
            "pack_ir_record(ir_ast_event_opcode, ir_ast_event_owner, ir_ast_event_operand, ir_ast_event_offset)"
            in source
        ),
        "calls_have_existing_instruction_linkage_seed": (
            "pack_ir_record(20, previous_value, ir_call_count, 0)" in source
            and "pack_ir_record(21, previous_value, ir_call_count, 0)" in source
        ),
        "legacy_block_fields_present_for_separate_packed_block_migration": all(
            spec is not None for spec in block_fields.values()
        ),
    }

    guards = {
        "event_bank_layout": event_layout_pass,
        "value_bank_layout": value_layout_pass,
        "call_table_layout": call_table_layout_pass,
        "call_argument_layout": call_arg_layout_pass,
        "legacy_block_layout": legacy_block_layout_pass,
        "ownerless_instruction_record_fits_signed_i64": instruction_limit <= SIGNED_I64_MAX,
        "ownerless_instruction_record_round_trip": round_trip_pass,
        "instruction_block_domain_supports_730_blocks": BLOCK_RADIX == CANDIDATE_BLOCK_CAPACITY + 1,
        "event_instruction_cardinality_marker": structural_markers[
            "event_count_drives_instruction_count"
        ],
        "event_bank_safe_overwrite_frontier": bool(
            event_lifetime["safe_overwrite_frontier_proven"]
        ),
    }

    return {
        "schema": "s3.selfhost.codegen-ir-v2-storage-reuse-audit.v3",
        "status": "STATIC_STORAGE_AUDIT_PASS" if all(guards.values()) else "STATIC_STORAGE_AUDIT_FAIL",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "declarations": {
            "event_banks": {str(k): list(v) for k, v in sorted(event_banks.items())},
            "value_banks": {str(k): list(v) for k, v in sorted(value_banks.items())},
            "legacy_instruction_banks_observed": {
                str(k): list(v) for k, v in sorted(legacy_instruction_banks.items())
            },
            "call_table": {
                name: list(spec) if spec is not None else None
                for name, spec in call_table_specs.items()
            },
            "call_argument_banks": {
                name: list(spec) if spec is not None else None
                for name, spec in call_arg_specs.items()
            },
            "legacy_block_fields": {
                name: list(spec) if spec is not None else None
                for name, spec in block_fields.items()
            },
        },
        "instruction_record": {
            "fields": [
                "block_id",
                "opcode",
                "operand_a_value_id",
                "operand_b_value_id",
                "result_value_id",
                "aux_id",
            ],
            "owner_field": "NOT_STORED_DERIVED_FROM_PACKED_BLOCK_RECORD",
            "block_capacity": CANDIDATE_BLOCK_CAPACITY,
            "max_encoded": instruction_limit,
            "signed_i64_max": SIGNED_I64_MAX,
            "headroom_to_i64_max": SIGNED_I64_MAX - instruction_limit,
            "radices": {
                "block": BLOCK_RADIX,
                "opcode": OPCODE_RADIX,
                "operand_a": VALUE_ID_RADIX,
                "operand_b": VALUE_ID_RADIX,
                "result": VALUE_ID_RADIX,
                "aux": VALUE_ID_RADIX,
            },
            "aux_constraint": "ID/reference only; arbitrary raw i64 literal payload belongs in the value representation",
        },
        "event_bank_lifetime": event_lifetime,
        "structural_markers": structural_markers,
        "guards": guards,
        "storage_decision": {
            "new_four_bank_instruction_arrays": "NOT_SELECTED",
            "new_call_result_array": "NOT_SELECTED",
            "new_terminator_condition_array": "NOT_SELECTED_PACKED_BLOCK_RECORD_OWNS_TERMINATOR_VALUES",
            "event_banks_as_instruction_storage": "CANDIDATE_AFTER_PROVEN_OVERWRITE_FRONTIER_AND_REQUIRES_NATIVE_IR_V2_VERIFIER",
            "value_banks_as_unified_value_storage": "CANDIDATE_REQUIRES_NAMESPACE_REBUILD_AND_LITERAL_PAYLOAD_QUALIFICATION",
            "block_storage": "SEE_PACKED_730_BLOCK_CAPACITY_AUDIT",
        },
        "qualification_rule": "Static PASS only proves layout/encoding/lifetime feasibility. Native Stage1 candidate execution plus an IR-v2 verifier must prove semantics before source promotion.",
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
    print(f"INSTRUCTION_RECORD_MAX={result['instruction_record']['max_encoded']}")
    print(f"INSTRUCTION_BLOCK_CAPACITY={result['instruction_record']['block_capacity']}")
    print(f"CALL_TABLE_LAYOUT={result['guards']['call_table_layout']}")
    print(f"EVENT_OVERWRITE_FRONTIER={result['event_bank_lifetime']['frontier']}")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] == "STATIC_STORAGE_AUDIT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
