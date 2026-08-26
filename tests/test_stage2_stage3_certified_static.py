from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import tools.qualify_stage2_stage3_certified_static as static_wrapper
import tools.qualify_stage2_stage3_fixed_point as fixed_point_module
from tools.selfhost_static_link import assemble_link_static


pytestmark = pytest.mark.s3_fast


def _base(*, full: bool) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage2-stage3-certified-strict.v1",
        "qualification": {
            "stage1_hashed_evidence_revalidation": "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION",
            "stage1_to_stage2": "PASS",
            "stage2_pythonless_compiler": "PASS_STRICT_PROCESS_AND_FILE_TRACE",
            "filesystem_inaccessible": "PASS_LANDLOCK",
            "stage2_conformance": "PASS",
            "stage2_to_stage3": "PASS",
            "stage2_stage3_exact_elf_fixed_point": True,
            "full_self_hosting": full,
        },
    }


def _passing_artifact_audits() -> dict[str, object]:
    return {
        "status": "PASS_FINAL_STAGE2_STAGE3_FREESTANDING_STATIC_ELF_BINDING",
        "stage2": {
            "status": "PASS_FREESTANDING_STATIC_ELF",
            "sha256": "a" * 64,
            "bytes": 123,
        },
        "stage3": {
            "status": "PASS_FREESTANDING_STATIC_ELF",
            "sha256": "a" * 64,
            "bytes": 123,
        },
        "stage2_stage3_sha256_equal": True,
        "stage2_stage3_bytes_equal": True,
    }


def _passing_self_emit_binding() -> dict[str, object]:
    return {
        "status": "PASS_STAGE1_SELF_EMIT_STAGE2_CANDIDATE_EVIDENCE",
        "report": {
            "path": "/repo/stage1-final-self-emit.json",
            "sha256": "b" * 64,
            "schema": "s3.selfhost.stage1-final-self-emit.v1",
            "rehash_matches_stage1_gate": True,
        },
        "candidate": {
            "sha256": "a" * 64,
            "bytes": 123,
            "deterministic_two_artifacts": True,
            "freestanding_static_elf": True,
            "stage2_certified_by_self_emit_alone": False,
        },
    }


def _passing_continuity() -> dict[str, object]:
    return {
        "status": "PASS_STAGE1_SELF_EMIT_TO_STAGE2_STAGE3_CONTINUITY",
        "stage1_self_emit_stage2": {"sha256": "a" * 64, "bytes": 123},
        "fixed_point_stage2": {
            "sha256": "a" * 64,
            "bytes": 123,
            "matches_stage1_self_emit_candidate": True,
        },
        "fixed_point_stage3": {
            "sha256": "a" * 64,
            "bytes": 123,
            "matches_stage1_self_emit_candidate_via_exact_fixed_point": True,
        },
    }


def _kwargs(tmp_path: Path) -> dict[str, object]:
    return {
        "stage1": tmp_path / "stage1",
        "stage1_certification": tmp_path / "gate.json",
        "stage1_contract": tmp_path / "stage1-contract.json",
        "fixed_point_contract": tmp_path / "fixed-contract.json",
        "manifest": tmp_path / "manifest.json",
        "host_io": tmp_path / "host.c",
        "report": tmp_path / "final.json",
        "workspace": tmp_path / "workspace",
        "stage4": False,
    }


def _patch_passing_final_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        static_wrapper,
        "_audit_final_stage_artifacts",
        lambda base: _passing_artifact_audits(),
    )
    monkeypatch.setattr(
        static_wrapper,
        "_load_stage1_self_emit_stage2_binding",
        lambda base: _passing_self_emit_binding(),
    )
    monkeypatch.setattr(
        static_wrapper,
        "_bind_fixed_point_to_stage1_self_emit",
        lambda audits, self_emit: _passing_continuity(),
    )


