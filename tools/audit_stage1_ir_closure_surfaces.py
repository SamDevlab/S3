"""Normalize Stage1 IR closure into five semantic surfaces.

This host/static audit intentionally does not require the historical seven-lane
inventory to remain unchanged. Earlier checkpoints split parameter/local/
constant identity into separate lanes and operand/result relationships into
fine-grained entries. Newer Stage1 checkpoints may close some of those while
still lacking the five emitter-facing semantic surfaces below.

The audit consumes semantic-ir-requirements.json when available and reports
which relationships are still absent. It is not native evidence and does not
authorize source promotion, general emission, self-emission, Stage2, Stage3 or
T4.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = (
    ROOT / "reports" / "selfhost" / "stage1" / "semantic-ir-requirements.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "ir-closure-surfaces.json"
)

SURFACES: dict[str, tuple[str, ...]] = {
    "S1_typed_value_definitions": ("typed_value_definitions",),
    "S2_instruction_def_use": (
        "instruction_operand_value_ids",
        "instruction_result_value_ids",
    ),
    "S3_call_dataflow": (
        "call_argument_value_ids",
        "call_result_value_ids",
    ),
    "S4_complete_terminators": ("complete_terminator_values",),
    "S5_canonical_serialized_ir": ("canonical_serialized_ir",),
}

SURFACE_DEPENDENCIES = {
    "S1_typed_value_definitions": [],
    "S2_instruction_def_use": ["S1_typed_value_definitions"],
    "S3_call_dataflow": [
        "S1_typed_value_definitions",
        "S2_instruction_def_use",
    ],
    "S4_complete_terminators": [
        "S1_typed_value_definitions",
        "CURRENT_BLOCK_REPRESENTATION_NATIVE_RESULT",
    ],
    "S5_canonical_serialized_ir": [
        "S1_typed_value_definitions",
        "S2_instruction_def_use",
        "S3_call_dataflow",
        "S4_complete_terminators",
    ],
}


def _relationships(requirements: dict[str, Any]) -> dict[str, bool | None]:
    value = (
        requirements.get("storage_evidence", {})
        .get("semantic_relationships", {})
    )
    if not isinstance(value, dict):
        return {}
    result: dict[str, bool | None] = {}
    for name in {item for fields in SURFACES.values() for item in fields}:
        raw = value.get(name)
        result[name] = raw if isinstance(raw, bool) else None
    return result


def build_surface_report(requirements: dict[str, Any]) -> dict[str, Any]:
    relationships = _relationships(requirements)
    surfaces: dict[str, Any] = {}
    missing_surfaces: list[str] = []
    unknown_surfaces: list[str] = []

    for surface, fields in SURFACES.items():
        states = {field: relationships.get(field) for field in fields}
        if any(value is False for value in states.values()):
            state = "MISSING"
            missing_surfaces.append(surface)
        elif all(value is True for value in states.values()):
            state = "CLOSED"
        else:
            state = "UNKNOWN"
            unknown_surfaces.append(surface)
        surfaces[surface] = {
            "state": state,
            "relationships": states,
            "depends_on": SURFACE_DEPENDENCIES[surface],
            "static_design_may_proceed": True,
            "canonical_promotion_authorized": False,
        }

    legacy_missing = requirements.get("missing_lossless_typed_lanes", [])
    if not isinstance(legacy_missing, list):
        legacy_missing = []

    guards = {
        "all_relationship_fields_are_known": all(
            relationships.get(field) is not None
            for fields in SURFACES.values()
            for field in fields
        ),
        "no_surface_is_unknown": not unknown_surfaces,
        "blocked_source_does_not_authorize_promotion": requirements.get("stage1_self_emit")
        != "PASS",
    }

    status = (
        "STATIC_FIVE_SURFACE_MODEL_PASS"
        if all(guards.values())
        else "STATIC_FIVE_SURFACE_MODEL_RECONCILE"
    )

    return {
        "schema": "s3.selfhost.stage1-ir-closure-surfaces.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "historical_missing_lane_count": len(legacy_missing),
        "historical_missing_lanes": legacy_missing,
        "semantic_surface_count": len(SURFACES),
        "missing_surface_count": len(missing_surfaces),
        "missing_surfaces": missing_surfaces,
        "surfaces": surfaces,
        "guards": guards,
        "interpretation": (
            "The five surfaces are emitter-facing closure categories. The historical "
            "missing_lossless_typed_lanes list may contain more or fewer entries as "
            "individual relationships are split or closed; it is provenance, not a "
            "fixed expected cardinality gate."
        ),
        "general_emitter": (
            "BLOCKED_IR_SEMANTIC_SURFACES_INCOMPLETE"
            if missing_surfaces or unknown_surfaces
            else "STATIC_SURFACES_CLOSED_NATIVE_QUALIFICATION_STILL_REQUIRED"
        ),
        "self_emit": "NOT_AUTHORIZED_BY_STATIC_AUDIT",
        "stage2": "NOT_AUTHORIZED_BY_STATIC_AUDIT",
        "stage3": "NOT_AUTHORIZED_BY_STATIC_AUDIT",
        "t4": "NOT_AUTHORIZED_BY_STATIC_AUDIT",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    requirements = json.loads(args.requirements.resolve().read_text(encoding="utf-8"))
    if not isinstance(requirements, dict):
        raise ValueError("semantic requirements must be a JSON object")
    result = build_surface_report(requirements)
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"SEMANTIC_SURFACES={result['semantic_surface_count']}")
    print(f"MISSING_SURFACES={result['missing_surface_count']}")
    print("NATIVE_EVIDENCE=False")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if result["status"] == "STATIC_FIVE_SURFACE_MODEL_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
