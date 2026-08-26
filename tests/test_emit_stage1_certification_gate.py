from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.emit_stage1_certification_gate import (
    Stage1CertificationGateError,
    _parse_evidence_overrides,
    build_gate,
    git_head_source_binding,
)
from tools.stage1_certification_evidence import Stage1CertificationEvidenceError


pytestmark = pytest.mark.s3_fast


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    stage1 = root / "stage1"
    stage1.write_bytes(b"stage1-artifact")
    stage1.chmod(stage1.stat().st_mode | 0o111)
    source = root / "compiler.s3"
    source.write_bytes(b"fn main() -> tryte:\n    return 0\n")
    canonical = {
        "path": "compiler.s3",
        "sha256": _sha(source.read_bytes()),
        "bytes": source.stat().st_size,
        "commit": "1" * 40,
        "working_tree_equals_commit_blob": True,
    }
    evidence_dir = root / "reports"
    evidence_dir.mkdir()
    report = evidence_dir / "proof.json"
    report.write_text(
        json.dumps(
            {
                "schema": "test.evidence.v1",
                "qualification": {"pass": True},
                "canonical": {"sha256": canonical["sha256"]},
                "stage1": {"sha256": _sha(stage1.read_bytes())},
            }
        ),
        encoding="utf-8",
    )
    contract = {
        "schema": "s3.selfhost.stage1-certification-gate-contract.v3",
        "output_schema": "s3.selfhost.stage1-certification-gate.v2",
        "required_evidence_roles": {
            "proof": {
                "schema": "test.evidence.v1",
                "assertions": [
                    {"path": "qualification.pass", "equals": True},
                ],
                "canonical_source_sha256_path": "canonical.sha256",
                "stage1_artifact_sha256_path": "stage1.sha256",
            }
        },
    }
    return root, source, stage1, canonical, report, contract


def test_build_gate_revalidates_current_evidence_content(tmp_path: Path) -> None:
    root, _source, stage1, canonical, _report, contract = _fixture(tmp_path)
    gate = build_gate(
        canonical_source=canonical,
        stage1_path=stage1,
        evidence_paths={"proof": "reports/proof.json"},
        contract=contract,
        root=root,
    )
    assert gate["schema"] == "s3.selfhost.stage1-certification-gate.v2"
    assert gate["qualification"]["stage1_certified_for_stage2"] is True
    assert gate["qualification"]["full_self_hosting"] is False
    assert gate["evidence_revalidation"]["status"] == "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION"
    assert gate["evidence_revalidation"]["required_roles"] == ["proof"]


def test_build_gate_rejects_report_with_false_assertion(tmp_path: Path) -> None:
    root, _source, stage1, canonical, report, contract = _fixture(tmp_path)
    document = json.loads(report.read_text(encoding="utf-8"))
    document["qualification"]["pass"] = False
    report.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(Stage1CertificationEvidenceError, match="assertion"):
        build_gate(
            canonical_source=canonical,
            stage1_path=stage1,
            evidence_paths={"proof": "reports/proof.json"},
            contract=contract,
            root=root,
        )


def test_build_gate_rejects_missing_or_extra_evidence_role(tmp_path: Path) -> None:
    root, _source, stage1, canonical, _report, contract = _fixture(tmp_path)
    with pytest.raises(Stage1CertificationGateError, match="role set mismatch"):
        build_gate(
            canonical_source=canonical,
            stage1_path=stage1,
            evidence_paths={},
            contract=contract,
            root=root,
        )
    with pytest.raises(Stage1CertificationGateError, match="role set mismatch"):
        build_gate(
            canonical_source=canonical,
            stage1_path=stage1,
            evidence_paths={"proof": "reports/proof.json", "extra": "reports/proof.json"},
            contract=contract,
            root=root,
        )


def test_build_gate_rejects_non_executable_stage1(tmp_path: Path) -> None:
    root, _source, stage1, canonical, _report, contract = _fixture(tmp_path)
    stage1.chmod(0o600)
    with pytest.raises(Stage1CertificationGateError, match="not executable"):
        build_gate(
            canonical_source=canonical,
            stage1_path=stage1,
            evidence_paths={"proof": "reports/proof.json"},
            contract=contract,
            root=root,
        )


def test_build_gate_rejects_evidence_path_escape(tmp_path: Path) -> None:
    root, _source, stage1, canonical, _report, contract = _fixture(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(Stage1CertificationGateError, match="escapes repository root"):
        build_gate(
            canonical_source=canonical,
            stage1_path=stage1,
            evidence_paths={"proof": "../outside.json"},
            contract=contract,
            root=root,
        )


def test_evidence_override_parser_only_accepts_known_roles() -> None:
    result = _parse_evidence_overrides(
        ["final_capacity=reports/selfhost/stage1/custom-capacity.json"]
    )
    assert result["final_capacity"].endswith("custom-capacity.json")
    with pytest.raises(Stage1CertificationGateError, match="invalid evidence override"):
        _parse_evidence_overrides(["unknown_role=x.json"])
    with pytest.raises(Stage1CertificationGateError, match="ROLE=repository/path.json"):
        _parse_evidence_overrides(["broken"])


def test_git_head_source_binding_rejects_source_outside_repository(tmp_path: Path) -> None:
    source = tmp_path / "outside.s3"
    source.write_text("fn main() -> tryte:\n    return 0\n", encoding="utf-8")
    with pytest.raises(Stage1CertificationGateError, match="inside repository root"):
        git_head_source_binding(source)
