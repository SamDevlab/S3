"""Audit design-only call-linkage and terminator contracts against current IR evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "reports" / "selfhost" / "stage1" / "semantic-ir-requirements.json"
CALL_CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "ir-v2-call-linkage-contract.json"
TERMINATOR_CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "ir-v2-terminator-contract.json"
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage1" / "call-terminator-design-audit.json"


def audit(
    requirements: dict[str, Any],
    call_contract: dict[str, Any],
    terminator_contract: dict[str, Any],
) -> dict[str, Any]:
    storage = requirements.get("storage_evidence", {})
    relationships = storage.get("semantic_relationships", {}) if isinstance(storage, dict) else {}
    reference = requirements.get("reference_typed_ir", {})
    call_logical = call_contract.get("logical_call", {})
    foreign = call_contract.get("foreign_abi", {})
    term_kinds = terminator_contract.get("terminator_kinds", {})
    compact_scope = terminator_contract.get("compact_block_candidate_scope", {})

    call_guards = {
        "call_argument_value_ids_absent_in_current_stage1": relationships.get("call_argument_value_ids") is False,
        "call_result_value_ids_absent_in_current_stage1": relationships.get("call_result_value_ids") is False,
        "call_contract_has_instruction_owner": "defining_instruction_id" in call_logical.get("fields", []),
        "call_contract_has_ordered_argument_values": "argument_value_ids" in call_logical.get("fields", []),
        "call_contract_has_result_values": "result_value_ids" in call_logical.get("fields", []),
        "call_contract_distinguishes_internal_foreign": set(call_logical.get("callee_kinds", [])) == {"INTERNAL", "FOREIGN"},
        "foreign_abi_has_typed_signature": set(foreign.get("required_fields", [])) >= {
            "foreign_symbol_identity",
            "parameter_types",
            "return_type",
            "argument_value_ids",
            "result_value_ids",
        },
    }

    term_guards = {
        "complete_terminator_values_absent_in_current_stage1": relationships.get("complete_terminator_values") is False,
        "return_kind_defined": "RETURN" in term_kinds,
        "jump_kind_defined": "JUMP" in term_kinds,
        "branch3_kind_defined": "BRANCH3" in term_kinds,
        "branch3_has_three_targets": term_kinds.get("BRANCH3", {}).get("target_count") == 3,
        "branch3_requires_condition_value": "condition_value_id" in term_kinds.get("BRANCH3", {}).get("required", []),
        "return_requires_value_id": "return_value_id" in term_kinds.get("RETURN", {}).get("required", []),
        "compact_block_candidate_is_capacity_only": compact_scope.get("classification") == "STRUCTURAL_CAPACITY_ONLY",
        "compact_block_candidate_does_not_close_w4": compact_scope.get("closes_complete_terminator_lane") is False,
    }

    host_calls = reference.get("call_kinds", {}) if isinstance(reference, dict) else {}
    host_terms = reference.get("terminators", {}) if isinstance(reference, dict) else {}
    status = (
        "STATIC_CALL_TERMINATOR_DESIGN_PASS"
        if all(call_guards.values()) and all(term_guards.values())
        else "STATIC_CALL_TERMINATOR_DESIGN_RECONCILE"
    )
    return {
        "schema": "s3.selfhost.ir-v2-call-terminator-design-audit.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "host_oracle": {
            "status": reference.get("status") if isinstance(reference, dict) else None,
            "calls": host_calls,
            "terminators": host_terms,
            "interpretation": "design scale oracle only; not Stage1 evidence",
        },
        "call_guards": call_guards,
        "terminator_guards": term_guards,
        "compact_block_native_result_required_for_w4": True,
        "call_linkage_native_allowed_now": False,
        "terminator_native_allowed_now": False,
        "next": (
            "WAIT_FOR_W1_W2_AND_COMPACT_BLOCK_NATIVE_GATES"
            if status == "STATIC_CALL_TERMINATOR_DESIGN_PASS"
            else "RECONCILE_CALL_TERMINATOR_CONTRACTS"
        ),
        "general_emitter": "BLOCKED_CALL_AND_TERMINATOR_LINKAGE_INCOMPLETE",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_CREATED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=REQUIREMENTS)
    parser.add_argument("--call-contract", type=Path, default=CALL_CONTRACT)
    parser.add_argument("--terminator-contract", type=Path, default=TERMINATOR_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = audit(
        json.loads(args.requirements.resolve().read_text(encoding="utf-8")),
        json.loads(args.call_contract.resolve().read_text(encoding="utf-8")),
        json.loads(args.terminator_contract.resolve().read_text(encoding="utf-8")),
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
    print("CALL_LINKAGE_NATIVE_ALLOWED_NOW=False")
    print("TERMINATOR_NATIVE_ALLOWED_NOW=False")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] == "STATIC_CALL_TERMINATOR_DESIGN_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