def test_static_wrapper_temporarily_replaces_linker_and_restores_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = fixed_point_module._assemble_link
    observed: list[object] = []

    def fake_certified(**kwargs):
        del kwargs
        observed.append(fixed_point_module._assemble_link)
        return _base(full=True)

    monkeypatch.setattr(static_wrapper, "qualify_certified_strict", fake_certified)
    _patch_passing_final_bindings(monkeypatch)
    result = static_wrapper.qualify_certified_static(**_kwargs(tmp_path))
    assert observed == [assemble_link_static]
    assert fixed_point_module._assemble_link is original
    assert result["schema"] == "s3.selfhost.stage2-stage3-certified-static.v1"
    assert result["authority"] == "FINAL_SELF_HOSTING_AUTHORITY"
    assert result["static_link_recipe"]["flags"][0] == "-static"
    assert result["static_link_recipe"]["final_artifact_audit_required"] is True
    assert result["qualification"]["stage2_freestanding_static_elf"] == "PASS_FREESTANDING_STATIC_ELF"
    assert result["qualification"]["stage3_freestanding_static_elf"] == "PASS_FREESTANDING_STATIC_ELF"
    assert result["qualification"]["final_artifacts_bound_to_fixed_point"] is True
    assert result["qualification"]["stage1_self_emit_report_revalidated"] is True
    assert result["qualification"]["stage2_matches_stage1_self_emit_candidate"] is True
    assert result["qualification"]["stage3_matches_stage1_self_emit_candidate_via_fixed_point"] is True
    assert result["qualification"]["static_freestanding_link_recipe"] is True
    assert result["qualification"]["full_self_hosting"] is True


def test_static_wrapper_restores_legacy_linker_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = fixed_point_module._assemble_link

    def fail(**kwargs):
        del kwargs
        assert fixed_point_module._assemble_link is assemble_link_static
        raise RuntimeError("synthetic engine failure")

    monkeypatch.setattr(static_wrapper, "qualify_certified_strict", fail)
    with pytest.raises(RuntimeError, match="synthetic engine failure"):
        static_wrapper.qualify_certified_static(**_kwargs(tmp_path))
    assert fixed_point_module._assemble_link is original


def test_static_wrapper_cannot_upgrade_failed_hashed_engine_to_full_self_hosting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        static_wrapper,
        "qualify_certified_strict",
        lambda **kwargs: _base(full=False),
    )
    _patch_passing_final_bindings(monkeypatch)
    result = static_wrapper.qualify_certified_static(**_kwargs(tmp_path))
    assert result["qualification"]["underlying_strict_engine_full_self_hosting"] is False
    assert result["qualification"]["full_self_hosting"] is False
    assert result["qualification"]["status"] == "BLOCKED_STATIC_HASHED_SELF_HOSTING_CERTIFICATION"


def _artifact_bound_base(tmp_path: Path) -> tuple[dict[str, object], bytes, str]:
    payload = b"same-final-stage-artifact"
    digest = hashlib.sha256(payload).hexdigest()
    stage2 = tmp_path / "stage2"
    stage3 = tmp_path / "stage3"
    stage2.write_bytes(payload)
    stage3.write_bytes(payload)
    base = _base(full=True)
    base["strict_execution_engine"] = {
        "base_fixed_point": {
            "stage2": {
                "path": str(stage2),
                "sha256": digest,
                "bytes": len(payload),
            },
            "stage3": {
                "path": str(stage3),
                "sha256": digest,
                "bytes": len(payload),
            },
            "fixed_point": {
                "stage2_stage3_bytes_equal": True,
                "stage2_stage3_sha256_equal": True,
            },
        }
    }
    return base, payload, digest


def test_final_artifact_audit_binds_both_elfs_to_fixed_point_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, payload, digest = _artifact_bound_base(tmp_path)

    def fake_audit(path: Path) -> dict[str, object]:
        data = path.read_bytes()
        return {
            "status": "PASS_FREESTANDING_STATIC_ELF",
            "artifact": {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            },
            "guards": {"no_pt_interp": True, "no_pt_dynamic": True},
        }

    monkeypatch.setattr(static_wrapper, "audit_path", fake_audit)
    result = static_wrapper._audit_final_stage_artifacts(base)
    assert result["status"] == "PASS_FINAL_STAGE2_STAGE3_FREESTANDING_STATIC_ELF_BINDING"
    assert result["stage2"]["sha256"] == digest
    assert result["stage3"]["sha256"] == digest
    assert result["stage2"]["bytes"] == len(payload)
    assert result["stage3"]["bytes"] == len(payload)
    assert result["stage2"]["fixed_point_sha256_bound"] is True
    assert result["stage3"]["fixed_point_bytes_bound"] is True
    assert result["stage2_stage3_sha256_equal"] is True
    assert result["stage2_stage3_bytes_equal"] is True


