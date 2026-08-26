"""Finalize native Stage1 capacity evidence for Stage2 certification.

This tool never promotes a projection or an older partial candidate report.  It
consumes a fresh ``s3.selfhost.stage1-capacity-measurement.v1`` document created
while the exact final Stage1 artifact compiles the exact final canonical source,
then independently rebinds the measurement to the source/artifact bytes and
rechecks every bounded lane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" / "final-capacity-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "stage1-final-capacity.json"
)


class FinalCapacityError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FinalCapacityError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise FinalCapacityError(f"{label} is not valid JSON: {path}") from error
    if not isinstance(document, dict):
        raise FinalCapacityError(f"{label} must be a JSON object")
    return document


def _require_bool(document: dict[str, Any], key: str, expected: bool) -> None:
    actual = document.get(key)
    if actual is not expected:
        raise FinalCapacityError(f"{key} must be {expected!r}; got {actual!r}")


def _require_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise FinalCapacityError(f"{label} must be an integer >= {minimum}; got {value!r}")
    return value


def _check_binding(
    document: dict[str, Any],
    *,
    label: str,
    path: Path,
) -> dict[str, Any]:
    entry = document.get(label)
    if not isinstance(entry, dict):
        raise FinalCapacityError(f"measurement lacks {label} binding")
    actual_sha = _sha256(path)
    actual_bytes = path.stat().st_size
    if entry.get("sha256") != actual_sha:
        raise FinalCapacityError(
            f"{label} SHA mismatch: measurement={entry.get('sha256')!r} actual={actual_sha}"
        )
    if entry.get("bytes") != actual_bytes:
        raise FinalCapacityError(
            f"{label} byte-count mismatch: measurement={entry.get('bytes')!r} actual={actual_bytes}"
        )
    runtime_sha = entry.get("runtime_input_sha256" if label == "canonical_source" else "executed_sha256")
    if runtime_sha != actual_sha:
        raise FinalCapacityError(
            f"{label} runtime binding mismatch: runtime={runtime_sha!r} actual={actual_sha}"
        )
    return {"path": str(path.resolve()), "sha256": actual_sha, "bytes": actual_bytes}


def _validate_lane(name: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise FinalCapacityError(f"lane {name!r} must be an object")
    required = _require_int(raw.get("required"), f"lane {name}.required")
    capacity = _require_int(raw.get("capacity"), f"lane {name}.capacity")
    headroom = raw.get("headroom")
    if isinstance(headroom, bool) or not isinstance(headroom, int):
        raise FinalCapacityError(f"lane {name}.headroom must be an integer")
    if required > capacity:
        raise FinalCapacityError(
            f"lane {name} exceeds capacity: required={required} capacity={capacity}"
        )
    expected_headroom = capacity - required
    if headroom != expected_headroom or headroom < 0:
        raise FinalCapacityError(
            f"lane {name} headroom mismatch: reported={headroom} expected={expected_headroom}"
        )

    sparse = raw.get("sparse")
    if not isinstance(sparse, bool):
        raise FinalCapacityError(f"lane {name}.sparse must be boolean")
    max_index = raw.get("max_written_index")
    if required == 0:
        if max_index is not None:
            raise FinalCapacityError(f"lane {name} required=0 but has max_written_index={max_index!r}")
    else:
        max_index = _require_int(max_index, f"lane {name}.max_written_index")
        if max_index >= capacity:
            raise FinalCapacityError(
                f"lane {name} wrote out of range index {max_index} for capacity {capacity}"
            )
        if not sparse and max_index != required - 1:
            raise FinalCapacityError(
                f"lane {name} dense high-water mismatch: max={max_index} required={required}"
            )

    if raw.get("overflow_attempted") is not False:
        raise FinalCapacityError(f"lane {name} reports canonical overflow attempt")
    if raw.get("truncation_detected") is not False:
        raise FinalCapacityError(f"lane {name} reports truncation")
    if raw.get("guard_probe") != "PASS":
        raise FinalCapacityError(f"lane {name} lacks PASS overflow-guard probe")

    dispatch = raw.get("dispatch_proof")
    roundtrip = raw.get("roundtrip_proof")
    allowed = {"PASS", "NOT_BANKED"}
    if dispatch not in allowed or roundtrip not in allowed:
        raise FinalCapacityError(
            f"lane {name} has invalid bank proof values dispatch={dispatch!r} roundtrip={roundtrip!r}"
        )
    if (dispatch == "PASS") != (roundtrip == "PASS"):
        raise FinalCapacityError(
            f"lane {name} banked dispatch/roundtrip proofs must agree"
        )

    provenance = raw.get("provenance")
    if not isinstance(provenance, str) or not provenance.strip():
        raise FinalCapacityError(f"lane {name} lacks native provenance")

    return {
        "required": required,
        "capacity": capacity,
        "headroom": headroom,
        "max_written_index": max_index,
        "sparse": sparse,
        "overflow_attempted": False,
        "truncation_detected": False,
        "guard_probe": "PASS",
        "dispatch_proof": dispatch,
        "roundtrip_proof": roundtrip,
        "provenance": provenance,
    }


def finalize_capacity(
    measurement: dict[str, Any],
    *,
    source_path: Path,
    stage1_path: Path,
    contract: dict[str, Any],
    measurement_sha256: str | None = None,
) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.stage1-final-capacity-contract.v1":
        raise FinalCapacityError("final capacity contract schema mismatch")
    if measurement.get("schema") != contract.get("measurement_schema"):
        raise FinalCapacityError("native capacity measurement schema mismatch")

    platform = measurement.get("platform")
    if not isinstance(platform, dict):
        raise FinalCapacityError("measurement lacks platform")
    expected_platform = contract.get("required_platform")
    if platform.get("system") != expected_platform.get("system"):
        raise FinalCapacityError("final capacity measurement must be native Linux")
    if str(platform.get("machine", "")).lower() not in {"x86_64", "amd64"}:
        raise FinalCapacityError("final capacity measurement must be x86-64")

    requirements = contract.get("measurement_requirements")
    if not isinstance(requirements, dict):
        raise FinalCapacityError("capacity contract lacks measurement requirements")
    for key, expected in requirements.items():
        _require_bool(measurement, key, bool(expected))

    source_path = source_path.resolve()
    stage1_path = stage1_path.resolve()
    if not source_path.is_file():
        raise FinalCapacityError(f"canonical source is missing: {source_path}")
    if not stage1_path.is_file():
        raise FinalCapacityError(f"Stage1 artifact is missing: {stage1_path}")
    canonical = _check_binding(measurement, label="canonical_source", path=source_path)
    stage1 = _check_binding(measurement, label="stage1", path=stage1_path)

    inventory = measurement.get("bounded_lane_inventory")
    if not isinstance(inventory, dict):
        raise FinalCapacityError("measurement lacks bounded_lane_inventory")
    if inventory.get("complete") is not True:
        raise FinalCapacityError("bounded lane inventory is not complete")
    total_sites = _require_int(
        inventory.get("bounded_write_sites_total"),
        "bounded_lane_inventory.bounded_write_sites_total",
    )
    accounted_sites = _require_int(
        inventory.get("accounted_write_sites"),
        "bounded_lane_inventory.accounted_write_sites",
    )
    if total_sites != accounted_sites:
        raise FinalCapacityError(
            f"bounded write-site inventory mismatch: total={total_sites} accounted={accounted_sites}"
        )
    inventory_source_sha = inventory.get("source_sha256")
    if inventory_source_sha != canonical["sha256"]:
        raise FinalCapacityError("bounded lane inventory is stale for the canonical source")

    lanes = measurement.get("lanes")
    if not isinstance(lanes, dict) or not lanes:
        raise FinalCapacityError("measurement lacks lane measurements")
    required_lanes = contract.get("minimum_required_lanes")
    if not isinstance(required_lanes, list) or not all(isinstance(item, str) for item in required_lanes):
        raise FinalCapacityError("capacity contract has invalid minimum lane list")
    missing = sorted(set(required_lanes) - set(lanes))
    if missing:
        raise FinalCapacityError("measurement is missing required lanes: " + ", ".join(missing))

    normalized_lanes = {
        name: _validate_lane(name, raw)
        for name, raw in sorted(lanes.items())
    }
    minimum_headroom = min(item["headroom"] for item in normalized_lanes.values())
    zero_headroom = sorted(
        name for name, item in normalized_lanes.items() if item["headroom"] == 0
    )

    return {
        "schema": contract["output_schema"],
        "canonical_source": canonical,
        "stage1": stage1,
        "platform": {"system": platform["system"], "machine": platform["machine"]},
        "measurement": {
            "schema": measurement["schema"],
            "sha256": measurement_sha256,
            "native_evidence": True,
            "projection_substituted_for_native_measurement": False,
        },
        "bounded_lane_inventory": {
            "complete": True,
            "bounded_write_sites_total": total_sites,
            "accounted_write_sites": accounted_sites,
            "source_sha256": canonical["sha256"],
        },
        "lanes": normalized_lanes,
        "summary": {
            "lane_count": len(normalized_lanes),
            "minimum_headroom": minimum_headroom,
            "zero_headroom_lanes": zero_headroom,
            "all_banked_dispatch_proofs_pass": True,
            "all_banked_roundtrip_proofs_pass": True,
            "all_overflow_guards_exercised": True,
            "truncation_detected": False,
        },
        "qualification": {
            "all_capacities_no_truncation": "PASS",
            "native_evidence": True,
            "stage2_allowed_from_this_report_alone": False,
            "full_self_hosting": False,
            "next": "FINAL_SEMANTIC_IR_VERIFIER_AND_SELF_EMIT_EVIDENCE_STILL_REQUIRED",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        measurement_path = args.measurement.resolve()
        result = finalize_capacity(
            _load_json(measurement_path, "native capacity measurement"),
            source_path=args.source,
            stage1_path=args.stage1,
            contract=_load_json(args.contract.resolve(), "capacity contract"),
            measurement_sha256=_sha256(measurement_path),
        )
    except FinalCapacityError as error:
        parser.exit(2, f"Stage1 final capacity blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print("FINAL_CAPACITY=PASS")
    print(f"LANES={result['summary']['lane_count']}")
    print(f"MINIMUM_HEADROOM={result['summary']['minimum_headroom']}")
    print("STAGE2_ALLOWED_FROM_THIS_REPORT_ALONE=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
