from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.qualify_stage2_stage3_certified_strict as certified
from tools.qualify_stage2_stage3_certified_strict import (
    CertifiedStrictError,
    _compatibility_v1_gate,
    _final_qualification,
    _validate_gate_contract_authority,
    _validate_gate_source_manifest_authority,
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


def _git_binding(*, path: str, sha256: str, bytes_: int, commit: str = "1" * 40) -> dict[str, object]:
    return {
        "status": "PASS_REPOSITORY_FILE_GIT_HEAD_BINDING",
        "commit": commit,
        "path": path,
        "sha256": sha256,
        "bytes": bytes_,
        "git_object_type": "commit",
        "working_tree_equals_head_blob": True,
    }


def _contract_authority() -> dict[str, object]:
    sha = "c" * 64
    size = 100
    return {
        "status": "PASS_CANONICAL_CONTRACT_AUTHORITY",
        "schema": "s3.selfhost.stage1-certification-gate-contract.v3",
        "sha256": sha,
        "bytes": size,
        "exact_bytes_equal": True,
        "git_head_binding": _git_binding(
            path="reports/selfhost/stage1/stage1-certification-gate-contract.json",
            sha256=sha,
            bytes_=size,
        ),
    }


def _source_manifest_authority() -> dict[str, object]:
    sha = "d" * 64
    size = 120
    return {
        "status": "PASS_CANONICAL_SOURCE_MANIFEST_AUTHORITY",
        "schema": "s3.compiler.sources.v1",
        "sha256": sha,
        "bytes": size,
        "exact_bytes_equal": True,
        "git_head_binding": _git_binding(
            path="selfhost/compiler/compiler-sources.json",
            sha256=sha,
            bytes_=size,
        ),
        "source": {
            "path": "selfhost/compiler/s3c_stage1.s3",
            "sha256": "a" * 64,
            "bytes": 10,
            "role": "canonical_stage1_compiler",
            "ordering": 0,
        },
    }


def test_strict_engine_only_computes_prerequisites_never_final_authority() -> None:
    result = _final_qualification(
        _strict_engine(), "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION"
    )
    assert result["strict_prerequisites_pass"] is True
    assert result["final_static_authority_required"] is True
    assert result["full_self_hosting"] is False
    assert result["status"] == "PASS_HASHED_EVIDENCE_STRICT_ENGINE_PREREQUISITES"
    assert result["next"] == "RUN_CERTIFIED_STATIC_FINAL_AUTHORITY"

    result = _final_qualification(_strict_engine(), "FAIL")
    assert result["strict_prerequisites_pass"] is False
    assert result["full_self_hosting"] is False

    result = _final_qualification(
        _strict_engine(filesystem="FAIL_OR_BLOCKED"),
        "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION",
    )
    assert result["strict_prerequisites_pass"] is False
    assert result["full_self_hosting"] is False
    assert "filesystem_inaccessible" in result["failed_final_gates"]

    result = _final_qualification(
        _strict_engine(full=False),
        "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION",
    )
    assert result["strict_prerequisites_pass"] is False
    assert result["underlying_strict_engine_full_self_hosting_signal"] is False
    assert result["full_self_hosting"] is False


def test_underlying_old_schema_cannot_supply_strict_prerequisites() -> None:
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


def test_stage1_gate_contract_authority_requires_producer_git_head_binding() -> None:
    expected = _contract_authority()
    gate = {"contract_authority": json.loads(json.dumps(expected))}
    _validate_gate_contract_authority(gate, expected=expected)

    del gate["contract_authority"]["git_head_binding"]
    with pytest.raises(CertifiedStrictError, match="lacks producer Git HEAD binding"):
        _validate_gate_contract_authority(gate, expected=expected)


def test_stage1_gate_contract_authority_rejects_malformed_producer_commit() -> None:
    expected = _contract_authority()
    embedded = json.loads(json.dumps(expected))
    embedded["git_head_binding"]["commit"] = "not-a-commit"
    with pytest.raises(CertifiedStrictError, match="full commit SHA"):
        _validate_gate_contract_authority(
            {"contract_authority": embedded},
            expected=expected,
        )


def test_stage1_gate_source_manifest_authority_requires_same_committed_policy_and_source() -> None:
    expected = _source_manifest_authority()
    gate = {"source_manifest_authority": json.loads(json.dumps(expected))}
    _validate_gate_source_manifest_authority(gate, expected=expected)

    gate["source_manifest_authority"]["source"]["sha256"] = "f" * 64
    with pytest.raises(CertifiedStrictError, match="source.sha256 mismatch"):
        _validate_gate_source_manifest_authority(gate, expected=expected)


def test_stage1_gate_source_manifest_authority_rejects_wrong_git_bound_path() -> None:
    expected = _source_manifest_authority()
    embedded = json.loads(json.dumps(expected))
    embedded["git_head_binding"]["path"] = "other/manifest.json"
    with pytest.raises(CertifiedStrictError, match="producer Git binding path"):
        _validate_gate_source_manifest_authority(
            {"source_manifest_authority": embedded},
            expected=expected,
        )


def test_certified_wrapper_records_v2_revalidation_as_nonfinal_strict_engine(
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
    source_manifest_authority = _source_manifest_authority()
    source_manifest_authority["source"]["bytes"] = len(canonical_bytes)
    monkeypatch.setattr(
        certified,
        "require_authoritative_source_manifest",
        lambda *args, **kwargs: (
            canonical_path,
            canonical_bytes,
            manifest_doc,
            source_manifest_authority,
        ),
    )
    monkeypatch.setattr(
        certified,
        "validate_hashed_stage1_gate",
        lambda gate, **kwargs: {
            "canonical_sha256": "a" * 64,
            "canonical_bytes": len(canonical_bytes),
            "canonical_commit_binding": {
                "status": "PASS_CANONICAL_SOURCE_GIT_COMMIT_BINDING",
                "commit": "1" * 40,
                "sha256": "a" * 64,
                "bytes": len(canonical_bytes),
                "commit_blob_bytes_equal": True,
            },
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
    assert result["authority"] == "HASHED_EVIDENCE_STRICT_ENGINE_ONLY"
    assert result["final_authority"] is False
    assert result["stage1_certification"]["schema"] == "s3.selfhost.stage1-certification-gate.v2"
    assert result["stage1_certification"]["compatibility_adapter"]["persisted"] is False
    assert result["canonical_source"]["manifest_authority"]["status"] == "PASS_CANONICAL_SOURCE_MANIFEST_AUTHORITY"
    assert result["canonical_source"]["git_commit_binding"]["status"] == "PASS_CANONICAL_SOURCE_GIT_COMMIT_BINDING"
    assert result["qualification"]["strict_prerequisites_pass"] is True
    assert result["qualification"]["full_self_hosting"] is False
    assert result["qualification"]["next"] == "RUN_CERTIFIED_STATIC_FINAL_AUTHORITY"
    assert report.is_file()
