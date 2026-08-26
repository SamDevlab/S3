from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.stage1_certification_evidence import (
    Stage1CertificationEvidenceError,
    validate_stage1_evidence,
)


pytestmark = pytest.mark.s3_fast
CANONICAL_SHA = "a" * 64
STAGE1_SHA = "b" * 64


def _write(root: Path, relative: str, document: dict[str, object]) -> tuple[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(document, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return relative, hashlib.sha256(payload).hexdigest()


def _contract() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-certification-gate-contract.v3",
        "output_schema": "s3.selfhost.stage1-certification-gate.v2",
        "required_evidence_roles": {
            "source": {
                "schema": "example.source.v1",
                "assertions": [{"path": "qualification.status", "equals": "PASS"}],
                "canonical_source_sha256_path": "canonical.sha256",
            },
            "artifact": {
                "schema": "example.artifact.v1",
                "assertions": [{"path": "qualification.status", "equals": "PASS"}],
                "stage1_artifact_sha256_path": "stage1.sha256",
            },
        },
    }


def _gate(root: Path) -> dict[str, object]:
    source_path, source_sha = _write(
        root,
        "reports/source.json",
        {
            "schema": "example.source.v1",
            "canonical": {"sha256": CANONICAL_SHA},
            "qualification": {"status": "PASS"},
        },
    )
    artifact_path, artifact_sha = _write(
        root,
        "reports/artifact.json",
        {
            "schema": "example.artifact.v1",
            "stage1": {"sha256": STAGE1_SHA},
            "qualification": {"status": "PASS"},
        },
    )
    return {
        "schema": "s3.selfhost.stage1-certification-gate.v2",
        "evidence": {
            "source": {"path": source_path, "sha256": source_sha},
            "artifact": {"path": artifact_path, "sha256": artifact_sha},
        },
    }


def test_hashed_evidence_revalidation_passes_exact_source_and_artifact(tmp_path: Path) -> None:
    result = validate_stage1_evidence(
        _gate(tmp_path),
        canonical_sha256=CANONICAL_SHA,
        stage1_sha256=STAGE1_SHA,
        root=tmp_path,
        contract=_contract(),
    )
    assert result["status"] == "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION"
    assert set(result["validated_roles"]) == {"source", "artifact"}


def test_report_mutation_after_gate_creation_is_rejected(tmp_path: Path) -> None:
    gate = _gate(tmp_path)
    (tmp_path / "reports/source.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(Stage1CertificationEvidenceError, match="SHA mismatch"):
        validate_stage1_evidence(
            gate,
            canonical_sha256=CANONICAL_SHA,
            stage1_sha256=STAGE1_SHA,
            root=tmp_path,
            contract=_contract(),
        )


def test_stale_source_bound_evidence_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(Stage1CertificationEvidenceError, match="different canonical source"):
        validate_stage1_evidence(
            _gate(tmp_path),
            canonical_sha256="c" * 64,
            stage1_sha256=STAGE1_SHA,
            root=tmp_path,
            contract=_contract(),
        )


def test_evidence_from_different_stage1_artifact_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(Stage1CertificationEvidenceError, match="different Stage1 artifact"):
        validate_stage1_evidence(
            _gate(tmp_path),
            canonical_sha256=CANONICAL_SHA,
            stage1_sha256="d" * 64,
            root=tmp_path,
            contract=_contract(),
        )


def test_missing_required_role_is_rejected(tmp_path: Path) -> None:
    gate = _gate(tmp_path)
    del gate["evidence"]["artifact"]
    with pytest.raises(Stage1CertificationEvidenceError, match="lacks required evidence roles"):
        validate_stage1_evidence(
            gate,
            canonical_sha256=CANONICAL_SHA,
            stage1_sha256=STAGE1_SHA,
            root=tmp_path,
            contract=_contract(),
        )


def test_evidence_path_cannot_escape_repository_root(tmp_path: Path) -> None:
    gate = _gate(tmp_path)
    gate["evidence"]["source"] = {"path": "../outside.json", "sha256": "0" * 64}
    with pytest.raises(Stage1CertificationEvidenceError, match="escapes repository root"):
        validate_stage1_evidence(
            gate,
            canonical_sha256=CANONICAL_SHA,
            stage1_sha256=STAGE1_SHA,
            root=tmp_path,
            contract=_contract(),
        )
