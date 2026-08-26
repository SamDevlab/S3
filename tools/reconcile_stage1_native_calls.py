"""Reconcile native Stage1 call capacity with current hosted semantic call oracles.

Only the native measurement is physical-capacity authority.  AST/O0 counts are
source-bound diagnostics used to catch stale evidence, not equality targets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.audit_stage1_reference_current_calls import validate_inventory_for_source


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_HOSTED = ROOT / "reports" / "selfhost" / "stage1" / "reference-current-call-inventory.json"
DEFAULT_CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "native-call-reconciliation-contract.json"
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage1" / "stage1-native-call-reconciliation.json"


class NativeCallReconciliationError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise NativeCallReconciliationError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise NativeCallReconciliationError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise NativeCallReconciliationError(f"{label} must be a JSON object")
    return value


def _int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise NativeCallReconciliationError(f"{label} must be an integer >= 0")
    return value


def _bind(document: dict[str, Any], key: str, path: Path, runtime_key: str) -> dict[str, Any]:
    section = document.get(key)
    if not isinstance(section, dict):
        raise NativeCallReconciliationError(f"native measurement lacks {key}")
    actual_sha = _sha(path)
    actual_bytes = path.stat().st_size
    if section.get("sha256") != actual_sha or section.get("bytes") != actual_bytes:
        raise NativeCallReconciliationError(f"native measurement {key} binding is stale")
    if section.get(runtime_key) != actual_sha:
        raise NativeCallReconciliationError(f"native measurement {key} runtime binding mismatch")
    return {"path": str(path.resolve()), "sha256": actual_sha, "bytes": actual_bytes}


def _lane(raw: Any, *, label: str, expected_high_water: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise NativeCallReconciliationError(f"{label} measurement is missing")
    high_water = _int(raw.get("high_water"), f"{label}.high_water")
    capacity = _int(raw.get("capacity"), f"{label}.capacity")
    if high_water != expected_high_water:
        raise NativeCallReconciliationError(
            f"{label} high-water disagrees with native audit: {high_water} != {expected_high_water}"
        )
    if high_water > capacity:
        raise NativeCallReconciliationError(f"{label} exceeds capacity: {high_water}>{capacity}")
    max_index = raw.get("max_written_index")
    if high_water == 0:
        if max_index is not None:
            raise NativeCallReconciliationError(f"{label} high_water=0 but max_written_index is set")
    else:
        max_index = _int(max_index, f"{label}.max_written_index")
        if max_index != high_water - 1:
            raise NativeCallReconciliationError(
                f"{label} dense high-water mismatch: max={max_index} expected={high_water - 1}"
            )
    if raw.get("overflow_attempted") is not False:
        raise NativeCallReconciliationError(f"{label} reports canonical overflow attempt")
    if raw.get("truncation_detected") is not False:
        raise NativeCallReconciliationError(f"{label} reports truncation")
    if raw.get("guard_probe") != "PASS":
        raise NativeCallReconciliationError(f"{label} overflow guard probe is not PASS")
    return {
        "high_water": high_water,
        "capacity": capacity,
        "headroom": capacity - high_water,
        "max_written_index": max_index,
        "overflow_attempted": False,
        "truncation_detected": False,
        "guard_probe": "PASS",
    }


def reconcile(
    measurement: dict[str, Any],
    hosted: dict[str, Any],
    *,
    source_path: Path,
    stage1_path: Path,
    contract: dict[str, Any],
    measurement_sha256: str | None = None,
    hosted_sha256: str | None = None,
) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.stage1-native-call-reconciliation-contract.v1":
        raise NativeCallReconciliationError("native call reconciliation contract schema mismatch")
    if measurement.get("schema") != contract.get("measurement_schema"):
        raise NativeCallReconciliationError("native call measurement schema mismatch")
    if hosted.get("schema") != contract.get("hosted_inventory_schema"):
        raise NativeCallReconciliationError("hosted current call inventory schema mismatch")

    source_path = source_path.resolve()
    stage1_path = stage1_path.resolve()
    source_bytes = source_path.read_bytes()
    try:
        validate_inventory_for_source(hosted, source_bytes)
    except Exception as error:
        raise NativeCallReconciliationError(str(error)) from error

    platform = measurement.get("platform")
    if not isinstance(platform, dict) or platform.get("system") != "Linux" or str(platform.get("machine", "")).lower() not in {"x86_64", "amd64"}:
        raise NativeCallReconciliationError("native call measurement must be Linux x86-64")

    for key, expected in contract.get("measurement_requirements", {}).items():
        if measurement.get(key) is not expected:
            raise NativeCallReconciliationError(f"native call measurement {key} must be {expected!r}")

    source_binding = _bind(measurement, "canonical_source", source_path, "runtime_input_sha256")
    stage1_binding = _bind(measurement, "stage1", stage1_path, "executed_sha256")
    if hosted.get("source", {}).get("sha256") != source_binding["sha256"]:
        raise NativeCallReconciliationError("hosted/native call evidence is bound to different source SHA")

    audit = measurement.get("audit")
    if not isinstance(audit, dict):
        raise NativeCallReconciliationError("native call measurement lacks audit counters")
    call_count = _int(audit.get("ir_call_count"), "audit.ir_call_count")
    argument_count = _int(audit.get("ir_call_arg_pool_count"), "audit.ir_call_arg_pool_count")
    internal = _int(audit.get("ir_internal_call_count"), "audit.ir_internal_call_count")
    foreign = _int(audit.get("ir_foreign_call_count"), "audit.ir_foreign_call_count")
    if internal + foreign != call_count:
        raise NativeCallReconciliationError(
            f"native call classification is incomplete: internal+foreign={internal + foreign} total={call_count}"
        )

    calls = _lane(measurement.get("call_records"), label="call_records", expected_high_water=call_count)
    arguments = _lane(measurement.get("call_arguments"), label="call_arguments", expected_high_water=argument_count)

    ast = hosted.get("ast", {})
    ir = hosted.get("o0_ir", {})
    return {
        "schema": contract["output_schema"],
        "status": "PASS_NATIVE_CURRENT_SOURCE_CALL_RECONCILIATION",
        "native_evidence": True,
        "canonical_source": source_binding,
        "stage1": stage1_binding,
        "platform": {"system": platform["system"], "machine": platform["machine"]},
        "inputs": {
            "native_measurement_sha256": measurement_sha256,
            "hosted_inventory_sha256": hosted_sha256,
            "hosted_inventory_schema": hosted["schema"],
        },
        "native": {
            "audit": {
                "ir_call_count": call_count,
                "ir_call_arg_pool_count": argument_count,
                "ir_internal_call_count": internal,
                "ir_foreign_call_count": foreign,
            },
            "call_records": calls,
            "call_arguments": arguments,
            "all_call_slices_in_range": True,
            "all_argument_slices_in_range": True,
            "all_recorded_arguments_addressable": True,
        },
        "hosted_diagnostics": {
            "ast_call_expressions": ast.get("total_call_expressions"),
            "ast_argument_occurrences": ast.get("total_argument_occurrences"),
            "o0_ir_call_instructions": ir.get("total_call_instructions"),
            "o0_ir_call_operands": ir.get("total_operand_uses"),
            "native_minus_ast_calls": call_count - int(ast.get("total_call_expressions", 0)),
            "native_minus_o0_ir_calls": call_count - int(ir.get("total_call_instructions", 0)),
            "native_args_minus_ast_arguments": argument_count - int(ast.get("total_argument_occurrences", 0)),
            "native_args_minus_o0_ir_operands": argument_count - int(ir.get("total_operand_uses", 0)),
            "equality_required": False,
            "physical_capacity_selected_from_hosted_oracle": False,
        },
        "historical_closure": {
            "calls_656_arguments_736_reused": False,
            "current_native_calls": call_count,
            "current_native_arguments": argument_count,
        },
        "qualification": {
            "native_call_capacity": "PASS",
            "native_call_argument_capacity": "PASS",
            "semantic_call_linkage_complete_from_this_report_alone": False,
            "stage1_certified_for_stage2": False,
            "full_self_hosting": False,
            "next": "USE_CURRENT_NATIVE_CALL_HIGH_WATER_IN_FINAL_CAPACITY_AND_COMPLETE_TYPED_CALL_LINKAGE_IN_SEMANTIC_IR",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--hosted", type=Path, default=DEFAULT_HOSTED)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        measurement_path = args.measurement.resolve()
        hosted_path = args.hosted.resolve()
        result = reconcile(
            _load(measurement_path, "native call measurement"),
            _load(hosted_path, "hosted call inventory"),
            source_path=args.source,
            stage1_path=args.stage1,
            contract=_load(args.contract.resolve(), "native call reconciliation contract"),
            measurement_sha256=_sha(measurement_path),
            hosted_sha256=_sha(hosted_path),
        )
    except (OSError, NativeCallReconciliationError) as error:
        parser.exit(2, f"Stage1 native call reconciliation blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"NATIVE_CALLS={result['native']['audit']['ir_call_count']}")
    print(f"NATIVE_CALL_ARGUMENTS={result['native']['audit']['ir_call_arg_pool_count']}")
    print("HISTORICAL_656_736_REUSED=False")
    print("SEMANTIC_CALL_LINKAGE_COMPLETE_FROM_THIS_REPORT_ALONE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
