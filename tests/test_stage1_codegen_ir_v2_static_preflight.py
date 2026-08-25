from __future__ import annotations

import json
from pathlib import Path

import tools.preflight_stage1_codegen_ir_v2_static as preflight


def _storage(pass_gate: bool) -> dict[str, object]:
    return {
        "status": "STATIC_STORAGE_AUDIT_PASS" if pass_gate else "STATIC_STORAGE_AUDIT_FAIL",
        "native_evidence": False,
    }


def _arrays(pass_gate: bool) -> dict[str, object]:
    return {
        "status": "STATIC_ARRAY_INITIALIZER_AUDIT_PASS" if pass_gate else "STATIC_ARRAY_INITIALIZER_AUDIT_FAIL",
        "native_evidence": False,
        "summary": {
            "zero_initializer_items": 123,
            "all_zero_arrays": 4,
        },
    }


def test_static_preflight_passes_only_when_both_audits_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(preflight, "audit_storage", lambda _: _storage(True))
    monkeypatch.setattr(preflight, "audit_arrays", lambda _: _arrays(True))
    source = tmp_path / "source.s3"
    source.write_text("fn main() -> tryte:\n    return 0\n", encoding="utf-8")
    result = preflight.run(
        source_path=source,
        storage_report_path=tmp_path / "storage.json",
        array_report_path=tmp_path / "arrays.json",
        report_path=tmp_path / "preflight.json",
    )
    assert result["status"] == "PASS_STATIC_ONLY"
    assert result["native_chain_allowed"] is True
    assert result["canonical_source_mutated"] is False
    assert json.loads((tmp_path / "preflight.json").read_text(encoding="utf-8"))["native_evidence"] is False


def test_static_preflight_fails_closed_when_storage_audit_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(preflight, "audit_storage", lambda _: _storage(False))
    monkeypatch.setattr(preflight, "audit_arrays", lambda _: _arrays(True))
    source = tmp_path / "source.s3"
    source.write_text("fn main() -> tryte:\n    return 0\n", encoding="utf-8")
    result = preflight.run(
        source_path=source,
        storage_report_path=tmp_path / "storage.json",
        array_report_path=tmp_path / "arrays.json",
        report_path=tmp_path / "preflight.json",
    )
    assert result["status"] == "FAIL_STATIC"
    assert result["native_chain_allowed"] is False


def test_static_preflight_fails_closed_when_array_audit_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(preflight, "audit_storage", lambda _: _storage(True))
    monkeypatch.setattr(preflight, "audit_arrays", lambda _: _arrays(False))
    source = tmp_path / "source.s3"
    source.write_text("fn main() -> tryte:\n    return 0\n", encoding="utf-8")
    result = preflight.run(
        source_path=source,
        storage_report_path=tmp_path / "storage.json",
        array_report_path=tmp_path / "arrays.json",
        report_path=tmp_path / "preflight.json",
    )
    assert result["status"] == "FAIL_STATIC"
    assert result["native_chain_allowed"] is False
