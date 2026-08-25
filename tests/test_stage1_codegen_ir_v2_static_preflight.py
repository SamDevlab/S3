from __future__ import annotations

import json
from pathlib import Path

import tools.preflight_stage1_codegen_ir_v2_static as preflight


def _storage(pass_gate: bool) -> dict[str, object]:
    return {
        "status": "STATIC_STORAGE_AUDIT_PASS" if pass_gate else "STATIC_STORAGE_AUDIT_FAIL",
        "native_evidence": False,
        "event_bank_lifetime": {
            "frontier": (
                "AFTER_LEGACY_EVENT_VERIFIER_BEFORE_REMAINING_VERIFIER_AND_PIPELINE_DECISION"
                if pass_gate
                else "NOT_PROVEN"
            )
        },
    }


def _blocks(pass_gate: bool) -> dict[str, object]:
    return {
        "status": (
            "STATIC_BLOCK_CAPACITY_DESIGN_PASS"
            if pass_gate
            else "STATIC_BLOCK_CAPACITY_DESIGN_FAIL"
        ),
        "native_evidence": False,
        "legacy": {"capacity": 365},
        "candidate": {"capacity": 730},
        "parameter_candidate_static_projection": {
            "projected_blocks": 362,
            "strict_additional_match_or_while_budget": 0,
        },
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


def _run(tmp_path: Path) -> dict[str, object]:
    source = tmp_path / "source.s3"
    source.write_text("fn main() -> tryte:\n    return 0\n", encoding="utf-8")
    return preflight.run(
        source_path=source,
        storage_report_path=tmp_path / "storage.json",
        block_report_path=tmp_path / "blocks.json",
        array_report_path=tmp_path / "arrays.json",
        report_path=tmp_path / "preflight.json",
    )


def test_static_preflight_passes_only_when_all_audits_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(preflight, "audit_storage", lambda _: _storage(True))
    monkeypatch.setattr(preflight, "audit_blocks", lambda _: _blocks(True))
    monkeypatch.setattr(preflight, "audit_arrays", lambda _: _arrays(True))
    result = _run(tmp_path)
    assert result["status"] == "PASS_STATIC_ONLY"
    assert result["native_chain_allowed"] is True
    assert result["canonical_source_mutated"] is False
    assert result["block_capacity_audit"]["legacy_capacity"] == 365
    assert result["block_capacity_audit"]["candidate_capacity"] == 730
    assert result["block_capacity_audit"]["strict_additional_control_budget"] == 0
    assert json.loads((tmp_path / "preflight.json").read_text(encoding="utf-8"))["native_evidence"] is False


def test_static_preflight_fails_closed_when_storage_audit_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(preflight, "audit_storage", lambda _: _storage(False))
    monkeypatch.setattr(preflight, "audit_blocks", lambda _: _blocks(True))
    monkeypatch.setattr(preflight, "audit_arrays", lambda _: _arrays(True))
    result = _run(tmp_path)
    assert result["status"] == "FAIL_STATIC"
    assert result["native_chain_allowed"] is False


def test_static_preflight_fails_closed_when_block_design_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(preflight, "audit_storage", lambda _: _storage(True))
    monkeypatch.setattr(preflight, "audit_blocks", lambda _: _blocks(False))
    monkeypatch.setattr(preflight, "audit_arrays", lambda _: _arrays(True))
    result = _run(tmp_path)
    assert result["status"] == "FAIL_STATIC"
    assert result["native_chain_allowed"] is False


def test_static_preflight_fails_closed_when_array_audit_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(preflight, "audit_storage", lambda _: _storage(True))
    monkeypatch.setattr(preflight, "audit_blocks", lambda _: _blocks(True))
    monkeypatch.setattr(preflight, "audit_arrays", lambda _: _arrays(False))
    result = _run(tmp_path)
    assert result["status"] == "FAIL_STATIC"
    assert result["native_chain_allowed"] is False
