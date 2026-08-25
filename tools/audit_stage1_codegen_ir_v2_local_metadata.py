"""Static contract audit for the future Stage1 IR-v2 local-metadata lane.

This tool does not transform the compiler. It proves only that the bounded
metadata representation and parser-state strategy are feasible against the
current Stage1 source. Native qualification and an exact candidate control-delta
preflight are still mandatory before local metadata may be added to the source.
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
    "codegen-ir-v2-local-metadata-design-audit.json"
)

SIGNED_I64_MAX = 2**63 - 1
FUNCTION_DOMAIN = 65          # none=0; function id N => N+1, N in 0..63
NAME_DOMAIN = 366             # none=0; lexer identity 0..364 => 1..365
TYPE_DOMAIN = 366             # none=0; type identity 0..364 => 1..365
MUTABILITY_DOMAIN = 2         # 0 immutable/reserved, 1 mutable local
FRAME_SLOT_DOMAIN = 65        # none=0; frame slot 0..63 => 1..64
VALUE_ID_DOMAIN = 1461        # none=0; semantic value id 0..1459 => 1..1460
LOCAL_CAPACITY = 64
FIXED_PARAMETER_VALUE_DOMAIN = 64

_ARRAY_DECL = re.compile(
    r"(?m)^\s*mut\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<type>i64|tryte|trit)\[(?P<size>\d+)\]\s*=\s*\["
)


def local_record_limit() -> int:
    return (
        FUNCTION_DOMAIN
        * NAME_DOMAIN
        * TYPE_DOMAIN
        * MUTABILITY_DOMAIN
        * FRAME_SLOT_DOMAIN
        * VALUE_ID_DOMAIN
        - 1
    )


def pack_local(
    owner_encoded: int,
    name_encoded: int,
    type_encoded: int,
    mutability: int,
    frame_slot_encoded: int,
    value_id_encoded: int,
) -> int:
    fields = (
        (owner_encoded, FUNCTION_DOMAIN, "owner"),
        (name_encoded, NAME_DOMAIN, "name"),
        (type_encoded, TYPE_DOMAIN, "type"),
        (mutability, MUTABILITY_DOMAIN, "mutability"),
        (frame_slot_encoded, FRAME_SLOT_DOMAIN, "frame_slot"),
        (value_id_encoded, VALUE_ID_DOMAIN, "value_id"),
    )
    for value, radix, label in fields:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= radix:
            raise ValueError(f"{label} outside packed-local domain")
    record = owner_encoded
    for value, radix in (
        (name_encoded, NAME_DOMAIN),
        (type_encoded, TYPE_DOMAIN),
        (mutability, MUTABILITY_DOMAIN),
        (frame_slot_encoded, FRAME_SLOT_DOMAIN),
        (value_id_encoded, VALUE_ID_DOMAIN),
    ):
        record = record * radix + value
    if record > SIGNED_I64_MAX:
        raise ValueError("packed local exceeds signed i64")
    return record


def unpack_local(record: int) -> tuple[int, int, int, int, int, int]:
    if (
        not isinstance(record, int)
        or isinstance(record, bool)
        or record < 0
        or record > local_record_limit()
    ):
        raise ValueError("packed local outside domain")
    values: list[int] = []
    remainder = record
    for radix in (
        VALUE_ID_DOMAIN,
        FRAME_SLOT_DOMAIN,
        MUTABILITY_DOMAIN,
        TYPE_DOMAIN,
        NAME_DOMAIN,
    ):
        values.append(remainder % radix)
        remainder //= radix
    value_id, frame_slot, mutability, type_id, name = values
    owner = remainder
    return owner, name, type_id, mutability, frame_slot, value_id


def audit(source: str) -> dict[str, object]:
    declarations = {
        match.group("name"): (match.group("type"), int(match.group("size")))
        for match in _ARRAY_DECL.finditer(source)
    }

    existing_local_arrays = sorted(
        name for name in declarations
        if name.startswith("ir_local_") or name == "ir_local_records"
    )
    has_counter = "mut ir_local_record_count: i64 = 0" in source
    has_local_count = "mut local_count: i64 = 0" in source
    mut_keyword_capture = (
        "match value == 87:" in source
        and "local_count += 1" in source
        and "ir_ast_event_opcode = 6" in source
    )
    has_current_function = "mut current_function: i64 = -1" in source
    function_activation_marker = "current_function = function_count" in source
    foreign_deactivation_marker = "current_function = -1" in source

    # The future candidate may track a single per-current-function frame slot
    # scalar because functions are parsed sequentially. It does not need a new
    # 64-entry per-function count array merely to assign deterministic slots.
    frame_strategy = {
        "strategy": "SCALAR_CURRENT_FUNCTION_FRAME_SLOT_RESET_ON_FUNCTION_ACTIVATION",
        "requires_new_large_array": False,
        "required_reset_anchor": function_activation_marker,
        "foreign_functions_deactivate_current_function": foreign_deactivation_marker,
    }

    boundary = (
        FUNCTION_DOMAIN - 1,
        NAME_DOMAIN - 1,
        TYPE_DOMAIN - 1,
        MUTABILITY_DOMAIN - 1,
        FRAME_SLOT_DOMAIN - 1,
        VALUE_ID_DOMAIN - 1,
    )
    round_trip = unpack_local(pack_local(*boundary)) == boundary
    maximum = local_record_limit()

    planned_value_range = {
        "start": FIXED_PARAMETER_VALUE_DOMAIN,
        "end_exclusive": FIXED_PARAMETER_VALUE_DOMAIN + LOCAL_CAPACITY,
    }

    guards = {
        "local_counter_exists": has_local_count,
        "ir_local_record_counter_exists": has_counter,
        "mut_keyword_is_current_local_signal": mut_keyword_capture,
        "current_function_state_exists": has_current_function,
        "function_activation_anchor_exists": function_activation_marker,
        "foreign_function_deactivation_anchor_exists": foreign_deactivation_marker,
        "no_existing_local_record_array_to_silently_reinterpret": not existing_local_arrays,
        "packed_local_record_fits_signed_i64": maximum <= SIGNED_I64_MAX,
        "packed_local_record_round_trip": round_trip,
        "planned_local_value_range_fits_semantic_value_domain": (
            planned_value_range["end_exclusive"] <= VALUE_ID_DOMAIN - 1
        ),
    }

    return {
        "schema": "s3.selfhost.codegen-ir-v2-local-metadata-design-audit.v1",
        "status": (
            "STATIC_LOCAL_METADATA_DESIGN_PASS"
            if all(guards.values())
            else "STATIC_LOCAL_METADATA_DESIGN_FAIL"
        ),
        "native_evidence": False,
        "canonical_source_mutated": False,
        "observed": {
            "existing_local_record_arrays": existing_local_arrays,
            "local_count_signal": "keyword identity 87 (mut)",
            "local_event_opcode": 6,
            "current_local_count_only": True,
        },
        "candidate_record": {
            "capacity": LOCAL_CAPACITY,
            "physical_strategy": "ONE_PACKED_I64_64_LANE_IF_EXACT_CANDIDATE_PREFLIGHT_FITS",
            "fields": [
                "owner_function_id",
                "name_identity",
                "type_id",
                "mutability",
                "frame_slot",
                "semantic_value_id",
            ],
            "max_encoded": maximum,
            "signed_i64_max": SIGNED_I64_MAX,
            "fits_signed_i64": maximum <= SIGNED_I64_MAX,
            "planned_value_id_range": planned_value_range,
            "parameter_value_id_domain_reserved": [0, FIXED_PARAMETER_VALUE_DOMAIN],
        },
        "parser_strategy": {
            "state_machine": [
                "SEEN_MUT",
                "CAPTURE_LOCAL_NAME",
                "REQUIRE_COLON",
                "CAPTURE_AND_VALIDATE_TYPE",
                "WRITE_PACKED_LOCAL_RECORD",
            ],
            "owner": "current_function; reject/fail-closed when current_function < 0",
            "frame_slot": frame_strategy,
            "value_id": "64 + global_local_index for the bounded 64-local bootstrap lane",
            "mutability": 1,
        },
        "required_candidate_preflight": {
            "exact_numeric_token_delta": True,
            "exact_match_line_delta": True,
            "exact_while_line_delta": True,
            "exact_mut_declaration_delta": True,
            "exact_function_signature_delta": True,
            "project_against_native_parameter_report": True,
            "must_not_use_static_zero_count_as_native_headroom": True,
        },
        "guards": guards,
        "qualification_rule": (
            "This audit proves representation/parser-state feasibility only. Do not create or promote the local lane until a concrete in-memory transform has an exact source-delta preflight against the native parameter report and then passes a real Linux x86-64 Stage1 self-source verifier gate."
        ),
        "local_transform": "NOT_IMPLEMENTED",
        "unified_value_namespace": "NOT_STARTED",
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
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
    print(f"PACKED_LOCAL_MAX={result['candidate_record']['max_encoded']}")
    print(f"EXISTING_LOCAL_RECORD_ARRAYS={len(result['observed']['existing_local_record_arrays'])}")
    print("LOCAL_TRANSFORM=NOT_IMPLEMENTED")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] == "STATIC_LOCAL_METADATA_DESIGN_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
