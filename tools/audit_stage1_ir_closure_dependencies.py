"""Build a static dependency matrix for the remaining Stage1 IR closure.

The input is the existing semantic-ir-requirements.json evidence.  This module
does not reinterpret lexical/event records as semantic IR and does not authorize
native promotion.  It groups the seven documented missing lanes into five
parallel workstreams so work that does not depend on the current native block
capacity experiment can proceed safely.
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
    ROOT / "reports" / "selfhost" / "stage1" / "ir-closure-parallel-workstreams.json"
)

EXPECTED_MISSING_LANES = {
    "parameter_identity_type_mutability_and_value_id",
    "local_identity_type_mutability_storage_and_value_id",
    "typed_constant_interning_and_definition_ids",
    "instruction_operands_results_and_order",
    "call_result_and_argument_value_ids",
    "branch_conditions_and_complete_terminators",
    "canonical_serialized_ir_artifact",
}


def build_matrix(requirements: dict[str, Any]) -> dict[str, Any]:
    missing = set(requirements.get("missing_lossless_typed_lanes", []))
    relationships = (
        requirements.get("storage_evidence", {})
        .get("semantic_relationships", {})
    )

    workstreams = {
        "W1_symbol_and_value_identity": {
            "covers": [
                "parameter_identity_type_mutability_and_value_id",
                "local_identity_type_mutability_storage_and_value_id",
                "typed_constant_interning_and_definition_ids",
            ],
            "can_prepare_in_parallel": True,
            "can_promote_without_native_candidate": False,
            "depends_on": [],
            "deliverables_now": [
                "namespace rules",
                "record schemas",
                "collision guards",
                "host roundtrip/property tests",
            ],
            "promotion_gate": "NATIVE_TYPED_VALUE_NAMESPACE_QUALIFICATION",
        },
        "W2_instruction_def_use_and_order": {
            "covers": ["instruction_operands_results_and_order"],
            "can_prepare_in_parallel": True,
            "can_promote_without_native_candidate": False,
            "depends_on": ["W1_symbol_and_value_identity"],
            "deliverables_now": [
                "instruction record schema",
                "operand/result cardinality audit",
                "overwrite-frontier proof for legacy write-only lane",
            ],
            "promotion_gate": "NATIVE_INSTRUCTION_DEF_USE_QUALIFICATION",
        },
        "W3_call_dataflow_and_abi": {
            "covers": ["call_result_and_argument_value_ids"],
            "can_prepare_in_parallel": True,
            "can_promote_without_native_candidate": False,
            "depends_on": [
                "W1_symbol_and_value_identity",
                "W2_instruction_def_use_and_order",
            ],
            "deliverables_now": [
                "argument value-id linkage schema",
                "result destination schema",
                "internal/foreign ABI classification guards",
            ],
            "promotion_gate": "NATIVE_CALL_LINKAGE_QUALIFICATION",
        },
        "W4_terminator_dataflow": {
            "covers": ["branch_conditions_and_complete_terminators"],
            "can_prepare_in_parallel": True,
            "can_promote_without_native_candidate": False,
            "depends_on": [
                "CURRENT_COMPACT_BLOCK_CAPACITY_NATIVE_RESULT",
                "W1_symbol_and_value_identity",
            ],
            "deliverables_now": [
                "terminator enum/schema",
                "condition value-id contract",
                "target roundtrip guards",
                "block-capacity-independent verifier rules",
            ],
            "promotion_gate": "NATIVE_TERMINATOR_QUALIFICATION",
        },
        "W5_canonical_stage2_serialization": {
            "covers": ["canonical_serialized_ir_artifact"],
            "can_prepare_in_parallel": True,
            "can_promote_without_native_candidate": False,
            "depends_on": [
                "W1_symbol_and_value_identity",
                "W2_instruction_def_use_and_order",
                "W3_call_dataflow_and_abi",
                "W4_terminator_dataflow",
            ],
            "deliverables_now": [
                "versioned schema envelope",
                "deterministic ordering rules",
                "hash/provenance fields",
                "reject-on-incomplete-lane rules",
            ],
            "promotion_gate": "STAGE1_SERIALIZE_THEN_INDEPENDENT_STAGE2_PARSE",
        },
    }

    for stream in workstreams.values():
        covers = set(stream["covers"])
        stream["currently_missing"] = sorted(covers & missing)
        stream["source_lanes_already_closed"] = sorted(covers - missing)
        stream["complete_in_current_stage1"] = not bool(covers & missing)

    guards = {
        "requirements_status_is_blocked": requirements.get("status")
        == "BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP",
        "all_expected_missing_lanes_present": EXPECTED_MISSING_LANES <= missing,
        "typed_value_definitions_absent": relationships.get("typed_value_definitions")
        is False,
        "instruction_operand_value_ids_absent": relationships.get(
            "instruction_operand_value_ids"
        )
        is False,
        "instruction_result_value_ids_absent": relationships.get(
            "instruction_result_value_ids"
        )
        is False,
        "call_argument_value_ids_absent": relationships.get("call_argument_value_ids")
        is False,
        "call_result_value_ids_absent": relationships.get("call_result_value_ids")
        is False,
        "complete_terminator_values_absent": relationships.get(
            "complete_terminator_values"
        )
        is False,
        "canonical_serialized_ir_absent": relationships.get("canonical_serialized_ir")
        is False,
    }

    return {
        "schema": "s3.selfhost.stage1-ir-closure-parallel-workstreams.v1",
        "status": (
            "STATIC_PARALLEL_WORKSTREAM_MATRIX_PASS"
            if all(guards.values())
            else "STATIC_PARALLEL_WORKSTREAM_MATRIX_RECONCILE"
        ),
        "native_evidence": False,
        "canonical_source_mutated": False,
        "source_requirements_status": requirements.get("status"),
        "missing_lane_count": len(missing),
        "missing_lanes": sorted(missing),
        "workstreams": workstreams,
        "parallel_execution_rule": {
            "safe_now": [
                "static schemas",
                "host audits",
                "property tests",
                "fail-closed verifier design",
                "Stage2 serialization envelope design",
            ],
            "must_wait_for_native_or_upstream_lane": [
                "canonical Stage1 source promotion",
                "general emitter enablement",
                "self emit",
                "Stage2 artifact creation",
                "Stage3",
                "T4",
            ],
        },
        "guards": guards,
        "general_emitter": "BLOCKED_UNTIL_EMITTER_WORKSTREAMS_NATIVE_QUALIFY",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_CREATED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    requirements = json.loads(args.requirements.resolve().read_text(encoding="utf-8"))
    result = build_matrix(requirements)
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"MISSING_LANES={result['missing_lane_count']}")
    print("PARALLEL_WORKSTREAMS=5")
    print("NATIVE_EVIDENCE=False")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if result["status"] == "STATIC_PARALLEL_WORKSTREAM_MATRIX_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
