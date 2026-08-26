"""Validate the design-only IR-v2 instruction stream contract.

This audit consumes existing semantic-requirements evidence. It never treats the
host IR oracle as Stage1 output and never authorizes source promotion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "reports" / "selfhost" / "stage1" / "semantic-ir-requirements.json"
CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "ir-v2-instruction-stream-contract.json"
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage1" / "ir-v2-instruction-stream-design-audit.json"
LEGACY_BANK_SIZE = 365


def audit(requirements: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    missing = set(requirements.get("missing_lossless_typed_lanes", []))
    reference = requirements.get("reference_typed_ir", {})
    storage = requirements.get("storage_evidence", {})
    legacy = storage.get("legacy_instruction_records", {}) if isinstance(storage, dict) else {}
    relationships = storage.get("semantic_relationships", {}) if isinstance(storage, dict) else {}
    physical = contract.get("physical_strategy", {})
    logical = contract.get("logical_instruction", {})
    verifier = contract.get("verifier_requirements", [])

    if not isinstance(reference, dict) or not isinstance(legacy, dict):
        raise ValueError("semantic requirements are missing typed-IR/legacy instruction evidence")
    if not isinstance(physical, dict) or not isinstance(logical, dict):
        raise ValueError("instruction stream contract is missing required sections")
    if not isinstance(verifier, list):
        raise ValueError("instruction stream verifier requirements must be a list")

    host_instructions = reference.get("instructions")
    host_max_per_function = reference.get("max_instructions_per_function")
    legacy_declarations = legacy.get("declaration_count")
    legacy_reads = legacy.get("read_count")
    legacy_writes = legacy.get("write_count")
    legacy_slots = (
        legacy_declarations * LEGACY_BANK_SIZE
        if isinstance(legacy_declarations, int) and not isinstance(legacy_declarations, bool)
        else None
    )

    guards = {
        "instruction_lane_is_still_missing": "instruction_operands_results_and_order" in missing,
        "host_oracle_is_labeled_non_stage1": reference.get("status") == "MEASURED_HOST_IR_ORACLE_NOT_STAGE1_EVIDENCE",
        "host_oracle_exceeds_legacy_instruction_slots": (
            isinstance(host_instructions, int)
            and isinstance(legacy_slots, int)
            and host_instructions > legacy_slots
        ),
        "max_function_exceeds_single_legacy_bank": (
            isinstance(host_max_per_function, int)
            and host_max_per_function > LEGACY_BANK_SIZE
        ),
        "legacy_instruction_lane_has_no_semantic_reads": legacy_reads == 0,
        "legacy_instruction_lane_has_writes": isinstance(legacy_writes, int) and legacy_writes > 0,
        "typed_operand_ids_absent": relationships.get("instruction_operand_value_ids") is False,
        "typed_result_ids_absent": relationships.get("instruction_result_value_ids") is False,
        "contract_forbids_fixed_matrix": physical.get("fixed_instruction_matrix_allowed") is False,
        "contract_forbids_legacy_semantic_reuse": physical.get("legacy_ir_instruction_records_semantic_reuse_allowed") is False,
        "contract_uses_streaming_records": physical.get("kind") == "STREAMING_SERIALIZED_RECORDS",
        "logical_contract_has_order_field": "ordinal_in_block" in logical.get("fields", []),
        "logical_contract_has_operands": "operand_value_ids" in logical.get("fields", []),
        "logical_contract_has_results": "result_value_ids" in logical.get("fields", []),
        "verifier_is_nonempty": len(verifier) >= 6,
    }

    status = (
        "STATIC_INSTRUCTION_STREAM_DESIGN_PASS"
        if all(guards.values())
        else "STATIC_INSTRUCTION_STREAM_DESIGN_RECONCILE"
    )
    return {
        "schema": "s3.selfhost.ir-v2-instruction-stream-design-audit.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "oracle": {
            "status": reference.get("status"),
            "instructions": host_instructions,
            "max_instructions_per_function": host_max_per_function,
            "instruction_results": reference.get("instruction_results"),
            "interpretation": "capacity/design oracle only; never Stage1 qualification",
        },
        "legacy_instruction_lane": {
            "declarations": legacy_declarations,
            "estimated_physical_slots": legacy_slots,
            "writes": legacy_writes,
            "reads": legacy_reads,
            "semantic_reuse_allowed": False,
        },
        "contract_strategy": physical.get("kind"),
        "guards": guards,
        "next": (
            "WAIT_FOR_NATIVE_VALUE_NAMESPACE_THEN_BUILD_INSTRUCTION_STREAM_PREFLIGHT"
            if status == "STATIC_INSTRUCTION_STREAM_DESIGN_PASS"
            else "RECONCILE_INSTRUCTION_STREAM_CONTRACT"
        ),
        "general_emitter": "BLOCKED_UNTIL_TYPED_INSTRUCTION_DEF_USE_EXISTS",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_CREATED",
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
    print(f"HOST_ORACLE_INSTRUCTIONS={result['oracle']['instructions']}")
    print(f"LEGACY_INSTRUCTION_SLOTS={result['legacy_instruction_lane']['estimated_physical_slots']}")
    print("NATIVE_EVIDENCE=False")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if result["status"] == "STATIC_INSTRUCTION_STREAM_DESIGN_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
