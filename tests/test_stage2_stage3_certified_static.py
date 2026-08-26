from __future__ import annotations

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
    result = static_wrapper.qualify_certified_static(**_kwargs(tmp_path))
    assert observed == [assemble_link_static]
    assert fixed_point_module._assemble_link is original
    assert result["schema"] == "s3.selfhost.stage2-stage3-certified-static.v1"
    assert result["authority"] == "FINAL_SELF_HOSTING_AUTHORITY"
    assert result["static_link_recipe"]["flags"][0] == "-static"
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
    result = static_wrapper.qualify_certified_static(**_kwargs(tmp_path))
    assert result["qualification"]["full_self_hosting"] is False
    assert result["qualification"]["status"] == "BLOCKED_STATIC_HASHED_SELF_HOSTING_CERTIFICATION"
