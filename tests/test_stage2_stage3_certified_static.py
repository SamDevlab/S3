from __future__ import annotations

import hashlib
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
    monkeypatch.setattr(
        static_wrapper,
        "_audit_final_stage_artifacts",
        lambda base: _passing_artifact_audits(),
    )
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
    monkeypatch.setattr(
        static_wrapper,
        "_audit_final_stage_artifacts",
        lambda base: _passing_artifact_audits(),
    )
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
