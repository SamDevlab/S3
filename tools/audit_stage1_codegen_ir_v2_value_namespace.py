"""Static design audit for the Stage1 IR-v2 semantic value namespace.

This is not a source transform and not native evidence. It validates the packed
header mathematics, the current direct 68-slot parameter metadata capacity,
the dynamic semantic-ID layout, current physical value-bank shape, and the
constant representation rules that a later report-gated value namespace
candidate must obey after a native local PASS.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tools.preflight_stage1_codegen_ir_v2_locals import stage1_tokens


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-value-namespace-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-value-namespace-design-audit.json"
)

SIGNED_I64_MAX = 2**63 - 1
KIND_DOMAIN = 8
OWNER_DOMAIN = 65
TYPE_DOMAIN = 366
PAYLOAD_DOMAIN = 1461
VALUE_CAPACITY = 1460
PARAMETER_CAPACITY = 68
INLINE_LITERAL_MIN = -730
INLINE_LITERAL_MAX = 730

_ARRAY_DECL = re.compile(
    r"(?m)^\s*mut\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<type>i64|tryte|trit)\[(?P<size>\d+)\]\s*=\s*\["
)


def header_limit() -> int:
    return KIND_DOMAIN * OWNER_DOMAIN * TYPE_DOMAIN * PAYLOAD_DOMAIN - 1


def pack_header(kind: int, owner: int, type_id: int, payload: int) -> int:
    fields = (
        (kind, KIND_DOMAIN, "kind"),
        (owner, OWNER_DOMAIN, "owner"),
        (type_id, TYPE_DOMAIN, "type"),
        (payload, PAYLOAD_DOMAIN, "payload"),
    )
    for value, radix, label in fields:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= radix:
            raise ValueError(f"{label} outside packed-value-header domain")
    record = kind
    for value, radix in ((owner, OWNER_DOMAIN), (type_id, TYPE_DOMAIN), (payload, PAYLOAD_DOMAIN)):
        record = record * radix + value
    if record > SIGNED_I64_MAX:
        raise ValueError("packed value header exceeds signed i64")
    return record


def unpack_header(record: int) -> tuple[int, int, int, int]:
    if not isinstance(record, int) or isinstance(record, bool) or record < 0 or record > header_limit():
        raise ValueError("packed value header outside domain")
    payload = record % PAYLOAD_DOMAIN
    remainder = record // PAYLOAD_DOMAIN
    type_id = remainder % TYPE_DOMAIN
    remainder //= TYPE_DOMAIN
    owner = remainder % OWNER_DOMAIN
    kind = remainder // OWNER_DOMAIN
    return kind, owner, type_id, payload


def encode_inline_literal(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("inline literal must be integer")
    if value < INLINE_LITERAL_MIN or value > INLINE_LITERAL_MAX:
        raise ValueError("literal requires wide representation")
    return value - INLINE_LITERAL_MIN


def decode_inline_literal(encoded: int) -> int:
    if not isinstance(encoded, int) or isinstance(encoded, bool) or encoded < 0 or encoded >= PAYLOAD_DOMAIN:
        raise ValueError("inline literal payload outside domain")
    return encoded + INLINE_LITERAL_MIN


def _value_banks(source: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for match in _ARRAY_DECL.finditer(source):
        name = match.group("name")
        if name.startswith("ir_value_records_"):
            result.append({
                "name": name,
                "element_type": match.group("type"),
                "size": int(match.group("size")),
            })
    return result


def _parameter_lanes(source: str) -> list[dict[str, object]]:
    expected = {
        "ir_parameter_owner",
        "ir_parameter_name",
        "ir_parameter_ordinal",
        "ir_parameter_type",
    }
    result: list[dict[str, object]] = []
    for match in _ARRAY_DECL.finditer(source):
        name = match.group("name")
        if name in expected:
            result.append({
                "name": name,
                "element_type": match.group("type"),
                "size": int(match.group("size")),
            })
    return result


def _numeric_inventory(source: str) -> dict[str, object]:
    numeric = [token.value for token in stage1_tokens(source) if token.kind == 2]
    unique = sorted(set(numeric))
    inline_unique = [value for value in unique if INLINE_LITERAL_MIN <= value <= INLINE_LITERAL_MAX]
    wide_unique = [value for value in unique if value < INLINE_LITERAL_MIN or value > INLINE_LITERAL_MAX]
    return {
        "lexical_numeric_occurrences": len(numeric),
        "unique_untyped_numeric_values": len(unique),
        "unique_inline_range_values": len(inline_unique),
        "unique_wide_values": len(wide_unique),
        "wide_values": wide_unique,
        "note": "Untyped uniqueness is only a lower-bound planning signal. Exact semantic constant inventory must be keyed by resolved type plus literal value after native local PASS."
    }


def audit(source: str, contract: dict[str, object]) -> dict[str, object]:
    banks = _value_banks(source)
    parameter_lanes = _parameter_lanes(source)
    total_slots = sum(int(bank["size"]) for bank in banks)
    boundary = (KIND_DOMAIN - 1, OWNER_DOMAIN - 1, TYPE_DOMAIN - 1, PAYLOAD_DOMAIN - 1)
    round_trip = unpack_header(pack_header(*boundary)) == boundary
    numeric = _numeric_inventory(source)

    contract_header = contract.get("packed_header")
    physical = contract.get("physical_storage")
    constants = contract.get("constant_representation")
    layout = contract.get("semantic_id_layout")
    if not isinstance(contract_header, dict) or not isinstance(physical, dict) or not isinstance(constants, dict) or not isinstance(layout, dict):
        raise ValueError("value namespace contract is missing required sections")

    parameter_names = {str(lane["name"]) for lane in parameter_lanes}
    guards = {
        "four_legacy_value_banks_present": len(banks) == 4,
        "legacy_value_capacity_is_1460": total_slots == VALUE_CAPACITY,
        "all_legacy_value_banks_are_i64_365": all(
            bank["element_type"] == "i64" and bank["size"] == 365 for bank in banks
        ),
        "four_direct_parameter_lanes_present": parameter_names == {
            "ir_parameter_owner",
            "ir_parameter_name",
            "ir_parameter_ordinal",
            "ir_parameter_type",
        },
        "direct_parameter_capacity_is_68": len(parameter_lanes) == 4 and all(
            lane["element_type"] == "i64" and lane["size"] == PARAMETER_CAPACITY
            for lane in parameter_lanes
        ),
        "header_limit_matches_contract": contract_header.get("maximum_encoded") == header_limit(),
        "header_fits_signed_i64": header_limit() <= SIGNED_I64_MAX,
        "header_boundary_round_trip": round_trip,
        "physical_capacity_matches_contract": physical.get("physical_slots") == VALUE_CAPACITY,
        "parameter_capacity_bound_matches_contract": layout.get("parameter_capacity_bound") == PARAMETER_CAPACITY,
        "parameter_domain_is_dynamic": layout.get("parameter_domain") == "[0,parameter_count)",
        "local_domain_starts_at_parameter_count": layout.get("local_domain_start") == "parameter_count",
        "dynamic_start_follows_locals": layout.get("dynamic_start") == "parameter_count + local_record_count",
        "historical_fixed_64_reservation_disabled": layout.get("fixed_64_parameter_reservation") is False,
        "inline_min_matches_contract": constants.get("inline_range", {}).get("min") == INLINE_LITERAL_MIN,
        "inline_max_matches_contract": constants.get("inline_range", {}).get("max") == INLINE_LITERAL_MAX,
        "wide_extension_is_not_semantic_id": constants.get("wide_literal", {}).get("extension_slot_is_semantic_value_id") is False,
        "legacy_silent_reinterpretation_forbidden": physical.get("silent_reinterpretation_allowed") is False,
    }

    return {
        "schema": "s3.selfhost.codegen-ir-v2-value-namespace-design-audit.v2",
        "status": (
            "STATIC_VALUE_NAMESPACE_DESIGN_PASS"
            if all(guards.values())
            else "STATIC_VALUE_NAMESPACE_DESIGN_FAIL"
        ),
        "native_evidence": False,
        "canonical_source_mutated": False,
        "legacy_storage": {
            "banks": banks,
            "total_slots": total_slots,
            "contents": "STRUCTURAL_NUMERIC_TOKEN_RECORDS_NOT_SEMANTIC_VALUES"
        },
        "parameter_metadata": {
            "lanes": parameter_lanes,
            "capacity_bound": PARAMETER_CAPACITY,
            "semantic_id_domain": "[0,parameter_count)",
            "fixed_64_reservation": False,
        },
        "packed_header": {
            "maximum_encoded": header_limit(),
            "signed_i64_max": SIGNED_I64_MAX,
            "boundary_round_trip": round_trip,
            "fields": ["kind", "owner", "type_id", "payload_or_reference"]
        },
        "numeric_inventory": numeric,
        "namespace": {
            "parameter_domain": {"start": 0, "end_exclusive": "parameter_count"},
            "local_start": "parameter_count",
            "local_id_rule": "parameter_count + global_local_record_index",
            "dynamic_start": "parameter_count + native_local_record_count",
            "physical_capacity": VALUE_CAPACITY,
            "semantic_id_equals_header_slot": True,
            "wide_extension_slots_are_holes": True
        },
        "guards": guards,
        "qualification_rule": (
            "This audit validates representation mathematics and the unchanged physical banks only. Exact native parameter_count/local_record_count, typed constant interning, wide-literal slot count, materialized instruction results and use-site def/use must be measured from a PASS native local candidate before a value-namespace transform may be built."
        ),
        "next": "WAIT_FOR_NATIVE_LOCAL_PASS_THEN_BUILD_EXACT_VALUE_NAMESPACE_PREFLIGHT",
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    contract = json.loads(args.contract.resolve().read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise ValueError("value namespace contract must be a JSON object")
    result = audit(args.source.resolve().read_text(encoding="utf-8"), contract)
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"LEGACY_VALUE_SLOTS={result['legacy_storage']['total_slots']}")
    print(f"PARAMETER_CAPACITY_BOUND={result['parameter_metadata']['capacity_bound']}")
    print(f"UNIQUE_UNTYPED_NUMERIC_VALUES={result['numeric_inventory']['unique_untyped_numeric_values']}")
    print(f"UNIQUE_WIDE_VALUES={result['numeric_inventory']['unique_wide_values']}")
    print(f"HEADER_MAX={result['packed_header']['maximum_encoded']}")
    print("NATIVE_EVIDENCE=False")
    print("CANONICAL_SOURCE_MUTATED=False")
    print(f"NEXT={result['next']}")
    return 0 if result["status"] == "STATIC_VALUE_NAMESPACE_DESIGN_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
