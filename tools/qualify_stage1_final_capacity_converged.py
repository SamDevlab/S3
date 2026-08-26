"""Final Stage1 capacity authority with recursive self-host convergence.

The existing final-capacity engine remains the low-level lane validator.  This
v2 authority first proves that parameter/local capacities converged on the exact
current source and Stage1 artifact, then invokes the lane engine with a private
compatibility view of the contract.  The compatibility view has no standalone
authority and is not written to disk.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.qualify_stage1_final_capacity import (
    DEFAULT_SOURCE,
    FinalCapacityError,
    _load_json,
    finalize_capacity,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "final-capacity-contract.json"
DEFAULT_CONVERGENCE = ROOT / "reports" / "selfhost" / "stage1" / "selfhost-capacity-convergence.json"
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage1" / "stage1-final-capacity.json"


class ConvergedFinalCapacityError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.resolve().read_bytes()).hexdigest()


def _binding(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise ConvergedFinalCapacityError(f"required file is missing: {path}")
    return {"path": str(path), "sha256": _sha(path), "bytes": path.stat().st_size}


def validate_convergence(
    document: dict[str, Any],
    *,
    source: Path,
    stage1: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    dependency = contract.get("selfhost_capacity_convergence_dependency")
    if not isinstance(dependency, dict):
        raise ConvergedFinalCapacityError("final-capacity v2 contract lacks convergence dependency")
    if document.get("schema") != dependency.get("schema"):
        raise ConvergedFinalCapacityError("self-host capacity convergence schema mismatch")
    if document.get("status") != dependency.get("required_status"):
        raise ConvergedFinalCapacityError("self-host capacity convergence status is not PASS")
    qualification = document.get("qualification")
    if not isinstance(qualification, dict):
        raise ConvergedFinalCapacityError("convergence report lacks qualification")
    required_qualification = dependency.get("required_qualification")
    if not isinstance(required_qualification, dict):
        raise ConvergedFinalCapacityError("convergence dependency qualification policy is malformed")
    for key, expected in required_qualification.items():
        if qualification.get(key) != expected:
            raise ConvergedFinalCapacityError(
                f"convergence qualification {key!r} must be {expected!r}"
            )

    source_binding = _binding(source)
    stage1_binding = _binding(stage1)
    reported_source = document.get("canonical_source")
    reported_stage1 = document.get("stage1")
    if not isinstance(reported_source, dict) or not isinstance(reported_stage1, dict):
        raise ConvergedFinalCapacityError("convergence report lacks source/Stage1 bindings")
    if (
        reported_source.get("sha256") != source_binding["sha256"]
        or reported_source.get("bytes") != source_binding["bytes"]
    ):
        raise ConvergedFinalCapacityError("convergence report is stale for current source")
    if (
        reported_stage1.get("sha256") != stage1_binding["sha256"]
        or reported_stage1.get("bytes") != stage1_binding["bytes"]
    ):
        raise ConvergedFinalCapacityError("convergence report is bound to a different Stage1 artifact")

    repeated = document.get("repeated_native_measurements")
    if not isinstance(repeated, dict):
        raise ConvergedFinalCapacityError("convergence report lacks repeated native measurements")
    if repeated.get("count", 0) < 2:
        raise ConvergedFinalCapacityError("convergence report needs at least two native measurements")
    for key in ("same_source", "same_stage1_artifact", "same_required_counts"):
        if repeated.get(key) is not True:
            raise ConvergedFinalCapacityError(f"convergence repeated measurement {key} must be true")
    if repeated.get("overflow_or_truncation") is not False:
        raise ConvergedFinalCapacityError("convergence observed overflow/truncation")

    return {
        "source": source_binding,
        "stage1": stage1_binding,
        "status": document["status"],
        "native_measurement_count": repeated["count"],
    }


def _legacy_engine_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Return an in-memory compatibility policy for the v1 lane engine only."""
    compat = copy.deepcopy(contract)
    compat["schema"] = "s3.selfhost.stage1-final-capacity-contract.v1"
    compat.pop("selfhost_capacity_convergence_dependency", None)
    requirements = compat.get("measurement_requirements")
    if isinstance(requirements, dict):
        requirements.pop("selfhost_capacity_convergence_consumed", None)
    return compat


def finalize_converged_capacity(
    measurement: dict[str, Any],
    convergence: dict[str, Any],
    *,
    source_path: Path,
    stage1_path: Path,
    contract: dict[str, Any],
    measurement_sha256: str | None,
    convergence_sha256: str | None,
) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.stage1-final-capacity-contract.v2":
        raise ConvergedFinalCapacityError("final capacity authority requires contract v2")
    binding = validate_convergence(
        convergence,
        source=source_path,
        stage1=stage1_path,
        contract=contract,
    )
    if measurement.get("selfhost_capacity_convergence_consumed") is not True:
        raise ConvergedFinalCapacityError(
            "native final-capacity measurement must declare selfhost_capacity_convergence_consumed=true"
        )

    try:
        result = finalize_capacity(
            measurement,
            source_path=source_path,
            stage1_path=stage1_path,
            contract=_legacy_engine_contract(contract),
            measurement_sha256=measurement_sha256,
        )
    except FinalCapacityError as error:
        raise ConvergedFinalCapacityError(str(error)) from error

    result["authority"] = "STAGE1_FINAL_CAPACITY_V2_CONVERGED"
    result["contract_schema"] = contract["schema"]
    result["selfhost_capacity_convergence"] = {
        "schema": convergence["schema"],
        "sha256": convergence_sha256,
        "status": binding["status"],
        "same_canonical_source": True,
        "same_stage1_artifact": True,
        "native_measurement_count": binding["native_measurement_count"],
    }
    result["measurement"]["selfhost_capacity_convergence_consumed"] = True
    result["qualification"]["all_capacities_no_truncation"] = "PASS"
    result["qualification"]["selfhost_capacity_convergence"] = "PASS"
    result["qualification"]["stage2_allowed_from_this_report_alone"] = False
    result["qualification"]["full_self_hosting"] = False
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--convergence", type=Path, default=DEFAULT_CONVERGENCE)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        measurement_path = args.measurement.resolve()
        convergence_path = args.convergence.resolve()
        result = finalize_converged_capacity(
            _load_json(measurement_path, "native capacity measurement"),
            _load_json(convergence_path, "self-host capacity convergence"),
            source_path=args.source,
            stage1_path=args.stage1,
            contract=_load_json(args.contract.resolve(), "capacity contract"),
            measurement_sha256=_sha(measurement_path),
            convergence_sha256=_sha(convergence_path),
        )
    except (OSError, FinalCapacityError, ConvergedFinalCapacityError) as error:
        parser.exit(2, f"Stage1 converged final capacity blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print("FINAL_CAPACITY=PASS")
    print("SELFHOST_CAPACITY_CONVERGENCE=PASS")
    print(f"LANES={result['summary']['lane_count']}")
    print(f"MINIMUM_HEADROOM={result['summary']['minimum_headroom']}")
    print("STAGE2_ALLOWED_FROM_THIS_REPORT_ALONE=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
