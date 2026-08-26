"""Qualify recursive Stage1 parameter/local capacity convergence.

The Stage1 compiler is its own future input, so adding capacity metadata can
itself increase the number of parameters/locals that must be represented.  This
gate prevents stale counts from being promoted: it independently recounts the
exact source AST, re-hashes the source and Stage1 artifact, and requires at
least two identical native measurements on those exact bytes.

This is capacity evidence only.  PASS never authorizes Stage2 by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

from bootstrap.s3.parser import parse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "selfhost-capacity-convergence-contract.json"
)
DEFAULT_MEASUREMENT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "selfhost-capacity-convergence-measurement.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "selfhost-capacity-convergence.json"
)


class CapacityConvergenceError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.resolve().read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CapacityConvergenceError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise CapacityConvergenceError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise CapacityConvergenceError(f"{label} must be a JSON object")
    return value


def _source_inventory(source: Path) -> dict[str, Any]:
    source = source.resolve()
    data = source.read_bytes()
    try:
        program = parse(data.decode("utf-8"))
    except (UnicodeDecodeError, Exception) as error:
        # Preserve parser failures as a gate failure, not as a fallback count.
        raise CapacityConvergenceError(f"cannot parse exact Stage1 source: {error}") from error

    functions = getattr(program, "functions", None)
    if not isinstance(functions, list):
        raise CapacityConvergenceError("parsed program does not expose a function list")
    parameters_total = 0
    for function in functions:
        parameters = getattr(function, "parameters", None)
        if parameters is None:
            raise CapacityConvergenceError("function does not expose parameters")
        parameters_total += len(parameters)

    walk = getattr(program, "walk", None)
    if not callable(walk):
        raise CapacityConvergenceError("parsed program does not expose walk()")
    local_declarations_total = sum(
        1 for node in walk() if node.__class__.__name__ == "VariableDeclaration"
    )
    return {
        "path": str(source),
        "sha256": _sha(data),
        "bytes": len(data),
        "functions_total": len(functions),
        "parameters_total": parameters_total,
        "local_declarations_total": local_declarations_total,
    }


def _artifact_binding(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise CapacityConvergenceError(f"Stage1 artifact is missing: {path}")
    data = path.read_bytes()
    return {"path": str(path), "sha256": _sha(data), "bytes": len(data)}


def _require_bool(document: dict[str, Any], key: str, expected: bool) -> None:
    if document.get(key) is not expected:
        raise CapacityConvergenceError(
            f"measurement field {key!r} must be {expected!r}; actual={document.get(key)!r}"
        )


def _validate_lane(
    name: str,
    lane: dict[str, Any],
    *,
    expected_scope: str,
    expected_required: int,
) -> dict[str, Any]:
    if lane.get("scope") != expected_scope:
        raise CapacityConvergenceError(
            f"{name} lane scope must be {expected_scope!r}"
        )
    required = lane.get("required")
    capacity = lane.get("capacity")
    headroom = lane.get("headroom")
    if not isinstance(required, int) or required < 0:
        raise CapacityConvergenceError(f"{name} required must be a non-negative integer")
    if required != expected_required:
        raise CapacityConvergenceError(
            f"{name} required count is stale: native={required} source={expected_required}"
        )
    if not isinstance(capacity, int) or capacity < required:
        raise CapacityConvergenceError(
            f"{name} capacity {capacity!r} is smaller than required {required}"
        )
    if headroom != capacity - required:
        raise CapacityConvergenceError(
            f"{name} headroom must equal capacity-required"
        )
    if lane.get("overflow_attempted") is not False:
        raise CapacityConvergenceError(f"{name} overflow_attempted must be false")
    if lane.get("truncation_detected") is not False:
        raise CapacityConvergenceError(f"{name} truncation_detected must be false")
    if lane.get("guard_probe") != "PASS":
        raise CapacityConvergenceError(f"{name} overflow guard probe must PASS")

    policy = lane.get("selection_policy")
    if policy == "EXACT":
        if capacity != required:
            raise CapacityConvergenceError(
                f"{name} EXACT capacity must equal required: capacity={capacity} required={required}"
            )
        bank_layout: list[int] = []
    elif policy == "BANKED":
        raw_layout = lane.get("bank_layout")
        if (
            not isinstance(raw_layout, list)
            or not raw_layout
            or any(not isinstance(item, int) or item <= 0 for item in raw_layout)
        ):
            raise CapacityConvergenceError(f"{name} BANKED lane requires positive bank_layout")
        bank_layout = list(raw_layout)
        if sum(bank_layout) != capacity:
            raise CapacityConvergenceError(
                f"{name} bank layout sum does not equal physical capacity"
            )
        if lane.get("dispatch_proof") != "PASS":
            raise CapacityConvergenceError(f"{name} bank dispatch proof must PASS")
        if lane.get("roundtrip_proof") != "PASS":
            raise CapacityConvergenceError(f"{name} bank roundtrip proof must PASS")
    else:
        raise CapacityConvergenceError(
            f"{name} selection_policy must be EXACT or BANKED"
        )

    return {
        "scope": expected_scope,
        "required": required,
        "capacity": capacity,
        "headroom": capacity - required,
        "selection_policy": policy,
        "bank_layout": bank_layout,
        "guard_probe": "PASS",
    }


def qualify(
    *,
    source: Path,
    stage1: Path,
    measurement_path: Path,
    contract_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    contract = _load_json(contract_path, "capacity convergence contract")
    if contract.get("schema") != "s3.selfhost.stage1-selfhost-capacity-convergence-contract.v1":
        raise CapacityConvergenceError("capacity convergence contract schema mismatch")
    measurement = _load_json(measurement_path, "capacity convergence measurement")
    if measurement.get("schema") != contract.get("measurement_schema"):
        raise CapacityConvergenceError("capacity convergence measurement schema mismatch")

    inventory = _source_inventory(source)
    artifact = _artifact_binding(stage1)
    canonical = measurement.get("canonical_source")
    measured_stage1 = measurement.get("stage1")
    if not isinstance(canonical, dict) or not isinstance(measured_stage1, dict):
        raise CapacityConvergenceError("measurement lacks canonical_source/stage1 bindings")
    if canonical.get("sha256") != inventory["sha256"] or canonical.get("bytes") != inventory["bytes"]:
        raise CapacityConvergenceError("measurement is bound to stale source bytes")
    if measured_stage1.get("sha256") != artifact["sha256"] or measured_stage1.get("bytes") != artifact["bytes"]:
        raise CapacityConvergenceError("measurement is bound to a different Stage1 artifact")

    platform_doc = measurement.get("platform")
    if not isinstance(platform_doc, dict):
        raise CapacityConvergenceError("measurement lacks platform")
    if platform_doc.get("system") != "Linux" or str(platform_doc.get("machine", "")).lower() not in {"x86_64", "amd64"}:
        raise CapacityConvergenceError("measurement must be native Linux x86-64")

    flags = measurement.get("measurement")
    if not isinstance(flags, dict):
        raise CapacityConvergenceError("measurement lacks measurement flags")
    _require_bool(flags, "native_evidence", True)
    _require_bool(flags, "projection_substituted_for_native_measurement", False)
    _require_bool(flags, "source_mutated_after_measurement", False)
    _require_bool(flags, "capacity_mutated_after_measurement", False)
    _require_bool(flags, "repeated_required_counts_identical", True)

    lanes = measurement.get("lanes")
    if not isinstance(lanes, dict):
        raise CapacityConvergenceError("measurement lacks lane map")
    parameters = lanes.get("parameters")
    locals_lane = lanes.get("locals")
    if not isinstance(parameters, dict) or not isinstance(locals_lane, dict):
        raise CapacityConvergenceError("measurement must contain parameters and locals lanes")
    validated_parameters = _validate_lane(
        "parameters",
        parameters,
        expected_scope="ALL_DECLARED_PARAMETERS",
        expected_required=int(inventory["parameters_total"]),
    )
    validated_locals = _validate_lane(
        "locals",
        locals_lane,
        expected_scope="ALL_VARIABLE_DECLARATIONS",
        expected_required=int(inventory["local_declarations_total"]),
    )

    runs = measurement.get("native_runs")
    if not isinstance(runs, list) or len(runs) < 2:
        raise CapacityConvergenceError("at least two native convergence measurements are required")
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise CapacityConvergenceError(f"native run {index} is malformed")
        expected = {
            "source_sha256": inventory["sha256"],
            "stage1_sha256": artifact["sha256"],
            "parameters_required": inventory["parameters_total"],
            "locals_required": inventory["local_declarations_total"],
        }
        for key, value in expected.items():
            if run.get(key) != value:
                raise CapacityConvergenceError(
                    f"native run {index} field {key!r} is stale or nondeterministic: expected={value!r} actual={run.get(key)!r}"
                )
        if run.get("overflow_attempted") is not False or run.get("truncation_detected") is not False:
            raise CapacityConvergenceError(f"native run {index} observed overflow/truncation")

    result = {
        "schema": contract["output_schema"],
        "status": "PASS_SELFHOST_CAPACITY_CONVERGENCE",
        "canonical_source": inventory,
        "stage1": artifact,
        "platform": platform_doc,
        "native_evidence": True,
        "independent_source_recount": {
            "parameters_total": inventory["parameters_total"],
            "local_declarations_total": inventory["local_declarations_total"],
        },
        "lanes": {
            "parameters": validated_parameters,
            "locals": validated_locals,
        },
        "repeated_native_measurements": {
            "count": len(runs),
            "same_source": True,
            "same_stage1_artifact": True,
            "same_required_counts": True,
            "overflow_or_truncation": False,
        },
        "qualification": {
            "selfhost_capacity_convergence": "PASS",
            "stale_capacity_evidence": False,
            "final_capacity_gate_allowed": True,
            "stage2_allowed_from_this_report_alone": False,
            "full_self_hosting": False,
            "next": "RUN_STAGE1_FINAL_CAPACITY_GATE_WITH_THIS_EXACT_SOURCE_AND_ARTIFACT",
        },
    }
    destination = report_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--measurement", type=Path, default=DEFAULT_MEASUREMENT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        result = qualify(
            source=args.source,
            stage1=args.stage1,
            measurement_path=args.measurement,
            contract_path=args.contract,
            report_path=args.report,
        )
    except (OSError, CapacityConvergenceError) as error:
        parser.exit(2, f"Stage1 self-host capacity convergence blocked: {error}\n")
    print(f"REPORT={args.report.resolve()}")
    print(f"STATUS={result['status']}")
    print(f"SOURCE_SHA256={result['canonical_source']['sha256']}")
    print(f"PARAMETERS_REQUIRED={result['lanes']['parameters']['required']}")
    print(f"PARAMETERS_CAPACITY={result['lanes']['parameters']['capacity']}")
    print(f"LOCALS_REQUIRED={result['lanes']['locals']['required']}")
    print(f"LOCALS_CAPACITY={result['lanes']['locals']['capacity']}")
    print(f"NATIVE_RUNS={result['repeated_native_measurements']['count']}")
    print("STAGE2_ALLOWED_FROM_THIS_REPORT_ALONE=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
