"""Static contract audit for the future Stage1 IR-v2 local-metadata lane.

This tool does not transform the compiler. It proves only that a bounded packed
local record can preserve the information the emitter will actually need.
Native qualification and an exact candidate source-delta preflight are mandatory
before local metadata may be added to the canonical compiler.

Important correction: canonical Stage1 uses both scalar locals and fixed arrays.
The IR must therefore retain storage kind and fixed-array extent. A physical
stack/frame offset is deliberately *not* frozen in semantic IR; the emitter can
lay out storage deterministically from local ordinal + kind + extent.
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
FUNCTION_DOMAIN = 65          # none=0; function id 0..63 => 1..64
NAME_DOMAIN = 366             # none=0; Stage1 identifier hash 0..364 => 1..365
TYPE_DOMAIN = 366             # none=0; type identity 0..364 => 1..365
MUTABILITY_DOMAIN = 2         # 0 reserved/immutable, 1 mutable
STORAGE_KIND_DOMAIN = 3       # 0 none, 1 scalar, 2 fixed array
LOCAL_ORDINAL_DOMAIN = 366    # none=0; per-function ordinal 0..364 => 1..365
EXTENT_DOMAIN = 1461          # none=0; extent 1..1460 is encoded directly
VALUE_ID_DOMAIN = 1461        # none=0; semantic value id 0..1459 => 1..1460
MAX_LOCAL_RECORDS = 365
FIXED_PARAMETER_VALUE_DOMAIN = 64

_ARRAY_DECL = re.compile(
    r"(?m)^\s*mut\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<type>i64|tryte|trit)\[(?P<size>\d+)\]\s*=\s*\["
)
_SCALAR_DECL = re.compile(
    r"(?m)^\s*mut\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<type>i64|tryte|trit)\s*="
)


def local_record_limit() -> int:
    return (
        FUNCTION_DOMAIN
        * NAME_DOMAIN
        * TYPE_DOMAIN
        * MUTABILITY_DOMAIN
        * STORAGE_KIND_DOMAIN
        * LOCAL_ORDINAL_DOMAIN
        * EXTENT_DOMAIN
        * VALUE_ID_DOMAIN
        - 1
    )


def pack_local(
    owner_encoded: int,
    name_encoded: int,
    type_encoded: int,
    mutability: int,
    storage_kind: int,
    local_ordinal_encoded: int,
    extent_encoded: int,
    value_id_encoded: int,
) -> int:
    fields = (
        (owner_encoded, FUNCTION_DOMAIN, "owner"),
        (name_encoded, NAME_DOMAIN, "name"),
        (type_encoded, TYPE_DOMAIN, "type"),
        (mutability, MUTABILITY_DOMAIN, "mutability"),
        (storage_kind, STORAGE_KIND_DOMAIN, "storage_kind"),
        (local_ordinal_encoded, LOCAL_ORDINAL_DOMAIN, "local_ordinal"),
        (extent_encoded, EXTENT_DOMAIN, "extent"),
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
        (storage_kind, STORAGE_KIND_DOMAIN),
        (local_ordinal_encoded, LOCAL_ORDINAL_DOMAIN),
        (extent_encoded, EXTENT_DOMAIN),
        (value_id_encoded, VALUE_ID_DOMAIN),
    ):
        record = record * radix + value
    if record > SIGNED_I64_MAX:
        raise ValueError("packed local exceeds signed i64")
    return record


def unpack_local(record: int) -> tuple[int, int, int, int, int, int, int, int]:
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
        EXTENT_DOMAIN,
        LOCAL_ORDINAL_DOMAIN,
        STORAGE_KIND_DOMAIN,
        MUTABILITY_DOMAIN,
        TYPE_DOMAIN,
        NAME_DOMAIN,
    ):
        values.append(remainder % radix)
        remainder //= radix
    value_id, extent, local_ordinal, storage_kind, mutability, type_id, name = values
    owner = remainder
    return owner, name, type_id, mutability, storage_kind, local_ordinal, extent, value_id


def audit(source: str) -> dict[str, object]:
    arrays = list(_ARRAY_DECL.finditer(source))
    scalars = list(_SCALAR_DECL.finditer(source))
    declarations = {
        match.group("name"): (match.group("type"), int(match.group("size")))
        for match in arrays
    }

    # The current source owns eight explicit local metadata lanes.  They are
    # the intended shape-preserving representation, not a legacy packed lane.
    # Only the old aggregate ``ir_local_records`` name is a silent-reuse risk.
    existing_local_arrays = sorted(
        name for name in declarations if name == "ir_local_records"
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

    observed_extents = [int(match.group("size")) for match in arrays]
    maximum_extent = max(observed_extents, default=1)

    boundary = (
        FUNCTION_DOMAIN - 1,
        NAME_DOMAIN - 1,
        TYPE_DOMAIN - 1,
        MUTABILITY_DOMAIN - 1,
        STORAGE_KIND_DOMAIN - 1,
        LOCAL_ORDINAL_DOMAIN - 1,
        EXTENT_DOMAIN - 1,
        VALUE_ID_DOMAIN - 1,
    )
    round_trip = unpack_local(pack_local(*boundary)) == boundary
    maximum = local_record_limit()

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
        "observed_fixed_array_extents_fit_record_domain": maximum_extent < EXTENT_DOMAIN,
        "fixed_parameter_domain_leaves_room_for_locals": FIXED_PARAMETER_VALUE_DOMAIN < VALUE_ID_DOMAIN - 1,
    }

    return {
        "schema": "s3.selfhost.codegen-ir-v2-local-metadata-design-audit.v2",
        "status": (
            "STATIC_LOCAL_METADATA_DESIGN_PASS"
            if all(guards.values())
            else "STATIC_LOCAL_METADATA_DESIGN_FAIL"
        ),
        "native_evidence": False,
        "canonical_source_mutated": False,
        "observed": {
            "existing_local_record_arrays": existing_local_arrays,
            "local_count_signal": "Stage1 identifier hash 87 (literal mut; collision audit still required)",
            "local_event_opcode": 6,
            "scalar_declaration_lines": len(scalars),
            "fixed_array_declaration_lines": len(arrays),
            "maximum_fixed_array_extent": maximum_extent,
            "native_local_count_not_assumed_from_static_source": True,
        },
        "candidate_record": {
            "maximum_physical_records_without_banking": MAX_LOCAL_RECORDS,
            "capacity_selection": "DEFER_TO_NATIVE_PARAMETER_REPORT_PLUS_EXACT_CANDIDATE_LEXICAL_COUNT",
            "physical_strategy": "ONE_BOUNDED_I64_LANE_IF_SELECTED_CAPACITY_LE_365",
            "fields": [
                "owner_function_id",
                "name_identity",
                "type_id",
                "mutability",
                "storage_kind",
                "local_ordinal",
                "fixed_extent",
                "semantic_value_id",
            ],
            "storage_kinds": {"1": "SCALAR", "2": "FIXED_ARRAY"},
            "max_encoded": maximum,
            "signed_i64_max": SIGNED_I64_MAX,
            "fits_signed_i64": maximum <= SIGNED_I64_MAX,
            "parameter_value_id_domain_reserved": [0, FIXED_PARAMETER_VALUE_DOMAIN],
            "local_value_id_rule": "64 + global_local_record_index",
        },
        "parser_strategy": {
            "state_machine": [
                "SEEN_MUT",
                "CAPTURE_LOCAL_NAME",
                "REQUIRE_COLON",
                "CAPTURE_AND_VALIDATE_TYPE",
                "IF_EQUAL_FINALIZE_SCALAR_EXTENT_1",
                "IF_LEFT_BRACKET_CAPTURE_INTEGER_EXTENT_REQUIRE_RIGHT_BRACKET_FINALIZE_ARRAY",
                "WRITE_PACKED_LOCAL_RECORD",
            ],
            "owner": "current_function; fail closed when current_function < 0",
            "local_ordinal": "scalar counter reset when current_function changes; physical frame/static offset is emitter-owned",
            "value_id": "64 + global local record index",
            "mutability": 1,
            "array_shape": "storage_kind=2 plus fixed_extent; do not erase [N] into scalar type",
        },
        "required_candidate_preflight": {
            "native_parameter_report_pass": True,
            "native_and_stage1_lexical_local_count_consistency": True,
            "identifier_hash_87_collision_check": True,
            "selected_capacity_at_least_candidate_local_count": True,
            "exact_numeric_token_delta": True,
            "exact_match_token_delta": True,
            "exact_while_token_delta": True,
            "exact_mut_token_delta": True,
            "exact_function_signature_delta": True,
            "exact_fixed_array_extent_inventory": True,
            "project_against_native_parameter_report": True,
            "must_not_use_static_zero_count_as_native_headroom": True,
        },
        "guards": guards,
        "qualification_rule": (
            "Representation feasibility is not source-promotion evidence. The concrete local transform must consume a PASS native parameter report, prove Stage1-token local-count consistency, select bounded capacity from the exact candidate source, project its exact lexical/control delta, and then pass real Linux x86-64 Stage1 self-source verification."
        ),
        "local_transform": "PREPARATION_ALLOWED_REPORT_GATED",
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
    print(f"MAX_FIXED_ARRAY_EXTENT={result['observed']['maximum_fixed_array_extent']}")
    print(f"EXISTING_LOCAL_RECORD_ARRAYS={len(result['observed']['existing_local_record_arrays'])}")
    print("LOCAL_TRANSFORM=PREPARATION_ALLOWED_REPORT_GATED")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] == "STATIC_LOCAL_METADATA_DESIGN_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
