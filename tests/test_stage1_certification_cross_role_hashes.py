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
            "native": {
                "schema": "example.native.v1",
                "assertions": [{"path": "status", "equals": "PASS"}],
            },
            "dependent": {
                "schema": "example.dependent.v1",
                "assertions": [{"path": "status", "equals": "PASS"}],
                "evidence_sha256_matches_role": [
                    {"path": "dependency.report_sha256", "role": "native"}
                ],
            },
        },
    }


def _gate(root: Path, *, referenced_native_sha: str | None = None) -> dict[str, object]:
    native_path, native_sha = _write(
        root,
        "reports/native.json",
        {"schema": "example.native.v1", "status": "PASS"},
    )
    dependent_path, dependent_sha = _write(
        root,
        "reports/dependent.json",
        {
            "schema": "example.dependent.v1",
            "status": "PASS",
            "dependency": {
                "report_sha256": native_sha if referenced_native_sha is None else referenced_native_sha
            },
        },
    )
    return {
        "schema": "s3.selfhost.stage1-certification-gate.v2",
        "evidence": {
            "native": {"path": native_path, "sha256": native_sha},
            "dependent": {"path": dependent_path, "sha256": dependent_sha},
        },
    }


def test_cross_role_sha_binding_accepts_exact_selected_evidence(tmp_path: Path) -> None:
    result = validate_stage1_evidence(
        _gate(tmp_path),
        canonical_sha256="a" * 64,
        stage1_sha256="b" * 64,
        root=tmp_path,
        contract=_contract(),
    )
    bindings = result["cross_role_hash_bindings"]
    assert len(bindings) == 1
    assert bindings[0]["role"] == "dependent"
    assert bindings[0]["target_role"] == "native"


def test_cross_role_sha_binding_rejects_different_but_individually_valid_report(tmp_path: Path) -> None:
    gate = _gate(tmp_path, referenced_native_sha="f" * 64)
    with pytest.raises(Stage1CertificationEvidenceError, match="cross-role SHA binding"):
        validate_stage1_evidence(
            gate,
            canonical_sha256="a" * 64,
            stage1_sha256="b" * 64,
            root=tmp_path,
            contract=_contract(),
        )
