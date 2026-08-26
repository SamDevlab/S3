from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.qualify_stage1_final_semantic_ir_verifier import (
    FinalSemanticIRError,
    finalize_semantic_ir,
)


pytestmark = pytest.mark.s3_fast
ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract() -> dict[str, object]:
    return json.loads(
        (
            ROOT / "reports" / "selfhost" / "stage1"
            / "final-semantic-ir-verifier-contract.json"
        ).read_text(encoding="utf-8")
    )


def _files(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "compiler.s3"
    stage1 = tmp_path / "s3c-stage1"
    source.write_bytes(b"fn main() -> tryte:\n    return 0\n")
    stage1.write_bytes(b"\x7fELFsynthetic-stage1-semantic-ir")
    return source, stage1


def _capacity(source: Path, stage1: Path) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-final-capacity.v1",
        "canonical_source": {"sha256": _sha(source), "bytes": source.stat().st_size},
        "stage1": {"sha256": _sha(stage1), "bytes": stage1.stat().st_size},
        "qualification": {"all_capacities_no_truncation": "PASS"},
    }


def _reference(source: Path) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.reference-bootstrap-opcode-inventory.v1",
        "status": "PASS_HOSTED_REFERENCE_OPCODE_RECONCILIATION",
        "canonical_source": {"sha256": _sha(source), "bytes": source.stat().st_size},
        "reference_ir": {
            "required_capabilities": {
                "const": "CONST",
                "load": "LOAD",
                "store": "STORE",
                "call": "CALL",
                "return": "RETURN",
                "branch3": "BRANCH3",
            }
        },
    }


def _measurement(source: Path, stage1: Path) -> dict[str, object]:
    contract = _contract()
    source_sha = _sha(source)
    stage1_sha = _sha(stage1)
    required_caps = {"CONST", "LOAD", "STORE", "CALL", "RETURN", "BRANCH3"}
    document: dict[str, object] = {
        "schema": "s3.selfhost.stage1-semantic-ir-measurement.v1",
        "platform": {"system": "Linux", "machine": "x86_64"},
        "canonical_source": {
            "sha256": source_sha,
            "bytes": source.stat().st_size,
            "runtime_input_sha256": source_sha,
        },
        "stage1": {
            "sha256": stage1_sha,
            "bytes": stage1.stat().st_size,
            "executed_sha256": stage1_sha,
        },
        "semantic_features": list(contract["required_semantic_features"]),
        "inventory_counts": {
            key: 1 for key in contract["minimum_inventory_counts"]
        },
        "verifier_checks": {
            key: "PASS" for key in contract["required_verifier_checks"]
        },
        "negative_fixtures": {
            key: "PASS_REJECTED" for key in contract["required_negative_fixtures"]
        },
        "capabilities": {
            "inventory_complete": True,
            "native_supported": sorted(required_caps),
            "general_emitter": {key: "PASS" for key in required_caps},
        },
        "emitter_boundary": dict(contract["required_emitter_boundary"]),
    }
    document.update(contract["required_measurement_flags"])
    return document


def _finalize(tmp_path: Path):
    source, stage1 = _files(tmp_path)
    return source, stage1, finalize_semantic_ir(
        _measurement(source, stage1),
        source_path=source,
        stage1_path=stage1,
        contract=_contract(),
        capacity_report=_capacity(source, stage1),
        reference_report=_reference(source),
    )


def test_valid_complete_measurement_passes_but_does_not_authorize_stage2(tmp_path: Path) -> None:
    _source, _stage1, result = _finalize(tmp_path)
    assert result["schema"] == "s3.selfhost.stage1-final-semantic-ir-verifier.v1"
    assert result["qualification"]["semantic_ir"] == "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET"
    assert result["qualification"]["verifier_v2"] == "PASS"
    assert result["qualification"]["general_emitter"] == "PASS_BOOTSTRAP_REQUIRED_OPCODES"
    assert result["qualification"]["stage2_allowed_from_this_report_alone"] is False
    assert result["qualification"]["full_self_hosting"] is False


def test_capacity_must_bind_same_stage1_and_source(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    capacity = _capacity(source, stage1)
    capacity["stage1"]["sha256"] = "0" * 64  # type: ignore[index]
    with pytest.raises(FinalSemanticIRError, match="different Stage1 artifact"):
        finalize_semantic_ir(
            _measurement(source, stage1), source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=capacity, reference_report=_reference(source),
        )


def test_reference_opcode_inventory_must_be_pass_and_current(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    reference = _reference(source)
    reference["status"] = "BLOCKED_LEGACY_EMITTER_REQUIREMENTS_STALE"
    with pytest.raises(FinalSemanticIRError, match="not reconciled PASS"):
        finalize_semantic_ir(
            _measurement(source, stage1), source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=reference,
        )

    reference = _reference(source)
    reference["canonical_source"]["sha256"] = "f" * 64  # type: ignore[index]
    with pytest.raises(FinalSemanticIRError, match="stale for canonical source"):
        finalize_semantic_ir(
            _measurement(source, stage1), source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=reference,
        )


def test_missing_structural_semantic_feature_fails_closed(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["semantic_features"].remove("INTERNAL_CALL_ARGUMENT_AND_RESULT_LINKAGE")  # type: ignore[union-attr]
    with pytest.raises(FinalSemanticIRError, match="missing structural features"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )


def test_required_inventory_counts_must_be_positive(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["inventory_counts"]["semantic_values"] = 0  # type: ignore[index]
    with pytest.raises(FinalSemanticIRError, match="semantic_values must be positive"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )


def test_every_required_verifier_check_must_pass(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["verifier_checks"]["dominance"] = "FAIL"  # type: ignore[index]
    with pytest.raises(FinalSemanticIRError, match="verifier-v2 checks"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )


def test_every_malformed_ir_fixture_must_be_rejected(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["negative_fixtures"]["extension_slot_used_as_value"] = "ACCEPTED"  # type: ignore[index]
    with pytest.raises(FinalSemanticIRError, match="malformed-IR fixtures"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )


def test_reference_required_capability_must_exist_in_native_ir_and_emitter(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["capabilities"]["native_supported"].remove("BRANCH3")  # type: ignore[index,union-attr]
    with pytest.raises(FinalSemanticIRError, match="lacks required capabilities"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )

    measurement = _measurement(source, stage1)
    measurement["capabilities"]["general_emitter"]["BRANCH3"] = "BLOCKED"  # type: ignore[index]
    with pytest.raises(FinalSemanticIRError, match="general emitter lacks PASS"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )


def test_verified_ir_only_emitter_boundary_is_mandatory(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["emitter_boundary"]["raw_source_accesses_after_verifier"] = 1  # type: ignore[index]
    with pytest.raises(FinalSemanticIRError, match="emitter boundary failed"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )


def test_top_level_source_reread_or_python_codegen_flag_blocks(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["raw_source_reread"] = True
    with pytest.raises(FinalSemanticIRError, match="raw_source_reread"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )

    measurement = _measurement(source, stage1)
    measurement["python_codegen"] = True
    with pytest.raises(FinalSemanticIRError, match="python_codegen"):
        finalize_semantic_ir(
            measurement, source_path=source, stage1_path=stage1,
            contract=_contract(), capacity_report=_capacity(source, stage1), reference_report=_reference(source),
        )