def test_final_artifact_audit_rejects_stale_or_replaced_stage3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, payload, digest = _artifact_bound_base(tmp_path)

    def fake_audit(path: Path) -> dict[str, object]:
        actual_digest = digest if path.name == "stage2" else "f" * 64
        return {
            "status": "PASS_FREESTANDING_STATIC_ELF",
            "artifact": {
                "path": str(path.resolve()),
                "sha256": actual_digest,
                "bytes": len(payload),
            },
        }

    monkeypatch.setattr(static_wrapper, "audit_path", fake_audit)
    with pytest.raises(static_wrapper.CertifiedStaticError, match="stage3 ELF audit SHA differs"):
        static_wrapper._audit_final_stage_artifacts(base)


def test_final_artifact_audit_rejects_dynamic_or_malformed_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, payload, digest = _artifact_bound_base(tmp_path)

    def fake_audit(path: Path) -> dict[str, object]:
        return {
            "status": (
                "FAIL_FREESTANDING_STATIC_ELF"
                if path.name == "stage2"
                else "PASS_FREESTANDING_STATIC_ELF"
            ),
            "artifact": {
                "path": str(path.resolve()),
                "sha256": digest,
                "bytes": len(payload),
            },
        }

    monkeypatch.setattr(static_wrapper, "audit_path", fake_audit)
    with pytest.raises(static_wrapper.CertifiedStaticError, match="stage2 failed final freestanding"):
        static_wrapper._audit_final_stage_artifacts(base)


def test_final_artifact_audit_requires_fixed_point_equality_before_auditing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, _payload, _digest = _artifact_bound_base(tmp_path)
    base["strict_execution_engine"]["base_fixed_point"]["fixed_point"][
        "stage2_stage3_bytes_equal"
    ] = False
    called = False

    def fail_if_called(path: Path) -> dict[str, object]:
        nonlocal called
        called = True
        raise AssertionError(path)

    monkeypatch.setattr(static_wrapper, "audit_path", fail_if_called)
    with pytest.raises(static_wrapper.CertifiedStaticError, match="byte equality"):
        static_wrapper._audit_final_stage_artifacts(base)
    assert called is False


def _self_emit_document(stage2_sha: str, stage2_bytes: int) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-final-self-emit.v1",
        "qualification": {
            "self_emit": "PASS",
            "stage1_certified_candidate": True,
            "stage2_artifact_created": True,
            "stage2_certified": False,
            "stage3_started": False,
            "full_self_hosting": False,
            "semantic_ir_native_call_boundary": "PASS",
        },
        "link_recipe": {"mode": "STATIC_FREESTANDING_FINAL_AUTHORITY"},
        "semantic_ir_call_boundary": {
            "status": "PASS",
            "authority": "STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND",
        },
        "stage2": {
            "sha256": stage2_sha,
            "bytes": stage2_bytes,
            "second_artifact": {"sha256": stage2_sha, "bytes": stage2_bytes},
            "elf_bytes_equal": True,
            "elf_sha256_equal": True,
            "freestanding_elf_audit": {"status": "PASS_FREESTANDING_STATIC_ELF"},
            "second_freestanding_elf_audit": {"status": "PASS_FREESTANDING_STATIC_ELF"},
            "certified": False,
        },
    }


def _base_with_self_emit_evidence(
    tmp_path: Path,
    *,
    stage2_sha: str = "a" * 64,
    stage2_bytes: int = 123,
) -> tuple[dict[str, object], Path, str]:
    report = tmp_path / "reports" / "selfhost" / "stage1" / "stage1-final-self-emit.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            _self_emit_document(stage2_sha, stage2_bytes),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    report.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    base = _base(full=True)
    base["stage1_certification"] = {
        "evidence_revalidation": {
            "status": "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION",
            "validated_roles": {
                "final_self_emit": {
                    "path": str(report),
                    "sha256": digest,
                    "schema": "s3.selfhost.stage1-final-self-emit.v1",
                }
            },
        }
    }
    return base, report, digest


