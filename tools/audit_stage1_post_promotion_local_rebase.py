"""Audit the post-promotion Stage1 local-IR rebase contract.

This is a static design gate, not native evidence and not a source transform.
The historical IR-v2 local tooling was built around the pre-promotion packed
``ir_parameter_records: i64[64]`` lane. The canonical Stage1 now uses four
68-slot parameter metadata lanes, so blindly chaining the historical local
transform would reintroduce a stale namespace and an already-observed OOM-prone
source shape.

This audit makes the rebase explicit:
- parameter semantic IDs occupy ``[0, parameter_count)``;
- local semantic IDs start at ``parameter_count`` and are derived from the
  global local-record slot, requiring no extra value-ID array;
- local records preserve semantic metadata but defer physical frame layout;
- the compact implementation should recognize scalar/fixed-array declarations
  with a bounded rolling token window instead of the historical large state
  machine.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
LEGACY_LOCAL_TRANSFORM = ROOT / "tools" / "patch_stage1_codegen_ir_v2_locals.py"
LEGACY_VALUE_AUDIT = ROOT / "tools" / "audit_stage1_codegen_ir_v2_value_namespace.py"
PARAMETER_VALUE_CANDIDATE = ROOT / "tools" / "patch_stage1_parameter_semantic_value_ids.py"
DEFAULT_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "post-promotion-local-rebase-design-audit.json"
)

SIGNED_I64_MAX = 2**63 - 1
PARAMETER_CAPACITY = 68
LOCAL_RECORD_CAPACITY_BOUND = 365
FUNCTION_DOMAIN = 64
IDENTITY_DOMAIN = 365
TYPE_DOMAIN = 365
LOCAL_ORDINAL_DOMAIN = 365
FIXED_EXTENT_MAX = 1460

_ARRAY_RE = re.compile(
    r"(?m)^\s*mut\s+(ir_parameter_(?:owner|name|ordinal|type)):\s*i64\[(\d+)\]\s*="
)


def pack_local_record(
    owner: int,
    name_identity: int,
    type_id: int,
    storage_kind: int,
    local_ordinal: int,
    fixed_extent: int,
) -> int:
    """Pack semantic local metadata without a redundant semantic-ID field."""

    fields = (
        (owner, 0, FUNCTION_DOMAIN - 1, "owner"),
        (name_identity, 0, IDENTITY_DOMAIN - 1, "name_identity"),
        (type_id, 0, TYPE_DOMAIN - 1, "type_id"),
        (storage_kind, 1, 2, "storage_kind"),
        (local_ordinal, 0, LOCAL_ORDINAL_DOMAIN - 1, "local_ordinal"),
        (fixed_extent, 1, FIXED_EXTENT_MAX, "fixed_extent"),
    )
    for value, minimum, maximum, label in fields:
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum or value > maximum:
            raise ValueError(f"{label} outside packed-local domain")

    record = owner + 1
    record = record * (IDENTITY_DOMAIN + 1) + (name_identity + 1)
    record = record * (TYPE_DOMAIN + 1) + (type_id + 1)
    record = record * 3 + storage_kind
    record = record * (LOCAL_ORDINAL_DOMAIN + 1) + (local_ordinal + 1)
    record = record * (FIXED_EXTENT_MAX + 1) + fixed_extent
    if record > SIGNED_I64_MAX:
        raise ValueError("packed local record exceeds signed i64")
    return record


def maximum_packed_local_record() -> int:
    return pack_local_record(
        FUNCTION_DOMAIN - 1,
        IDENTITY_DOMAIN - 1,
        TYPE_DOMAIN - 1,
        2,
        LOCAL_ORDINAL_DOMAIN - 1,
        FIXED_EXTENT_MAX,
    )


def _parameter_arrays(source: str) -> dict[str, int]:
    return {name: int(size) for name, size in _ARRAY_RE.findall(source)}


def audit(
    source: str,
    *,
    legacy_local_transform: str,
    legacy_value_audit: str,
    parameter_value_candidate: str,
) -> dict[str, object]:
    parameter_arrays = _parameter_arrays(source)
    expected_parameter_arrays = {
        "ir_parameter_owner",
        "ir_parameter_name",
        "ir_parameter_ordinal",
        "ir_parameter_type",
    }
    packed_max = maximum_packed_local_record()

    guards = {
        "canonical_has_exact_four_parameter_metadata_lanes": set(parameter_arrays) == expected_parameter_arrays,
        "canonical_parameter_metadata_lanes_are_68_slots": bool(parameter_arrays)
        and all(size == PARAMETER_CAPACITY for size in parameter_arrays.values()),
        "canonical_no_longer_has_legacy_packed_parameter_lane": "mut ir_parameter_records:" not in source,
        "legacy_local_transform_requires_stale_64_slot_parameter_lane": (
            '"mut ir_parameter_records: i64[64]"' in legacy_local_transform
        ),
        "legacy_value_namespace_hardcodes_64_parameter_boundary": (
            "PARAMETER_DOMAIN_END = 64" in legacy_value_audit
        ),
        "parameter_semantic_value_candidate_uses_parameter_slot": (
            "ir_return_operand[current_function] = parameter_scan" in parameter_value_candidate
            and "PARAMETER_VALUE_ID=PARAMETER_SLOT" in parameter_value_candidate
        ),
        "packed_local_record_fits_signed_i64": packed_max <= SIGNED_I64_MAX,
        "current_source_tracks_previous_token": (
            "mut previous_kind: i64 = 0" in source
            and "mut previous_value: i64 = 0" in source
            and "previous_kind = kind" in source
            and "previous_value = value" in source
        ),
        "current_source_contains_fixed_arrays": bool(
            re.search(r"\bmut\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z0-9_]+\[\d+\]", source)
        ),
    }

    status = (
        "STATIC_POST_PROMOTION_LOCAL_REBASE_DESIGN_PASS"
        if all(guards.values())
        else "STATIC_POST_PROMOTION_LOCAL_REBASE_DESIGN_FAIL"
    )

    return {
        "schema": "s3.selfhost.stage1-post-promotion-local-rebase-design.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "canonical_parameter_metadata": {
            "arrays": parameter_arrays,
            "capacity_bound": PARAMETER_CAPACITY,
            "semantic_value_domain": "[0,parameter_count)",
            "semantic_value_id_rule": "parameter_slot",
        },
        "legacy_tooling_disposition": {
            "local_transform": str(LEGACY_LOCAL_TRANSFORM),
            "value_namespace_audit": str(LEGACY_VALUE_AUDIT),
            "status": "REBASE_REQUIRED_DO_NOT_CHAIN_AS_CANONICAL",
            "reason": "legacy local/value tooling is bound to the historical packed 64-slot parameter namespace",
        },
        "local_record_contract": {
            "capacity_bound_not_promotion_authority": LOCAL_RECORD_CAPACITY_BOUND,
            "fields": [
                "owner_function",
                "name_identity",
                "declared_type",
                "storage_kind",
                "local_ordinal",
                "fixed_extent",
            ],
            "mutability": "implicit_mut_declaration_for_current_local_grammar",
            "storage_kinds": {"1": "SCALAR", "2": "FIXED_ARRAY"},
            "semantic_value_id_rule": "parameter_count + global_local_record_slot",
            "physical_frame_offset": "DEFERRED_TO_EMITTER",
            "maximum_packed_record": packed_max,
            "signed_i64_max": SIGNED_I64_MAX,
        },
        "compact_capture_contract": {
            "implementation_shape": "BOUNDED_ROLLING_TOKEN_WINDOW",
            "scalar_suffix": ["mut", "name", ":", "type", "="],
            "fixed_array_suffix": ["mut", "name", ":", "type", "[", "extent", "]", "="],
            "maximum_history_tokens": 7,
            "reason": "avoid the historical large local parser state machine that materially increased candidate source size",
        },
        "historical_native_constraint": {
            "previous_local_candidate_source_bytes": 193408,
            "previous_native_build": "HOST_OOM",
            "previous_native_output": "ABSENT",
            "interpretation": "HOST_CAPACITY_EVIDENCE_ONLY_NOT_COMPILER_SEMANTIC_FAILURE",
        },
        "guards": guards,
        "next": (
            "IMPLEMENT_COMPACT_LOCAL_METADATA_CANDIDATE_WITH_DYNAMIC_PARAMETER_NAMESPACE"
            if status == "STATIC_POST_PROMOTION_LOCAL_REBASE_DESIGN_PASS"
            else "RECONCILE_POST_PROMOTION_LOCAL_REBASE_GUARDS"
        ),
        "general_emitter": "INCREMENTAL_ONLY",
        "self_emit": "BLOCKED_REMAINING_LOSSLESS_TYPED_IR_LANES",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--legacy-local-transform", type=Path, default=LEGACY_LOCAL_TRANSFORM)
    parser.add_argument("--legacy-value-audit", type=Path, default=LEGACY_VALUE_AUDIT)
    parser.add_argument("--parameter-value-candidate", type=Path, default=PARAMETER_VALUE_CANDIDATE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = audit(
        args.source.resolve().read_text(encoding="utf-8"),
        legacy_local_transform=args.legacy_local_transform.resolve().read_text(encoding="utf-8"),
        legacy_value_audit=args.legacy_value_audit.resolve().read_text(encoding="utf-8"),
        parameter_value_candidate=args.parameter_value_candidate.resolve().read_text(encoding="utf-8"),
    )
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"PARAMETER_CAPACITY_BOUND={PARAMETER_CAPACITY}")
    print("PARAMETER_VALUE_NAMESPACE=[0,parameter_count)")
    print("LOCAL_VALUE_ID_RULE=parameter_count+global_local_record_slot")
    print(f"PACKED_LOCAL_MAX={result['local_record_contract']['maximum_packed_record']}")
    print("NATIVE_EVIDENCE=False")
    print("CANONICAL_SOURCE_MUTATED=False")
    print(f"NEXT={result['next']}")
    return 0 if result["status"] == "STATIC_POST_PROMOTION_LOCAL_REBASE_DESIGN_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
