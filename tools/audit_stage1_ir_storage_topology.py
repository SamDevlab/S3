"""Classify Stage1 IR storage families without sizing arrays from the host oracle.

The reference_typed_ir section is a host/compiler measurement oracle only. It
may reveal scale and topology pressure, but it is never Stage1 evidence and must
not be used to silently calibrate current Stage1 counters.

This audit deliberately distinguishes:
- FIXED_BANK_PLAUSIBLE: bounded metadata may fit a measured fixed domain;
- STREAM_OR_REUSE_REQUIRED: full-module materialization exceeds the current
  bounded bootstrap storage model and needs streaming, per-function reuse, or a
  proven liveness/overwrite frontier;
- REPRESENTATION_NOT_COMPARABLE: host and Stage1 structures are not yet proven
  one-to-one, so numeric inequality is not a capacity failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE1 = ROOT / "reports" / "selfhost" / "stage1"
DEFAULT_REQUIREMENTS = STAGE1 / "semantic-ir-requirements.json"
DEFAULT_VALUE_CONTRACT = STAGE1 / "codegen-ir-v2-value-namespace-contract.json"
DEFAULT_REPORT = STAGE1 / "ir-storage-topology-audit.json"

LEGACY_BANK_SIZE = 365
COMPACT_BLOCK_BANKS = 4
COMPACT_BLOCK_CAPACITY = LEGACY_BANK_SIZE * COMPACT_BLOCK_BANKS


def _positive_int(mapping: dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def audit(
    requirements: dict[str, Any],
    value_contract: dict[str, Any],
    *,
    stage1_structural_blocks: int | None = None,
) -> dict[str, Any]:
    oracle = requirements.get("reference_typed_ir")
    if not isinstance(oracle, dict):
        oracle = {}
    oracle_status = oracle.get("status")

    value_storage = value_contract.get("physical_storage")
    if not isinstance(value_storage, dict):
        value_storage = {}
    value_slots = _positive_int(value_storage, "physical_slots")

    blocks = _positive_int(oracle, "blocks")
    instructions = _positive_int(oracle, "instructions")
    results = _positive_int(oracle, "instruction_results")
    registers = _positive_int(oracle, "registers")
    memory_objects = _positive_int(oracle, "memory_objects")
    max_blocks_per_function = _positive_int(oracle, "max_blocks_per_function")
    max_instructions_per_function = _positive_int(oracle, "max_instructions_per_function")
    max_registers_per_function = _positive_int(oracle, "max_registers_per_function")

    instruction_pressure = (
        instructions is not None and instructions > LEGACY_BANK_SIZE
    )
    value_pressure = (
        value_slots is not None
        and any(
            count is not None and count > value_slots
            for count in (results, registers, max_registers_per_function)
        )
    )

    block_comparison = {
        "host_oracle_blocks": blocks,
        "host_oracle_max_blocks_per_function": max_blocks_per_function,
        "stage1_structural_blocks": stage1_structural_blocks,
        "compact_stage1_capacity": COMPACT_BLOCK_CAPACITY,
        "classification": "REPRESENTATION_NOT_COMPARABLE",
        "reason": (
            "Host typed basic blocks and the current Stage1 structural block lane are "
            "not proven one-to-one. A larger host count does not authorize expanding "
            "Stage1 banks; the native Stage1 structural measurement must qualify its "
            "own representation."
        ),
    }
    if stage1_structural_blocks is not None:
        block_comparison["stage1_capacity_headroom"] = (
            COMPACT_BLOCK_CAPACITY - stage1_structural_blocks
        )
        block_comparison["stage1_capacity_fits_measurement"] = (
            0 <= stage1_structural_blocks <= COMPACT_BLOCK_CAPACITY
        )

    storage = {
        "blocks": block_comparison,
        "instructions": {
            "host_oracle_instructions": instructions,
            "host_oracle_max_instructions_per_function": max_instructions_per_function,
            "legacy_single_bank_size": LEGACY_BANK_SIZE,
            "classification": (
                "STREAM_OR_REUSE_REQUIRED"
                if instruction_pressure
                else "FIXED_BANK_PLAUSIBLE"
            ),
            "reason": (
                "Semantic instruction ordering/def-use must use the streaming contract; "
                "arbitrary full-module fixed-array expansion is forbidden."
            ),
        },
        "semantic_values": {
            "host_oracle_registers": registers,
            "host_oracle_instruction_results": results,
            "host_oracle_max_registers_per_function": max_registers_per_function,
            "current_value_physical_slots": value_slots,
            "classification": (
                "STREAM_OR_REUSE_REQUIRED"
                if value_pressure
                else "FIXED_BANK_PLAUSIBLE"
            ),
            "reason": (
                "If the host oracle scale exceeds current value slots, Stage1 must not "
                "allocate a larger full-module value matrix by calibration. Measure exact "
                "Stage1 semantic materialization and prefer per-function lifetime/reuse or "
                "serialized definitions where correctness permits."
            ),
        },
        "local_storage_metadata": {
            "host_oracle_memory_objects": memory_objects,
            "classification": "REPRESENTATION_NOT_COMPARABLE",
            "reason": (
                "Host memory objects are a scale signal only; Stage1 local records and host "
                "memory objects are not yet proven to have identical cardinality."
            ),
        },
    }

    guards = {
        "oracle_is_explicitly_non_stage1": oracle_status
        == "MEASURED_HOST_IR_ORACLE_NOT_STAGE1_EVIDENCE",
        "value_contract_forbids_silent_reinterpretation": value_storage.get(
            "silent_reinterpretation_allowed"
        ) is False,
        "no_host_count_promotes_stage1": True,
    }

    return {
        "schema": "s3.selfhost.stage1-ir-storage-topology-audit.v1",
        "status": (
            "STATIC_IR_STORAGE_TOPOLOGY_PASS"
            if all(guards.values())
            else "STATIC_IR_STORAGE_TOPOLOGY_RECONCILE"
        ),
        "native_evidence": False,
        "canonical_source_mutated": False,
        "host_oracle_status": oracle_status,
        "storage": storage,
        "guards": guards,
        "decision_rules": [
            "Never expand Stage1 arrays solely because a host-oracle count is larger.",
            "Use native Stage1 measurements for Stage1 representation capacity.",
            "Use the host oracle to choose topology: bounded metadata vs streaming/reuse.",
            "Treat block cardinalities as incomparable until semantic block equivalence is proven.",
            "Treat semantic value pressure as a requirement for exact liveness/reuse/streaming design, not truncation.",
        ],
        "general_emitter": "BLOCKED_IR_SEMANTIC_SURFACES_INCOMPLETE",
        "self_emit": "NOT_AUTHORIZED",
        "stage2": "NOT_AUTHORIZED",
        "stage3": "NOT_AUTHORIZED",
        "t4": "NOT_AUTHORIZED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--value-contract", type=Path, default=DEFAULT_VALUE_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--stage1-structural-blocks", type=int)
    args = parser.parse_args(argv)

    requirements = json.loads(args.requirements.resolve().read_text(encoding="utf-8"))
    value_contract = json.loads(args.value_contract.resolve().read_text(encoding="utf-8"))
    if not isinstance(requirements, dict) or not isinstance(value_contract, dict):
        raise ValueError("audit inputs must be JSON objects")
    if args.stage1_structural_blocks is not None and args.stage1_structural_blocks < 0:
        raise ValueError("stage1 structural block count must be non-negative")

    result = audit(
        requirements,
        value_contract,
        stage1_structural_blocks=args.stage1_structural_blocks,
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
    print(f"BLOCK_TOPOLOGY={result['storage']['blocks']['classification']}")
    print(f"INSTRUCTION_TOPOLOGY={result['storage']['instructions']['classification']}")
    print(f"VALUE_TOPOLOGY={result['storage']['semantic_values']['classification']}")
    print("NATIVE_EVIDENCE=False")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if result["status"] == "STATIC_IR_STORAGE_TOPOLOGY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