def test_final_self_emit_report_is_rehashed_before_stage2_identity_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(static_wrapper, "ROOT", tmp_path)
    base, report, digest = _base_with_self_emit_evidence(tmp_path)
    result = static_wrapper._load_stage1_self_emit_stage2_binding(base)
    assert result["status"] == "PASS_STAGE1_SELF_EMIT_STAGE2_CANDIDATE_EVIDENCE"
    assert result["report"]["path"] == str(report.resolve())
    assert result["report"]["sha256"] == digest
    assert result["report"]["rehash_matches_stage1_gate"] is True
    assert result["candidate"]["sha256"] == "a" * 64
    assert result["candidate"]["bytes"] == 123
    assert result["candidate"]["stage2_certified_by_self_emit_alone"] is False


def test_final_self_emit_report_mutation_after_stage1_gate_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(static_wrapper, "ROOT", tmp_path)
    base, report, _digest = _base_with_self_emit_evidence(tmp_path)
    document = json.loads(report.read_text(encoding="utf-8"))
    document["stage2"]["sha256"] = "f" * 64
    report.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(
        static_wrapper.CertifiedStaticError,
        match="changed after Stage1 gate revalidation",
    ):
        static_wrapper._load_stage1_self_emit_stage2_binding(base)


def test_final_self_emit_report_wrong_schema_is_rejected_even_with_matching_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(static_wrapper, "ROOT", tmp_path)
    base, report, _digest = _base_with_self_emit_evidence(tmp_path)
    document = json.loads(report.read_text(encoding="utf-8"))
    document["schema"] = "s3.selfhost.stage1-final-self-emit.v0"
    payload = (json.dumps(document, sort_keys=True) + "\n").encode("utf-8")
    report.write_bytes(payload)
    base["stage1_certification"]["evidence_revalidation"]["validated_roles"][
        "final_self_emit"
    ]["sha256"] = hashlib.sha256(payload).hexdigest()
    with pytest.raises(static_wrapper.CertifiedStaticError, match="report schema"):
        static_wrapper._load_stage1_self_emit_stage2_binding(base)


def test_fixed_point_stage2_must_match_stage1_self_emit_candidate() -> None:
    audits = _passing_artifact_audits()
    binding = _passing_self_emit_binding()
    result = static_wrapper._bind_fixed_point_to_stage1_self_emit(audits, binding)
    assert result["status"] == "PASS_STAGE1_SELF_EMIT_TO_STAGE2_STAGE3_CONTINUITY"
    assert result["fixed_point_stage2"]["matches_stage1_self_emit_candidate"] is True
    assert result["fixed_point_stage3"][
        "matches_stage1_self_emit_candidate_via_exact_fixed_point"
    ] is True


def test_fixed_point_stage2_sha_mismatch_with_self_emit_is_rejected() -> None:
    audits = _passing_artifact_audits()
    audits["stage2"]["sha256"] = "c" * 64
    with pytest.raises(static_wrapper.CertifiedStaticError, match="fixed-point Stage2 SHA differs"):
        static_wrapper._bind_fixed_point_to_stage1_self_emit(
            audits,
            _passing_self_emit_binding(),
        )


def test_fixed_point_stage2_byte_mismatch_with_self_emit_is_rejected() -> None:
    audits = _passing_artifact_audits()
    audits["stage2"]["bytes"] = 124
    with pytest.raises(
        static_wrapper.CertifiedStaticError,
        match="fixed-point Stage2 byte count differs",
    ):
        static_wrapper._bind_fixed_point_to_stage1_self_emit(
            audits,
            _passing_self_emit_binding(),
        )


def test_fixed_point_stage3_must_preserve_self_emit_identity() -> None:
    audits = _passing_artifact_audits()
    audits["stage3"]["sha256"] = "d" * 64
    with pytest.raises(
        static_wrapper.CertifiedStaticError,
        match="Stage3 does not preserve",
    ):
        static_wrapper._bind_fixed_point_to_stage1_self_emit(
            audits,
            _passing_self_emit_binding(),
        )
