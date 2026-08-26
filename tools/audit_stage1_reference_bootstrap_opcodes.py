"""Reconcile canonical Stage0 typed-IR opcodes with Stage1 emitter requirements.

Hosted/static evidence only.  The reference IR defines semantics that must be
accounted for, but it does not dictate Stage1's physical IR layout.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bootstrap.s3.pipeline import compile_source
from tools.audit_stage1_reference_semantic_value_inventory import (
    InventoryError,
    _canonical_source,
    _sha256,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-bootstrap-opcode-contract.json"
)
DEFAULT_LEGACY = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "general-emitter-required-ops.json"
)
DEFAULT_MANIFEST = ROOT / "selfhost" / "compiler" / "compiler-sources.json"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-bootstrap-opcode-inventory.json"
)


class OpcodeAuditError(RuntimeError):
    pass


def _location_dict(instruction) -> dict[str, Any] | None:
    location = instruction.location
    if location is None:
        return None
    try:
        return location.to_dict()
    except AttributeError:
        return {
            "offset": getattr(location, "offset", None),
            "line": getattr(location, "line", None),
            "column": getattr(location, "column", None),
        }


def _legacy_shapes(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    shapes = document.get("required_shapes")
    if not isinstance(shapes, list):
        raise OpcodeAuditError("legacy emitter report lacks required_shapes")
    result: dict[str, dict[str, Any]] = {}
    for item in shapes:
        if not isinstance(item, dict) or not isinstance(item.get("shape"), str):
            raise OpcodeAuditError("legacy emitter required_shapes entry is malformed")
        result[item["shape"]] = item
    return result


def audit(
    contract: dict[str, Any],
    legacy: dict[str, Any],
    manifest_path: Path,
) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.reference-bootstrap-opcode-contract.v1":
        raise OpcodeAuditError("reference bootstrap opcode contract schema mismatch")
    capabilities = contract.get("opcode_capabilities")
    historical_mapping = contract.get("historical_shape_mapping")
    if not isinstance(capabilities, dict) or not isinstance(historical_mapping, dict):
        raise OpcodeAuditError("contract lacks opcode mappings")

    source_path, source_bytes, manifest = _canonical_source(manifest_path.resolve())
    compilation = compile_source(source_bytes.decode("utf-8"), optimization="O0")
    ir, _ = compilation.require_ordinary_artifacts()
    histogram: Counter[str] = Counter()
    operand_uses: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    callee_histogram: Counter[str] = Counter()
    external_names = {function.name for function in ir.functions if function.external}
    internal_call_count = 0
    foreign_call_count = 0

    for function in ir.functions:
        for block in function.blocks:
            for instruction in block.instructions:
                opcode = instruction.opcode.value
                histogram[opcode] += 1
                operand_uses[opcode] += len(instruction.operands)
                if len(samples[opcode]) < 3:
                    location = _location_dict(instruction)
                    samples[opcode].append(
                        {
                            "function": function.name,
                            "block": block.name,
                            "source": location,
                        }
                    )
                if opcode == "call" and instruction.callee is not None:
                    callee_histogram[instruction.callee] += 1
                    if instruction.callee in external_names:
                        foreign_call_count += 1
                    else:
                        internal_call_count += 1

    observed = sorted(histogram)
    unmapped = [opcode for opcode in observed if opcode not in capabilities]
    legacy_shapes = _legacy_shapes(legacy)
    zero_conflicts: list[dict[str, Any]] = []
    missing_historical_shapes: list[dict[str, Any]] = []
    for opcode in observed:
        legacy_shape = historical_mapping.get(opcode)
        if legacy_shape is None:
            missing_historical_shapes.append(
                {
                    "opcode": opcode,
                    "count": histogram[opcode],
                    "required_capability": capabilities.get(opcode),
                }
            )
            continue
        # Composite mapping labels intentionally do not pretend a single
        # historical aggregate counter can classify internal/foreign calls.
        if legacy_shape not in legacy_shapes:
            continue
        item = legacy_shapes[legacy_shape]
        historical_count = item.get("count")
        if historical_count == 0 and histogram[opcode] > 0:
            zero_conflicts.append(
                {
                    "opcode": opcode,
                    "reference_count": histogram[opcode],
                    "historical_shape": legacy_shape,
                    "historical_count": historical_count,
                    "historical_status": item.get("status"),
                    "historical_claim": item.get("ir_representation"),
                }
            )

    stale = bool(unmapped or zero_conflicts or missing_historical_shapes)
    status = (
        "BLOCKED_LEGACY_EMITTER_REQUIREMENTS_STALE"
        if stale
        else "PASS_HOSTED_REFERENCE_OPCODE_RECONCILIATION"
    )
    next_step = (
        "REBASE_GENERAL_EMITTER_REQUIREMENTS_ON_TYPED_REFERENCE_OPCODE_INVENTORY"
        if stale
        else "REQUIRE_NATIVE_STAGE1_IR_AND_EMITTER_COVERAGE_FOR_EVERY_OBSERVED_CAPABILITY"
    )
    return {
        "schema": "s3.selfhost.reference-bootstrap-opcode-inventory.v1",
        "status": status,
        "authority": "HOSTED_REFERENCE_ORACLE_ONLY",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "canonical_source": {
            "path": str(source_path),
            "sha256": _sha256(source_bytes),
            "bytes": len(source_bytes),
            "manifest": manifest,
        },
        "reference_ir": {
            "opcode_histogram": dict(sorted(histogram.items())),
            "operand_use_histogram": dict(sorted(operand_uses.items())),
            "observed_opcodes": observed,
            "required_capabilities": {
                opcode: capabilities.get(opcode) for opcode in observed
            },
            "source_samples": dict(sorted(samples.items())),
            "call_callee_histogram": dict(sorted(callee_histogram.items())),
            "internal_call_count": internal_call_count,
            "foreign_call_count": foreign_call_count,
        },
        "reconciliation": {
            "unmapped_reference_opcodes": unmapped,
            "historical_zero_count_conflicts": zero_conflicts,
            "observed_opcodes_without_historical_shape_mapping": missing_historical_shapes,
            "legacy_emitter_requirements_stale": stale,
            "reference_ir_physical_shape_is_stage1_authority": False,
        },
        "qualification": {
            "general_emitter_certified": False,
            "stage1_certified_for_stage2": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": next_step,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--legacy", type=Path, default=DEFAULT_LEGACY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        contract = json.loads(args.contract.resolve().read_text(encoding="utf-8"))
        legacy = json.loads(args.legacy.resolve().read_text(encoding="utf-8"))
        if not isinstance(contract, dict) or not isinstance(legacy, dict):
            raise OpcodeAuditError("contract and legacy report must be JSON objects")
        result = audit(contract, legacy, args.manifest)
    except (OpcodeAuditError, InventoryError, UnicodeDecodeError, json.JSONDecodeError) as error:
        parser.exit(2, f"reference bootstrap opcode audit blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print("OBSERVED_OPCODES=" + ",".join(result["reference_ir"]["observed_opcodes"]))
    print(f"INTERNAL_CALLS={result['reference_ir']['internal_call_count']}")
    print(f"FOREIGN_CALLS={result['reference_ir']['foreign_call_count']}")
    print(f"UNMAPPED_OPCODES={len(result['reconciliation']['unmapped_reference_opcodes'])}")
    print(f"ZERO_COUNT_CONFLICTS={len(result['reconciliation']['historical_zero_count_conflicts'])}")
    print(f"HISTORICAL_MAPPING_GAPS={len(result['reconciliation']['observed_opcodes_without_historical_shape_mapping'])}")
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
