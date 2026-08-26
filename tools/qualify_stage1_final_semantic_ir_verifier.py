"""Finalize emitter-complete Stage1 semantic IR and verifier-v2 evidence.

The final report is intentionally harder to satisfy than the historical
``verifier-v2.json`` structural checkpoint.  It requires a fresh native
measurement, an already-passing final-capacity report for the same exact source
and Stage1 artifact, hosted reference-opcode reconciliation for the same source,
complete semantic features, required verifier checks, malformed-IR rejection
fixtures, and a measured verified-IR-only emitter boundary.
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
    ROOT / "reports" / "selfhost" / "stage1"
    / "final-semantic-ir-verifier-contract.json"
)
DEFAULT_CAPACITY = (
    ROOT / "reports" / "selfhost" / "stage1" / "stage1-final-capacity.json"
)
DEFAULT_REFERENCE = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-bootstrap-opcode-inventory.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "stage1-final-semantic-ir-verifier.json"
)


class FinalSemanticIRError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FinalSemanticIRError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise FinalSemanticIRError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise FinalSemanticIRError(f"{label} must be a JSON object")
    return value


def _require_int(value: Any, label: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FinalSemanticIRError(f"{label} must be a non-negative integer")
    if positive and value <= 0:
        raise FinalSemanticIRError(f"{label} must be positive")
    return value


def _binding(
    document: dict[str, Any],
    *,
    label: str,
    actual_path: Path,
) -> dict[str, Any]:
    raw = document.get(label)
    if not isinstance(raw, dict):
        raise FinalSemanticIRError(f"measurement lacks {label} binding")
    actual_sha = _sha256(actual_path)
    actual_bytes = actual_path.stat().st_size
    if raw.get("sha256") != actual_sha:
        raise FinalSemanticIRError(f"{label} SHA mismatch")
    if raw.get("bytes") != actual_bytes:
        raise FinalSemanticIRError(f"{label} byte-count mismatch")
    runtime_key = "runtime_input_sha256" if label == "canonical_source" else "executed_sha256"
    if raw.get(runtime_key) != actual_sha:
        raise FinalSemanticIRError(f"{label} runtime/executed binding mismatch")
    return {"path": str(actual_path), "sha256": actual_sha, "bytes": actual_bytes}


def _validate_capacity(
    capacity: dict[str, Any],
    *,
    canonical_sha: str,
    stage1_sha: str,
) -> None:
    if capacity.get("schema") != "s3.selfhost.stage1-final-capacity.v1":
        raise FinalSemanticIRError("final capacity report schema mismatch")
    qualification = capacity.get("qualification")
    if not isinstance(qualification, dict) or qualification.get("all_capacities_no_truncation") != "PASS":
        raise FinalSemanticIRError("final capacity report is not PASS")
    canonical = capacity.get("canonical_source")
    stage1 = capacity.get("stage1")
    if not isinstance(canonical, dict) or canonical.get("sha256") != canonical_sha:
        raise FinalSemanticIRError("final capacity report is bound to a different canonical source")
    if not isinstance(stage1, dict) or stage1.get("sha256") != stage1_sha:
        raise FinalSemanticIRError("final capacity report is bound to a different Stage1 artifact")


def _required_capabilities(
    reference: dict[str, Any],
    *,
    canonical_sha: str,
) -> tuple[set[str], dict[str, str]]:
    if reference.get("schema") != "s3.selfhost.reference-bootstrap-opcode-inventory.v1":
        raise FinalSemanticIRError("reference opcode inventory schema mismatch")
    if reference.get("status") != "PASS_HOSTED_REFERENCE_OPCODE_RECONCILIATION":
        raise FinalSemanticIRError("reference opcode inventory is not reconciled PASS")
    canonical = reference.get("canonical_source")
    if not isinstance(canonical, dict) or canonical.get("sha256") != canonical_sha:
        raise FinalSemanticIRError("reference opcode inventory is stale for canonical source")
    ir = reference.get("reference_ir")
    mapping = None if not isinstance(ir, dict) else ir.get("required_capabilities")
    if not isinstance(mapping, dict) or not mapping:
        raise FinalSemanticIRError("reference opcode inventory lacks required capabilities")
    normalized: dict[str, str] = {}
    for opcode, capability in mapping.items():
        if not isinstance(opcode, str) or not isinstance(capability, str) or not capability:
            raise FinalSemanticIRError("reference opcode capability mapping is malformed")
        normalized[opcode] = capability
    return set(normalized.values()), normalized


def finalize_semantic_ir(
    measurement: dict[str, Any],
    *,
    source_path: Path,
    stage1_path: Path,
    contract: dict[str, Any],
    capacity_report: dict[str, Any],
    reference_report: dict[str, Any],
    measurement_sha256: str | None = None,
    capacity_sha256: str | None = None,
    reference_sha256: str | None = None,
) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.stage1-final-semantic-ir-verifier-contract.v3":
        raise FinalSemanticIRError("final semantic IR contract schema mismatch")
    if measurement.get("schema") != contract.get("measurement_schema"):
        raise FinalSemanticIRError("native semantic IR measurement schema mismatch")

    platform = measurement.get("platform")
    if not isinstance(platform, dict):
        raise FinalSemanticIRError("measurement lacks platform")
    if platform.get("system") != "Linux" or str(platform.get("machine", "")).lower() not in {"x86_64", "amd64"}:
        raise FinalSemanticIRError("semantic IR finalization requires native Linux x86-64 evidence")

    flags = contract.get("required_measurement_flags")
    if not isinstance(flags, dict):
        raise FinalSemanticIRError("contract lacks required measurement flags")
    for key, expected in flags.items():
        if measurement.get(key) is not expected:
            raise FinalSemanticIRError(
                f"measurement flag {key} must be {expected!r}; got {measurement.get(key)!r}"
            )

    source_path = source_path.resolve()
    stage1_path = stage1_path.resolve()
    if not source_path.is_file() or not stage1_path.is_file():
        raise FinalSemanticIRError("canonical source and Stage1 artifact must exist")
    canonical = _binding(measurement, label="canonical_source", actual_path=source_path)
    stage1 = _binding(measurement, label="stage1", actual_path=stage1_path)

    _validate_capacity(
        capacity_report,
        canonical_sha=canonical["sha256"],
        stage1_sha=stage1["sha256"],
    )
    required_capabilities, opcode_capabilities = _required_capabilities(
        reference_report,
        canonical_sha=canonical["sha256"],
    )

    semantic_features = measurement.get("semantic_features")
    if not isinstance(semantic_features, list) or not all(isinstance(item, str) for item in semantic_features):
        raise FinalSemanticIRError("measurement semantic_features must be a list of strings")
    required_features = contract.get("required_semantic_features")
    if not isinstance(required_features, list):
        raise FinalSemanticIRError("contract lacks required semantic features")
    missing_features = sorted(set(required_features) - set(semantic_features))
    if missing_features:
        raise FinalSemanticIRError(
            "semantic IR is missing structural features: " + ", ".join(missing_features)
        )

    counts = measurement.get("inventory_counts")
    if not isinstance(counts, dict):
        raise FinalSemanticIRError("measurement lacks inventory_counts")
    minimum_counts = contract.get("minimum_inventory_counts")
    positive_counts = set(contract.get("strict_positive_inventory_counts", []))
    if not isinstance(minimum_counts, list):
        raise FinalSemanticIRError("contract lacks inventory count requirements")
    normalized_counts: dict[str, int] = {}
    for key in minimum_counts:
        if not isinstance(key, str):
            raise FinalSemanticIRError("inventory count key is not a string")
        normalized_counts[key] = _require_int(
            counts.get(key),
            f"inventory_counts.{key}",
            positive=key in positive_counts,
        )

    verifier_checks = measurement.get("verifier_checks")
    if not isinstance(verifier_checks, dict):
        raise FinalSemanticIRError("measurement lacks verifier_checks")
    required_checks = contract.get("required_verifier_checks")
    if not isinstance(required_checks, list):
        raise FinalSemanticIRError("contract lacks verifier check list")
    failed_checks = sorted(
        check for check in required_checks
        if not isinstance(check, str) or verifier_checks.get(check) != "PASS"
    )
    if failed_checks:
        raise FinalSemanticIRError(
            "verifier-v2 checks are not PASS: " + ", ".join(str(item) for item in failed_checks)
        )

    negatives = measurement.get("negative_fixtures")
    if not isinstance(negatives, dict):
        raise FinalSemanticIRError("measurement lacks negative_fixtures")
    required_negatives = contract.get("required_negative_fixtures")
    if not isinstance(required_negatives, list):
        raise FinalSemanticIRError("contract lacks negative fixture list")
    failed_negatives = sorted(
        name for name in required_negatives
        if not isinstance(name, str) or negatives.get(name) != "PASS_REJECTED"
    )
    if failed_negatives:
        raise FinalSemanticIRError(
            "verifier malformed-IR fixtures not rejected: "
            + ", ".join(str(item) for item in failed_negatives)
        )

    capabilities = measurement.get("capabilities")
    if not isinstance(capabilities, dict) or capabilities.get("inventory_complete") is not True:
        raise FinalSemanticIRError("native capability inventory is incomplete")
    native_supported = capabilities.get("native_supported")
    emitter = capabilities.get("general_emitter")
    if not isinstance(native_supported, list) or not all(isinstance(item, str) for item in native_supported):
        raise FinalSemanticIRError("capabilities.native_supported must be a list of strings")
    if not isinstance(emitter, dict):
        raise FinalSemanticIRError("capabilities.general_emitter must be an object")
    missing_native = sorted(required_capabilities - set(native_supported))
    if missing_native:
        raise FinalSemanticIRError(
            "Stage1 native IR lacks required capabilities: " + ", ".join(missing_native)
        )
    emitter_failures = sorted(
        capability for capability in required_capabilities
        if emitter.get(capability) != "PASS"
    )
    if emitter_failures:
        raise FinalSemanticIRError(
            "general emitter lacks PASS capabilities: " + ", ".join(emitter_failures)
        )

    boundary = measurement.get("emitter_boundary")
    required_boundary = contract.get("required_emitter_boundary")
    if not isinstance(boundary, dict) or not isinstance(required_boundary, dict):
        raise FinalSemanticIRError("emitter boundary evidence is missing")
    boundary_failures = [
        key for key, expected in required_boundary.items()
        if boundary.get(key) != expected
    ]
    if boundary_failures:
        raise FinalSemanticIRError(
            "verified-IR emitter boundary failed: " + ", ".join(boundary_failures)
        )

    return {
        "schema": contract["output_schema"],
        "canonical_source": canonical,
        "stage1": stage1,
        "platform": {"system": platform["system"], "machine": platform["machine"]},
        "evidence_inputs": {
            "native_measurement_sha256": measurement_sha256,
            "final_capacity_sha256": capacity_sha256,
            "reference_opcode_inventory_sha256": reference_sha256,
        },
        "reference_semantics": {
            "opcode_to_capability": dict(sorted(opcode_capabilities.items())),
            "required_capabilities": sorted(required_capabilities),
            "reference_physical_ir_is_stage1_authority": False,
        },
        "semantic_features": sorted(set(semantic_features)),
        "inventory_counts": normalized_counts,
        "verifier_checks": {key: "PASS" for key in required_checks},
        "negative_fixtures": {key: "PASS_REJECTED" for key in required_negatives},
        "capabilities": {
            "inventory_complete": True,
            "native_supported": sorted(set(native_supported)),
            "general_emitter": {key: emitter[key] for key in sorted(required_capabilities)},
        },
        "emitter_boundary": dict(required_boundary),
        "qualification": {
            "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
            "verifier_v2": "PASS",
            "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
            "native_evidence": True,
            "stage2_allowed_from_this_report_alone": False,
            "full_self_hosting": False,
            "next": "FINAL_STAGE1_SELF_EMIT_EVIDENCE_STILL_REQUIRED",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--capacity", type=Path, default=DEFAULT_CAPACITY)
    parser.add_argument("--reference-opcodes", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        measurement_path = args.measurement.resolve()
        capacity_path = args.capacity.resolve()
        reference_path = args.reference_opcodes.resolve()
        result = finalize_semantic_ir(
            _load_json(measurement_path, "native semantic IR measurement"),
            source_path=args.source,
            stage1_path=args.stage1,
            contract=_load_json(args.contract.resolve(), "semantic IR contract"),
            capacity_report=_load_json(capacity_path, "final capacity report"),
            reference_report=_load_json(reference_path, "reference opcode inventory"),
            measurement_sha256=_sha256(measurement_path),
            capacity_sha256=_sha256(capacity_path),
            reference_sha256=_sha256(reference_path),
        )
    except FinalSemanticIRError as error:
        parser.exit(2, f"Stage1 final semantic IR/verifier blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print("SEMANTIC_IR=PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET")
    print("VERIFIER_V2=PASS")
    print("GENERAL_EMITTER=PASS_BOOTSTRAP_REQUIRED_OPCODES")
    print("STAGE2_ALLOWED_FROM_THIS_REPORT_ALONE=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
