from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.qualify_stage1_final_self_emit_static as static


pytestmark = pytest.mark.s3_fast


def _call_bound_document() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-final-semantic-ir-verifier.v1",
        "authority": "STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND",
        "qualification": {
            "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
            "verifier_v2": "PASS",
            "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
            "native_call_capacity_boundary": "PASS",
        },
        "native_call_capacity_dependency": {
            "status": "PASS_NATIVE_CURRENT_SOURCE_CALL_RECONCILIATION",
            "report_sha256": "a" * 64,
            "same_canonical_source": True,
            "same_stage1_artifact": True,
            "semantic_calls_equal_native_high_water": True,
            "semantic_call_arguments_equal_native_high_water": True,
            "calls": 11,
            "call_arguments": 17,
        },
    }


def test_call_bound_semantic_ir_validation_accepts_exact_authority() -> None:
    static.validate_call_bound_semantic_ir(_call_bound_document())


def test_call_bound_semantic_ir_validation_rejects_unbound_report() -> None:
    document = _call_bound_document()
    document.pop("authority")
    with pytest.raises(
        static.FinalSelfEmitStaticBoundaryError,
        match="STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND",
    ):
        static.validate_call_bound_semantic_ir(document)


def test_call_bound_semantic_ir_validation_rejects_high_water_disagreement() -> None:
    document = _call_bound_document()
    dependency = document["native_call_capacity_dependency"]
    assert isinstance(dependency, dict)
    dependency["semantic_call_arguments_equal_native_high_water"] = False
    with pytest.raises(
        static.FinalSelfEmitStaticBoundaryError,
        match="semantic_call_arguments_equal_native_high_water",
    ):
        static.validate_call_bound_semantic_ir(document)


def test_static_self_emit_decorates_final_report_with_call_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic = tmp_path / "semantic-call-bound.json"
    semantic.write_text(json.dumps(_call_bound_document()), encoding="utf-8")
    report = tmp_path / "stage1-final-self-emit.json"
    seen: dict[str, object] = {}

    def fake_qualify(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {
            "schema": "s3.selfhost.stage1-final-self-emit.v1",
            "qualification": {
                "self_emit": "PASS",
                "stage1_certified_candidate": True,
                "stage2_artifact_created": True,
                "stage2_certified": False,
                "full_self_hosting": False,
            },
        }

    monkeypatch.setattr(static.base, "qualify", fake_qualify)
    result = static.qualify(
        semantic_ir_report_path=semantic,
        report=report,
        stage1=tmp_path / "unused-stage1",
        source=tmp_path / "unused-source",
        contract_path=tmp_path / "unused-contract",
        host_io=tmp_path / "unused-host",
        workspace=tmp_path / "unused-workspace",
    )

    assert seen["semantic_ir_report_path"] == semantic.resolve()
    assert result["link_recipe"]["mode"] == "STATIC_FREESTANDING_FINAL_AUTHORITY"  # type: ignore[index]
    boundary = result["semantic_ir_call_boundary"]
    assert isinstance(boundary, dict)
    assert boundary["authority"] == "STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND"
    assert boundary["status"] == "PASS"
    assert boundary["semantic_calls_equal_native_high_water"] is True
    assert boundary["semantic_call_arguments_equal_native_high_water"] is True
    qualification = result["qualification"]
    assert isinstance(qualification, dict)
    assert qualification["semantic_ir_native_call_boundary"] == "PASS"
    assert report.is_file()
