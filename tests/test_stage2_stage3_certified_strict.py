from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.qualify_stage2_stage3_certified_strict as certified
from tools.qualify_stage2_stage3_certified_strict import (
    CertifiedStrictError,
    _compatibility_v1_gate,
    _final_qualification,
)


pytestmark = pytest.mark.s3_fast
ROOT = Path(__file__).resolve().parents[1]


def _strict_engine(*, full: bool = True, filesystem: str = "PASS_LANDLOCK") -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage2-stage3-strict-sandbox.v4",
        "qualification": {
            "stage1_to_stage2": "PASS",
            "stage2_pythonless_compiler": "PASS_STRICT_PROCESS_AND_FILE_TRACE",
            "filesystem_inaccessible": filesystem,
            "stage2_conformance": "PASS",
            "stage2_to_stage3": "PASS",
            "stage2_stage3_exact_elf_fixed_point": True,
            "full_self_hosting": full,
        },
    }


def test_final_authority_requires_hashed_stage1_evidence_and_all_strict_gates() -> None:
    result = _final_qualification(
        _strict_engine(), "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION"
    )
    assert result["full_self_hosting"] is True
    assert result["status"] == "FULL_SELF_HOSTING_CERTIFIED_VIA_HASHED_STAGE1_GATE"

    result = _final_qualification(_strict_engine(), "FAIL")
    assert result["full_self_hosting"] is False

    result = _final_qualification(
        _strict_engine(filesystem="FAIL_OR_BLOCKED"),
        "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION",
    )
    assert result["full_self_hosting"] is False
    assert "filesystem_inaccessible" in result["failed_final_gates"]

    result = _final_qualification(
        _strict_engine(full=False),
        "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION",
    )
    assert result["full_self_hosting"] is False


def test_underlying_old_schema_cannot_be_final_authority() -> None:
    old = _strict_engine()
    old["schema"] = "s3.selfhost.stage2-stage3-strict-sandbox.v3"
    with pytest.raises(CertifiedStrictError, match="schema mismatch"):
        _final_qualification(old, "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION")


def test_compatibility_gate_is_explicitly_ephemeral_and_has_no_authority() -> None:
    gate = {
        "canonical_source": {"sha256": "a" * 64, "bytes": 123},
        "qualification": {
            "stage1_certified_for_stage2": True,
            "self_emit": "PASS",
            "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
            "verifier_v2": "PASS",
            "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
        },
    }
    compat = _compatibility_v1_gate(gate)
    assert compat["schema"] == "s3.selfhost.stage1-certification-gate.v1"
    assert compat["compatibility_only"] is True
    assert compat["authority"] == "NONE_EPHEMERAL_AFTER_V2_HASHED_EVIDENCE_REVALIDATION"
    assert "evidence" not in compat


def test_certified_wrapper_records_v2_revalidation_as_final_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stage1 = tmp_path / "stage1"
    stage1.write_bytes(b"stage1")
    stage1.chmod(stage1.stat().st_mode | 0o111)
    gate_path = tmp_path / "gate-v2.json"
    gate_path.write_text(
        json.dumps(
            {
                "schema": "s3.selfhost.stage1-certification-gate.v2",
                "canonical_source": {
                    "path": "selfhost/compiler/s3c_stage1.s3",
                    "sha256": "a" * 64,
                    "bytes": 10,
                    "commit": "1" * 40,
                    "working_tree_equals_commit_blob": True,
                },
                "stage1_artifact": {"sha256": "b" * 64, "bytes": 6},
                "evidence": {},
                "qualification": {
                    "stage1_certified_for_stage2": True,
                    "self_emit": "PASS",
                    "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
                    "verifier_v2": "PASS",
                    "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
                    "full_self_hosting": False,
                },
            }
        ),
        encoding="utf-8",
    )

    canonical_path = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
    canonical_bytes = b"canonical"
    manifest_doc = {"schema": "s3.compiler.sources.v1"}
    monkeypatch.setattr(
        certified,
        "_canonical_source",
        lambda manifest: (canonical_path, canonical_bytes, manifest_doc),
    )
    monkeypatch.setattr(
        certified,
        "validate_hashed_stage1_gate",
        lambda gate, **kwargs: {
            "canonical_sha256": "a" * 64,
            "canonical_bytes": len(canonical_bytes),
            "stage1_sha256": "b" * 64,
            "stage1_bytes": stage1.stat().st_size,
            "evidence": {
                "status": "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION",
                "validated_roles": {"proof": {}},
            },
        },
    )

    captured_compat: dict[str, object] = {}

    def fake_strict(**kwargs):
        compat_path = Path(kwargs["stage1_certification"])
        assert compat_path.is_file()
        captured_compat.update(json.loads(compat_path.read_text(encoding="utf-8")))
        return _strict_engine()

    monkeypatch.setattr(certified, "qualify_strict", fake_strict)
    report = tmp_path / "certified.json"
    result = certified.qualify_certified_strict(
        stage1=stage1,
        stage1_certification=gate_path,
        stage1_contract=ROOT / "reports" / "selfhost" / "stage1" / "stage1-certification-gate-contract.json",
        fixed_point_contract=ROOT / "reports" / "selfhost" / "stage2" / "stage2-stage3-fixed-point-contract.json",
        manifest=ROOT / "selfhost" / "compiler" / "compiler-sources.json",
        host_io=ROOT / "selfhost" / "compiler" / "stage1_host_io.c",
        report=report,
        workspace=tmp_path / "workspace",
    )
    assert captured_compat["schema"] == "s3.selfhost.stage1-certification-gate.v1"
    assert captured_compat["authority"] == "NONE_EPHEMERAL_AFTER_V2_HASHED_EVIDENCE_REVALIDATION"
    assert result["schema"] == "s3.selfhost.stage2-stage3-certified-strict.v1"
    assert result["authority"] == "FINAL_SELF_HOSTING_AUTHORITY"
    assert result["stage1_certification"]["schema"] == "s3.selfhost.stage1-certification-gate.v2"
    assert result["stage1_certification"]["compatibility_adapter"]["persisted"] is False
    assert result["qualification"]["full_self_hosting"] is True
    assert report.is_file()
