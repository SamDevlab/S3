"""Validate the design-only Stage1-to-Stage2 serialized IR envelope contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "reports" / "selfhost" / "stage1" / "semantic-ir-requirements.json"
CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "stage2-serialized-ir-envelope-contract.json"
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage1" / "stage2-serialized-ir-envelope-design-audit.json"

EXPECTED_SEMANTIC_RELATIONSHIPS = (
    "typed_value_definitions",
    "instruction_operand_value_ids",
    "instruction_result_value_ids",
    "call_argument_value_ids",
    "call_result_value_ids",
    "complete_terminator_values",
    "canonical_serialized_ir",
)


def audit(requirements: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    storage = requirements.get("storage_evidence", {})
    relationships = storage.get("semantic_relationships", {}) if isinstance(storage, dict) else {}
    envelope = contract.get("envelope", {})
    bits = contract.get("completeness_bits", {})
    stage1_rules = contract.get("stage1_emission_rules", [])
    stage2_rules = contract.get("stage2_acceptance_rules", [])
    prerequisite = contract.get("prerequisite", {})

    if not isinstance(relationships, dict):
        raise ValueError("semantic relationships evidence is missing")
    if not isinstance(envelope, dict) or not isinstance(bits, dict):
        raise ValueError("serialized IR envelope contract is incomplete")

    current_complete = {
        name: relationships.get(name) is True
        for name in EXPECTED_SEMANTIC_RELATIONSHIPS
    }
    typed_workstreams_complete = all(
        current_complete[name]
        for name in EXPECTED_SEMANTIC_RELATIONSHIPS
        if name != "canonical_serialized_ir"
    )

    guards = {
        "requirements_currently_block_general_emitter": requirements.get("status") == "BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP",
        "envelope_magic_is_s3ir2": envelope.get("magic") == "S3IR2",
        "schema_version_is_one": envelope.get("schema_version") == 1,
        "required_completeness_mask_is_15": contract.get("required_completeness_mask") == 15,
        "four_completeness_bits_defined": len(bits) == 4 and set(bits) == {"1", "2", "4", "8"},
        "stage2_creation_forbidden_before_prerequisites": prerequisite.get("stage2_creation_allowed_before_prerequisites") is False,
        "all_native_gates_required": prerequisite.get("all_required_native_gates_must_pass") is True,
        "stage1_rules_fail_closed": any("completeness_mask == 15" in str(rule) for rule in stage1_rules),
        "stage2_rules_reject_incomplete_mask": any("completeness_mask != 15" in str(rule) for rule in stage2_rules),
        "current_typed_workstreams_are_not_all_complete": typed_workstreams_complete is False,
        "canonical_serialized_ir_is_not_currently_present": current_complete["canonical_serialized_ir"] is False,
    }

    status = (
        "STATIC_STAGE2_ENVELOPE_DESIGN_PASS_FAIL_CLOSED"
        if all(guards.values())
        else "STATIC_STAGE2_ENVELOPE_DESIGN_RECONCILE"
    )
    return {
        "schema": "s3.selfhost.stage2-serialized-ir-envelope-design-audit.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "current_semantic_relationships": current_complete,
        "typed_workstreams_complete": typed_workstreams_complete,
        "stage2_creation_allowed_now": False,
        "required_completeness_mask": contract.get("required_completeness_mask"),
        "guards": guards,
        "next": (
            "WAIT_FOR_W1_W2_W3_W4_NATIVE_CLOSURE"
            if status == "STATIC_STAGE2_ENVELOPE_DESIGN_PASS_FAIL_CLOSED"
            else "RECONCILE_STAGE2_ENVELOPE_CONTRACT"
        ),
        "self_emit": "NOT_STARTED",
        "stage2": "DESIGN_ONLY_NOT_CREATED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=REQUIREMENTS)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = audit(
        json.loads(args.requirements.resolve().read_text(encoding="utf-8")),
        json.loads(args.contract.resolve().read_text(encoding="utf-8")),
    )
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"STAGE2_CREATION_ALLOWED_NOW={result['stage2_creation_allowed_now']}")
    print(f"REQUIRED_COMPLETENESS_MASK={result['required_completeness_mask']}")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] == "STATIC_STAGE2_ENVELOPE_DESIGN_PASS_FAIL_CLOSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
