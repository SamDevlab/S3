"""Static audit for Stage1 IR-v2 physical-storage reuse.

This audit intentionally does not qualify compiler behavior. It checks that the
canonical Stage1 source still exposes the bounded physical banks assumed by the
IR-v2 storage-reuse plan, proves the proposed mixed-radix encodings fit in a
signed i64, verifies the existing call-table layout, and identifies a safe
lifetime frontier after which the legacy event banks are no longer read.

A static PASS is only permission to attempt a native candidate. Native Stage1
qualification remains mandatory for semantic PASS.
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
    "codegen-ir-v2-storage-reuse-audit.json"
)

SIGNED_I64_MAX = 2**63 - 1
EVENT_BANK_SIZE = 365
EVENT_BANK_COUNT = 4
VALUE_BANK_SIZE = 365
VALUE_BANK_COUNT = 4
CALL_BANK_SIZE = 365
CALL_BANK_COUNT = 2
CALL_ARG_BANK_SIZES = (365, 365, 16)
BLOCK_CAPACITY = 365
VALUE_ID_RADIX = 1461  # none=0; value ids 0..1459 encode to 1..1460
OWNER_RADIX = 65       # none=0; function ids 0..63 encode to 1..64
BLOCK_RADIX = 366      # none=0; block ids 0..364 encode to 1..365
OPCODE_RADIX = 64
TERMINATOR_KIND_RADIX = 8

_ARRAY_DECL = re.compile(
    r"(?m)^\s*mut\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<type>i64|tryte|trit)\[(?P<size>\d+)\]\s*=\s*\["
)
_EVENT_BANK_REF = re.compile(r"\bir_ast_event_records_[0-3]\b")


def instruction_record_limit() -> int:
    return (
        OWNER_RADIX
        * BLOCK_RADIX
        * OPCODE_RADIX
        * VALUE_ID_RADIX**4
        - 1
    )


def terminator_record_limit() -> int:
    return TERMINATOR_KIND_RADIX * VALUE_ID_RADIX * VALUE_ID_RADIX - 1


def pack_instruction(
    owner_encoded: int,
    block_encoded: int,
    opcode: int,
    operand_a_encoded: int,
    operand_b_encoded: int,
    result_encoded: int,
    aux_encoded: int,
) -> int:
    limits = (
        (owner_encoded, OWNER_RADIX, "owner"),
        (block_encoded, BLOCK_RADIX, "block"),
        (opcode, OPCODE_RADIX, "opcode"),
        (operand_a_encoded, VALUE_ID_RADIX, "operand_a"),
        (operand_b_encoded, VALUE_ID_RADIX, "operand_b"),
        (result_encoded, VALUE_ID_RADIX, "result"),
        (aux_encoded, VALUE_ID_RADIX, "aux"),
    )
    for value, radix, label in limits:
        if not isinstance(value, int) or value < 0 or value >= radix:
            raise ValueError(f"{label} outside mixed-radix domain")
    record = owner_encoded
    for value, radix in (
        (block_encoded, BLOCK_RADIX),
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


def unpack_instruction(record: int) -> tuple[int, int, int, int, int, int, int]:
    if not isinstance(record, int) or record < 0 or record > instruction_record_limit():
        raise ValueError("instruction record outside mixed-radix domain")
    values: list[int] = []
    remainder = record
    for radix in (
        VALUE_ID_RADIX,
        VALUE_ID_RADIX,
        VALUE_ID_RADIX,
        VALUE_ID_RADIX,
        OPCODE_RADIX,
        BLOCK_RADIX,
    ):
        values.append(remainder % radix)
        remainder //= radix
    aux, result, operand_b, operand_a, opcode, block = values
    owner = remainder
    return owner, block, opcode, operand_a, operand_b, result, aux


def pack_terminator(kind: int, condition_encoded: int, return_encoded: int) -> int:
    for value, radix, label in (
        (kind, TERMINATOR_KIND_RADIX, "kind"),
        (condition_encoded, VALUE_ID_RADIX, "condition"),
        (return_encoded, VALUE_ID_RADIX, "return"),
    ):
        if not isinstance(value, int) or value < 0 or value >= radix:
            raise ValueError(f"{label} outside terminator mixed-radix domain")
    return (kind * VALUE_ID_RADIX + condition_encoded) * VALUE_ID_RADIX + return_encoded


def unpack_terminator(record: int) -> tuple[int, int, int]:
    if not isinstance(record, int) or record < 0 or record > terminator_record_limit():
        raise ValueError("terminator record outside mixed-radix domain")
    return_encoded = record % VALUE_ID_RADIX
    remainder = record // VALUE_ID_RADIX
    condition_encoded = remainder % VALUE_ID_RADIX
    kind = remainder // VALUE_ID_RADIX
    return kind, condition_encoded, return_encoded


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


def _call_table_specs(
    declarations: dict[str, tuple[str, int]],
) -> dict[str, tuple[str, int] | None]:
    fields: dict[str, tuple[str, int]] = {
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
    return {name: declarations.get(name) for name in fields}


def _call_table_layout_pass(
    declarations: dict[str, tuple[str, int]],
) -> bool:
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
    return all(declarations.get(name) == spec for name, spec in expected.items())


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
    return {
        "writer_anchor_found": writer >= 0,
        "control_scan_anchor_found": control_scan >= 0,
        "legacy_event_verifier_anchor_found": legacy_event_verifier >= 0,
        "post_event_verifier_anchor_found": post_event_verifier >= 0,
        "anchors_ordered": ordered,
        "event_bank_refs_after_frontier": len(refs_after_frontier),
        "safe_overwrite_frontier_proven": bool(ordered and not refs_after_frontier),
        "frontier": (
            "AFTER_LEGACY_EVENT_VERIFIER_BEFORE_REMAINING_VERIFIER_AND_PIPELINE_DECISION"
            if ordered and not refs_after_frontier
            else "NOT_PROVEN"
        ),
        "required_v2_sequence": [
            "preserve legacy event records through control lowering",
            "preserve legacy event records through legacy event verifier",
            "rewrite event banks in place as IR-v2 instructions only after the proven frontier",
            "run a new IR-v2 verifier over rewritten instruction/value/block/call records",
            "allow general emitter only after IR-v2 verifier PASS",
        ],
    }


def audit(source: str) -> dict[str, object]:
    declarations = _declarations(source)
    event_banks = _numbered_banks(declarations, "ir_ast_event_records_")
    value_banks = _numbered_banks(declarations, "ir_value_records_")
    instruction_banks = _numbered_banks(declarations, "ir_instruction_records_")

    call_arg_specs = {
        name: declarations.get(name)
        for name in ("ir_call_args_0", "ir_call_args_1", "ir_call_args_2")
    }
    call_table_specs = _call_table_specs(declarations)
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
    call_table_layout_pass = _call_table_layout_pass(declarations)
    block_layout_pass = all(
        spec == ("i64", BLOCK_CAPACITY) for spec in block_fields.values()
    )

    instruction_limit = instruction_record_limit()
    terminator_limit = terminator_record_limit()
    boundary_record = pack_instruction(
        OWNER_RADIX - 1,
        BLOCK_RADIX - 1,
        OPCODE_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )
    round_trip_pass = unpack_instruction(boundary_record) == (
        OWNER_RADIX - 1,
        BLOCK_RADIX - 1,
        OPCODE_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )
    terminator_boundary = pack_terminator(
        TERMINATOR_KIND_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )
    terminator_round_trip = unpack_terminator(terminator_boundary) == (
        TERMINATOR_KIND_RADIX - 1,
        VALUE_ID_RADIX - 1,
        VALUE_ID_RADIX - 1,
    )

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
        "block_targets_exist": all(spec is not None for spec in block_fields.values()),
    }

    guards = {
        "event_bank_layout": event_layout_pass,
        "value_bank_layout": value_layout_pass,
        "call_table_layout": call_table_layout_pass,
        "call_argument_layout": call_arg_layout_pass,
        "block_layout": block_layout_pass,
        "instruction_record_fits_signed_i64": instruction_limit <= SIGNED_I64_MAX,
        "instruction_record_round_trip": round_trip_pass,
        "terminator_record_fits_signed_i64": terminator_limit <= SIGNED_I64_MAX,
        "terminator_record_round_trip": terminator_round_trip,
        "event_instruction_cardinality_marker": structural_markers[
            "event_count_drives_instruction_count"
        ],
        "event_bank_safe_overwrite_frontier": bool(
            event_lifetime["safe_overwrite_frontier_proven"]
        ),
    }

    return {
        "schema": "s3.selfhost.codegen-ir-v2-storage-reuse-audit.v2",
        "status": "STATIC_STORAGE_AUDIT_PASS" if all(guards.values()) else "STATIC_STORAGE_AUDIT_FAIL",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "declarations": {
            "event_banks": {str(k): list(v) for k, v in sorted(event_banks.items())},
            "value_banks": {str(k): list(v) for k, v in sorted(value_banks.items())},
            "instruction_banks_observed": {
                str(k): list(v) for k, v in sorted(instruction_banks.items())
            },
            "call_table": {
                name: list(spec) if spec is not None else None
                for name, spec in call_table_specs.items()
            },
            "call_argument_banks": {
                name: list(spec) if spec is not None else None
                for name, spec in call_arg_specs.items()
            },
            "block_fields": {
                name: list(spec) if spec is not None else None
                for name, spec in block_fields.items()
            },
        },
        "instruction_record": {
            "max_encoded": instruction_limit,
            "signed_i64_max": SIGNED_I64_MAX,
            "headroom_to_i64_max": SIGNED_I64_MAX - instruction_limit,
            "radices": {
                "owner": OWNER_RADIX,
                "block": BLOCK_RADIX,
                "opcode": OPCODE_RADIX,
                "operand_a": VALUE_ID_RADIX,
                "operand_b": VALUE_ID_RADIX,
                "result": VALUE_ID_RADIX,
                "aux": VALUE_ID_RADIX,
            },
            "aux_constraint": "ID/reference only; arbitrary raw i64 literal payload is not supported by this record",
        },
        "terminator_record": {
            "max_encoded": terminator_limit,
            "signed_i64_max": SIGNED_I64_MAX,
            "radices": {
                "kind": TERMINATOR_KIND_RADIX,
                "condition": VALUE_ID_RADIX,
                "return": VALUE_ID_RADIX,
            },
            "targets_reused_from_existing_block_arrays": True,
        },
        "event_bank_lifetime": event_lifetime,
        "structural_markers": structural_markers,
        "guards": guards,
        "storage_decision": {
            "new_four_bank_instruction_arrays": "NOT_SELECTED",
            "new_call_result_array": "NOT_SELECTED",
            "new_terminator_condition_array": "NOT_SELECTED",
            "event_banks_as_instruction_storage": "CANDIDATE_AFTER_PROVEN_OVERWRITE_FRONTIER_AND_REQUIRES_NATIVE_IR_V2_VERIFIER",
            "value_banks_as_unified_value_storage": "CANDIDATE_REQUIRES_NAMESPACE_REBUILD_AND_LITERAL_PAYLOAD_QUALIFICATION",
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
    print(f"TERMINATOR_RECORD_MAX={result['terminator_record']['max_encoded']}")
    print(f"CALL_TABLE_LAYOUT={result['guards']['call_table_layout']}")
    print(f"EVENT_OVERWRITE_FRONTIER={result['event_bank_lifetime']['frontier']}")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] == "STATIC_STORAGE_AUDIT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
