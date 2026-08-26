"""Classify the exact Stage1 source representation epoch fail-closed.

This hosted audit prevents old candidate transformers/reports from being applied
to a source that has already materialized newer explicit IR lanes.  It is not
native compiler evidence and never authorizes Stage2 by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" / "representation-epoch-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "stage1-representation-epoch.json"
)

_ARRAY_DECL = re.compile(
    r"^\s*mut\s+(ir_(?:parameter|local)_[A-Za-z0-9_]+)\s*:\s*[A-Za-z0-9_]+\[(\d+)\]\s*=",
    re.MULTILINE,
)


class RepresentationEpochError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RepresentationEpochError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise RepresentationEpochError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise RepresentationEpochError(f"{label} must be a JSON object")
    return value


def classify_source(source_text: str, *, source_bytes: bytes | None = None, contract: dict[str, Any]) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.stage1-representation-epoch-contract.v1":
        raise RepresentationEpochError("representation epoch contract schema mismatch")

    encoded = source_text.encode("utf-8") if source_bytes is None else source_bytes
    if source_bytes is not None and source_bytes.decode("utf-8") != source_text:
        raise RepresentationEpochError("source text/bytes binding mismatch")

    arrays = {name: int(size) for name, size in _ARRAY_DECL.findall(source_text)}
    required_parameters = contract.get("explicit_parameter_arrays_required")
    if not isinstance(required_parameters, list) or not all(isinstance(item, str) for item in required_parameters):
        raise RepresentationEpochError("contract has invalid explicit parameter lane list")
    required_parameter_set = set(required_parameters)

    packed_parameter = str(contract.get("packed_parameter_marker", "ir_parameter_records"))
    packed_local = str(contract.get("packed_local_marker", "ir_local_records"))
    local_prefix = str(contract.get("local_array_prefix", "ir_local_"))
    exclusions = set(contract.get("local_array_exclusions", []))
    explicit_local_minimum = contract.get("explicit_local_array_minimum")
    if isinstance(explicit_local_minimum, bool) or not isinstance(explicit_local_minimum, int) or explicit_local_minimum < 1:
        raise RepresentationEpochError("contract has invalid explicit local lane minimum")

    present_parameter_arrays = sorted(name for name in arrays if name.startswith("ir_parameter_") and name != packed_parameter)
    present_parameter_set = set(present_parameter_arrays)
    required_parameter_present = sorted(required_parameter_set & present_parameter_set)
    required_parameter_missing = sorted(required_parameter_set - present_parameter_set)
    has_packed_parameter = packed_parameter in arrays
    explicit_parameter_complete = not required_parameter_missing
    partial_explicit_parameter = bool(required_parameter_present) and not explicit_parameter_complete

    explicit_local_arrays = sorted(
        name
        for name in arrays
        if name.startswith(local_prefix) and name not in exclusions and name != packed_local
    )
    has_packed_local = packed_local in arrays
    explicit_local_complete = len(explicit_local_arrays) >= explicit_local_minimum
    partial_explicit_local = 0 < len(explicit_local_arrays) < explicit_local_minimum

    conflicts: list[str] = []
    if has_packed_parameter and present_parameter_arrays:
        conflicts.append("PACKED_AND_EXPLICIT_PARAMETER_METADATA_COEXIST")
    if partial_explicit_parameter:
        conflicts.append("PARTIAL_EXPLICIT_PARAMETER_METADATA")
    if has_packed_local and explicit_local_arrays:
        conflicts.append("PACKED_AND_EXPLICIT_LOCAL_METADATA_COEXIST")
    if partial_explicit_local:
        conflicts.append("PARTIAL_EXPLICIT_LOCAL_METADATA")
    if explicit_local_complete and not explicit_parameter_complete:
        conflicts.append("EXPLICIT_LOCAL_METADATA_WITHOUT_EXPLICIT_PARAMETER_METADATA")

    if conflicts:
        status = "BLOCKED_REPRESENTATION_EPOCH_INCONSISTENT"
        epoch = -1
        epoch_name = "INCONSISTENT"
    elif explicit_parameter_complete and explicit_local_complete:
        status = "PASS_REPRESENTATION_EPOCH_CLASSIFIED"
        epoch = 3
        epoch_name = "EXPLICIT_PARAMETER_AND_LOCAL_METADATA"
    elif explicit_parameter_complete:
        status = "PASS_REPRESENTATION_EPOCH_CLASSIFIED"
        epoch = 2
        epoch_name = "EXPLICIT_PARAMETER_METADATA"
    elif has_packed_parameter:
        status = "PASS_REPRESENTATION_EPOCH_CLASSIFIED"
        epoch = 1
        epoch_name = "LEGACY_PACKED_PARAMETER_RECORD"
    else:
        status = "PASS_REPRESENTATION_EPOCH_CLASSIFIED"
        epoch = 0
        epoch_name = "LEGACY_NO_PARAMETER_METADATA"

    return {
        "schema": contract["output_schema"],
        "status": status,
        "native_evidence": False,
        "source": {
            "sha256": _sha256(encoded),
            "bytes": len(encoded),
        },
        "representation": {
            "epoch": epoch,
            "name": epoch_name,
            "conflicts": conflicts,
            "array_declarations": dict(sorted(arrays.items())),
            "packed_parameter_record_present": has_packed_parameter,
            "explicit_parameter_arrays": present_parameter_arrays,
            "required_explicit_parameter_arrays_present": required_parameter_present,
            "required_explicit_parameter_arrays_missing": required_parameter_missing,
            "explicit_parameter_metadata_complete": explicit_parameter_complete,
            "packed_local_record_present": has_packed_local,
            "explicit_local_arrays": explicit_local_arrays,
            "explicit_local_array_count": len(explicit_local_arrays),
            "explicit_local_array_minimum": explicit_local_minimum,
            "explicit_local_metadata_complete": explicit_local_complete,
        },
        "historical_transform_compatibility": {
            "legacy_packed_parameter_transform_applicable": (
                epoch == 0 and not conflicts
            ),
            "legacy_packed_local_transform_directly_applicable": (
                epoch == 1 and not has_packed_local and not explicit_local_arrays and not conflicts
            ),
            "newer_epoch_requires_migration_not_reapplication": epoch >= 2,
            "source_sha_lock_still_required": True,
        },
        "qualification": {
            "representation_epoch_known": not conflicts,
            "stage1_certified_for_stage2": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": (
                "USE_ONLY_TOOLS_AND_REPORTS_COMPATIBLE_WITH_THIS_EXACT_SOURCE_EPOCH"
                if not conflicts
                else "RECONCILE_MIXED_OR_PARTIAL_IR_REPRESENTATION_BEFORE_CONTINUING"
            ),
        },
    }


def validate_epoch_report_for_source(report: dict[str, Any], source_bytes: bytes, *, minimum_epoch: int | None = None) -> None:
    if report.get("schema") != "s3.selfhost.stage1-representation-epoch.v1":
        raise RepresentationEpochError("representation epoch report schema mismatch")
    if report.get("status") != "PASS_REPRESENTATION_EPOCH_CLASSIFIED":
        raise RepresentationEpochError("representation epoch report is not PASS")
    binding = report.get("source")
    representation = report.get("representation")
    if not isinstance(binding, dict) or not isinstance(representation, dict):
        raise RepresentationEpochError("representation epoch report is malformed")
    actual_sha = _sha256(source_bytes)
    if binding.get("sha256") != actual_sha or binding.get("bytes") != len(source_bytes):
        raise RepresentationEpochError("representation epoch report is stale for current source bytes")
    epoch = representation.get("epoch")
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise RepresentationEpochError("representation epoch value is invalid")
    if minimum_epoch is not None and epoch < minimum_epoch:
        raise RepresentationEpochError(
            f"representation epoch {epoch} is older than required minimum {minimum_epoch}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    try:
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8")
        result = classify_source(
            source_text,
            source_bytes=source_bytes,
            contract=_load_json(args.contract.resolve(), "representation epoch contract"),
        )
    except (OSError, UnicodeDecodeError, RepresentationEpochError) as error:
        parser.exit(2, f"Stage1 representation epoch audit blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"SOURCE_SHA256={result['source']['sha256']}")
    print(f"EPOCH={result['representation']['epoch']}")
    print(f"EPOCH_NAME={result['representation']['name']}")
    print(f"PARAMETER_ARRAYS={','.join(result['representation']['explicit_parameter_arrays'])}")
    print(f"LOCAL_ARRAY_COUNT={result['representation']['explicit_local_array_count']}")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"] == "PASS_REPRESENTATION_EPOCH_CLASSIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
