"""Strict content-bound validation for the Stage1 -> Stage2 authorization gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "stage1-certification-gate-contract.json"
)


class Stage1CertificationEvidenceError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def json_path(document: object, path: str) -> object:
    current = document
    for component in path.split("."):
        if not component:
            raise Stage1CertificationEvidenceError(f"invalid empty JSON path component in {path!r}")
        if not isinstance(current, dict) or component not in current:
            raise Stage1CertificationEvidenceError(f"JSON path {path!r} is missing at {component!r}")
        current = current[component]
    return current


def _resolve_repo_evidence(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise Stage1CertificationEvidenceError("evidence path must be repository-relative")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise Stage1CertificationEvidenceError(
            f"evidence path escapes repository root: {relative}"
        ) from error
    if resolved.suffix.lower() != ".json":
        raise Stage1CertificationEvidenceError(
            f"evidence must be a JSON report: {relative}"
        )
    if not resolved.is_file():
        raise Stage1CertificationEvidenceError(
            f"evidence report is missing: {relative}"
        )
    return resolved


def _load_contract(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise Stage1CertificationEvidenceError("Stage1 certification contract must be an object")
    if document.get("schema") != "s3.selfhost.stage1-certification-gate-contract.v3":
        raise Stage1CertificationEvidenceError("Stage1 certification contract schema mismatch")
    return document


def validate_stage1_evidence(
    gate: dict[str, Any],
    *,
    canonical_sha256: str,
    stage1_sha256: str,
    root: Path = ROOT,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = _load_contract(DEFAULT_CONTRACT) if contract is None else contract
    if policy.get("schema") != "s3.selfhost.stage1-certification-gate-contract.v3":
        raise Stage1CertificationEvidenceError("Stage1 certification contract schema mismatch")
    if gate.get("schema") != policy.get("output_schema"):
        raise Stage1CertificationEvidenceError(
            f"Stage1 gate schema must be {policy.get('output_schema')!r}"
        )
    evidence = gate.get("evidence")
    role_policy = policy.get("required_evidence_roles")
    if not isinstance(evidence, dict) or not isinstance(role_policy, dict):
        raise Stage1CertificationEvidenceError("Stage1 gate/contract lacks evidence role map")

    missing_roles = sorted(set(role_policy) - set(evidence))
    if missing_roles:
        raise Stage1CertificationEvidenceError(
            "Stage1 certification lacks required evidence roles: "
            + ", ".join(missing_roles)
        )

    validated: dict[str, Any] = {}
    for role, raw_spec in role_policy.items():
        entry = evidence.get(role)
        if not isinstance(raw_spec, dict) or not isinstance(entry, dict):
            raise Stage1CertificationEvidenceError(f"evidence role {role!r} is malformed")
        relative = entry.get("path")
        expected_digest = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_digest, str):
            raise Stage1CertificationEvidenceError(
                f"evidence role {role!r} lacks path/sha256"
            )
        path = _resolve_repo_evidence(root, relative)
        actual_digest = sha256_file(path)
        if actual_digest != expected_digest:
            raise Stage1CertificationEvidenceError(
                f"evidence role {role!r} SHA mismatch: gate={expected_digest} actual={actual_digest}"
            )
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise Stage1CertificationEvidenceError(
                f"evidence role {role!r} report is not a JSON object"
            )
        expected_schema = raw_spec.get("schema")
        if report.get("schema") != expected_schema:
            raise Stage1CertificationEvidenceError(
                f"evidence role {role!r} schema mismatch: expected={expected_schema!r} actual={report.get('schema')!r}"
            )
        assertions = raw_spec.get("assertions", [])
        if not isinstance(assertions, list):
            raise Stage1CertificationEvidenceError(
                f"evidence role {role!r} assertions policy is malformed"
            )
        checked_assertions: list[dict[str, Any]] = []
        for assertion in assertions:
            if not isinstance(assertion, dict) or not isinstance(assertion.get("path"), str):
                raise Stage1CertificationEvidenceError(
                    f"evidence role {role!r} contains malformed assertion"
                )
            field = assertion["path"]
            expected = assertion.get("equals")
            actual = json_path(report, field)
            if actual != expected:
                raise Stage1CertificationEvidenceError(
                    f"evidence role {role!r} assertion {field!r} failed: expected={expected!r} actual={actual!r}"
                )
            checked_assertions.append({"path": field, "equals": expected})

        canonical_path = raw_spec.get("canonical_source_sha256_path")
        if canonical_path is not None:
            if not isinstance(canonical_path, str):
                raise Stage1CertificationEvidenceError(
                    f"evidence role {role!r} canonical SHA policy is malformed"
                )
            report_sha = json_path(report, canonical_path)
            if report_sha != canonical_sha256:
                raise Stage1CertificationEvidenceError(
                    f"evidence role {role!r} was produced for a different canonical source: "
                    f"expected={canonical_sha256} actual={report_sha}"
                )

        artifact_path = raw_spec.get("stage1_artifact_sha256_path")
        if artifact_path is not None:
            if not isinstance(artifact_path, str):
                raise Stage1CertificationEvidenceError(
                    f"evidence role {role!r} Stage1 SHA policy is malformed"
                )
            report_stage1_sha = json_path(report, artifact_path)
            if report_stage1_sha != stage1_sha256:
                raise Stage1CertificationEvidenceError(
                    f"evidence role {role!r} was produced by a different Stage1 artifact: "
                    f"expected={stage1_sha256} actual={report_stage1_sha}"
                )

        validated[role] = {
            "path": str(path),
            "sha256": actual_digest,
            "schema": expected_schema,
            "assertions": checked_assertions,
            "canonical_source_bound": canonical_path is not None,
            "stage1_artifact_bound": artifact_path is not None,
        }

    return {
        "status": "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION",
        "canonical_source_sha256": canonical_sha256,
        "stage1_sha256": stage1_sha256,
        "required_roles": sorted(role_policy),
        "validated_roles": validated,
    }
