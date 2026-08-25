from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

import tools.promote_stage1_codegen_ir_v2_capacity as promoter
from tools.patch_stage1_codegen_ir_v2_capacity import (
    BASELINE_SOURCE_SHA256,
    NEW_DISCARD_EVENT_BLOCK,
    OLD_DISCARD_EVENT_BLOCK,
    transform,
)
from tools.promote_stage1_codegen_ir_v2_capacity import (
    MANIFEST,
    SOURCE,
    PromotionError,
    promote,
    validate_manifest,
    validate_native_report,
)


ROOT = Path(__file__).resolve().parents[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_for(data: bytes) -> dict[str, object]:
    return {
        "schema": "s3.compiler.sources.v1",
        "source_count": 1,
        "total_bytes": len(data),
        "sources": [
            {
                "path": "selfhost/compiler/s3c_stage1.s3",
                "sha256": _sha256(data),
                "role": "canonical_stage1_compiler",
                "ordering": 0,
            }
        ],
    }


def _good_native_report(canonical_bytes: bytes) -> dict[str, object]:
    candidate_bytes = transform(canonical_bytes.decode("utf-8")).encode("utf-8")
    audit = {
        "function_count": 34,
        "foreign_count": 5,
        "parameter_count": 64,
        "local_count": 23,
        "ast_assignment_count": 75,
        "ast_call_count": 656,
        "ast_return_count": 107,
        "ast_match_count": 92,
        "ast_while_count": 6,
        "ast_break_count": 6,
        "ast_binop_count": 155,
        "ast_comparison_count": 92,
        "ast_cast_count": 0,
        "ast_discard_count": 699,
        "local_function_count": 29,
        "ir_foreign_function_count": 5,
        "ir_parameter_count": 64,
        "ir_local_count": 23,
        "ir_block_count": 305,
        "ir_instruction_count": 761,
        "ir_value_count": 1213,
        "ir_internal_call_count": 653,
        "ir_foreign_call_count": 3,
        "ir_branch_count": 104,
        "ir_loop_count": 6,
        "ir_return_count": 107,
    }
    invariants = {
        "discard_count_preserved": True,
        "parameter_count_preserved": True,
        "call_count_preserved": True,
        "value_count_preserved": True,
        "block_count_preserved": True,
    }
    return {
        "schema": "s3.selfhost.codegen-ir-v2-capacity-native-candidate.v1",
        "platform": {"system": "Linux", "machine": "x86_64", "compiler": "/usr/bin/cc"},
        "canonical_source_mutated": False,
        "baseline": {
            "source_sha256": _sha256(canonical_bytes),
            "source_bytes": len(canonical_bytes),
            "native_events": 1460,
            "native_discard_events": 699,
            "event_capacity": 1460,
            "parameter_capacity": 64,
            "call_capacity": 730,
            "call_argument_capacity": 746,
        },
        "candidate": {
            "transform": "DROP_REDUNDANT_DISCARD_KEYWORD_EVENT",
            "source_sha256": _sha256(candidate_bytes),
            "source_bytes": len(candidate_bytes),
            "stage1_executable_sha256": "0" * 64,
            "stage1_executable_bytes": 1,
            "stage1_assembly_sha256": "1" * 64,
            "stage1_assembly_bytes": 1,
        },
        "contract_tests": {"status": "PASS", "returncode": 0, "stdout": "", "stderr": ""},
        "trivial_compile": {"status": "PASS", "returncode": 0, "stdout_sha256": "2" * 64, "stderr": ""},
        "self_source": {
            "status": "PASS_THROUGH_VERIFY_TO_EXPECTED_EMITTER_BOUNDARY",
            "returncode": 2,
            "stdout_bytes": 0,
            "stderr_lines": ["S3_STAGE1_AUDIT ...", "S3_STAGE1_EMITTER_BLOCKED"],
            "audit": audit,
            "final_marker": "S3_STAGE1_EMITTER_BLOCKED",
        },
        "audit_invariants": invariants,
        "capacity_measurement": {
            "actual_ir_instruction_count": 761,
            "actual_ast_discard_count": 699,
            "actual_event_reduction_from_native_baseline": 699,
            "actual_event_headroom": 699,
            "projection_was_761_events": True,
            "projection_is_not_substituted_for_native_measurement": True,
        },
        "qualification": {
            "contract_tests": "PASS",
            "candidate_build": "PASS",
            "trivial_compile": "PASS",
            "self_source_expected_boundary": "PASS",
            "audit_invariants": "PASS",
            "event_headroom": "PASS",
            "capacity_candidate": "PASS_NATIVE_CANDIDATE",
            "canonical_commit_allowed": True,
            "self_emit": "NOT_ATTEMPTED_GENERAL_EMITTER_STILL_BLOCKED",
            "stage2": "NOT_STARTED",
            "stage3": "NOT_STARTED",
            "full_self_hosting": False,
        },
    }


def test_canonical_manifest_matches_current_stage1_source() -> None:
    canonical_bytes = SOURCE.read_bytes()
    assert _sha256(canonical_bytes) == BASELINE_SOURCE_SHA256
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate_manifest(manifest, canonical_bytes)


def test_compaction_transform_is_narrow_and_single_use() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert source.count(OLD_DISCARD_EVENT_BLOCK) == 1
    assert source.count(NEW_DISCARD_EVENT_BLOCK) == 0

    transformed = transform(source)

    assert transformed.count(OLD_DISCARD_EVENT_BLOCK) == 0
    assert transformed.count(NEW_DISCARD_EVENT_BLOCK) == 1
    assert transformed.count("ast_discard_count += 1") == source.count("ast_discard_count += 1")
    assert "ir_ast_event_opcode = 5" not in transformed
    assert len(transformed.encode("utf-8")) < len(source.encode("utf-8"))

    with pytest.raises(ValueError, match="expected exactly one"):
        transform(transformed)


def test_native_report_validator_accepts_complete_consistent_evidence() -> None:
    canonical_bytes = SOURCE.read_bytes()
    report = _good_native_report(canonical_bytes)

    candidate_bytes, audit = validate_native_report(report, canonical_bytes=canonical_bytes)

    assert _sha256(candidate_bytes) == report["candidate"]["source_sha256"]
    assert audit["ir_instruction_count"] == 761
    assert audit["ast_discard_count"] == 699


def test_native_report_validator_rejects_skipped_contract_tests() -> None:
    canonical_bytes = SOURCE.read_bytes()
    report = _good_native_report(canonical_bytes)
    report["contract_tests"] = {"status": "SKIPPED_BY_OPERATOR"}
    report["qualification"]["contract_tests"] = "NOT_PASS"
    report["qualification"]["canonical_commit_allowed"] = False

    with pytest.raises(PromotionError, match="contract/capacity tests did not pass"):
        validate_native_report(report, canonical_bytes=canonical_bytes)


def test_native_report_validator_rejects_candidate_sha_mismatch() -> None:
    canonical_bytes = SOURCE.read_bytes()
    report = _good_native_report(canonical_bytes)
    report["candidate"]["source_sha256"] = "f" * 64

    with pytest.raises(PromotionError, match="candidate SHA"):
        validate_native_report(report, canonical_bytes=canonical_bytes)


def test_native_report_validator_rejects_changed_semantic_counts() -> None:
    canonical_bytes = SOURCE.read_bytes()
    report = _good_native_report(canonical_bytes)
    report["self_source"]["audit"]["ast_call_count"] = 655

    with pytest.raises(PromotionError, match="call count changed"):
        validate_native_report(report, canonical_bytes=canonical_bytes)


def test_manifest_validator_rejects_stale_hash() -> None:
    canonical_bytes = SOURCE.read_bytes()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    stale = deepcopy(manifest)
    stale["sources"][0]["sha256"] = "0" * 64

    with pytest.raises(PromotionError, match="manifest source SHA is stale"):
        validate_manifest(stale, canonical_bytes)


def test_promoter_default_is_validation_only(tmp_path: Path) -> None:
    canonical_before = SOURCE.read_bytes()
    manifest_before = MANIFEST.read_bytes()
    report_path = tmp_path / "native-candidate.json"
    report_path.write_text(
        json.dumps(_good_native_report(canonical_before), indent=2) + "\n",
        encoding="utf-8",
    )

    result = promote(report_path=report_path, in_place=False)

    assert result["status"] == "VALIDATED_NATIVE_CANDIDATE"
    assert result["canonical_source_mutated"] is False
    assert SOURCE.read_bytes() == canonical_before
    assert MANIFEST.read_bytes() == manifest_before


def test_transactional_promoter_rolls_back_both_files_on_post_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "s3c_stage1.s3"
    manifest_path = tmp_path / "compiler-sources.json"
    original_source = b"original-stage1-source\n"
    original_manifest = json.dumps(_manifest_for(original_source), indent=2).encode("utf-8") + b"\n"
    candidate_source = b"candidate-stage1-source\n"
    new_manifest = _manifest_for(candidate_source)
    source_path.write_bytes(original_source)
    manifest_path.write_bytes(original_manifest)

    monkeypatch.setattr(promoter, "SOURCE", source_path)
    monkeypatch.setattr(promoter, "MANIFEST", manifest_path)
    real_validate_manifest = promoter.validate_manifest
    calls = 0

    def fail_second_validation(manifest: dict[str, object], data: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PromotionError("forced post-write verification failure")
        real_validate_manifest(manifest, data)

    monkeypatch.setattr(promoter, "validate_manifest", fail_second_validation)

    with pytest.raises(PromotionError, match="was rolled back"):
        promoter._write_promoted_pair(
            candidate_bytes=candidate_source,
            new_manifest=new_manifest,
            original_source=original_source,
            original_manifest=original_manifest,
        )

    assert source_path.read_bytes() == original_source
    assert manifest_path.read_bytes() == original_manifest
    assert not source_path.with_name(source_path.name + ".ir-v2-promote.tmp").exists()
    assert not manifest_path.with_name(manifest_path.name + ".ir-v2-promote.tmp").exists()
