from __future__ import annotations

import hashlib

import pytest

from tools.patch_stage1_codegen_ir_v2_locals import (
    LocalCandidateError,
    SOURCE,
    transform_locals,
    validate_parameter_prerequisite,
)
from tools.patch_stage1_codegen_ir_v2_parameters import build_candidate as build_parameter_candidate
from tools.preflight_stage1_codegen_ir_v2_locals import (
    build_preflight,
    identifier_hash_text,
    source_metrics,
    stage1_tokens,
)


def _parameter_source() -> str:
    return build_parameter_candidate(SOURCE.read_text(encoding="utf-8"))


def _native_parameter_report(*, local_count_delta: int = 0) -> dict[str, object]:
    source = _parameter_source()
    metrics = source_metrics(source)
    audit = {
        "parameter_count": 64,
        "local_count": int(metrics["mut_hash_tokens"]) + local_count_delta,
        "ir_instruction_count": int(metrics["structural_event_tokens"]),
        "ir_value_count": int(metrics["numeric_tokens"]),
        "ir_block_count": 320,
        "ast_call_count": int(metrics["call_syntax_count"]),
    }
    encoded = source.encode("utf-8")
    return {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "canonical_source_mutated": False,
        "candidate": {
            "source_sha256": hashlib.sha256(encoded).hexdigest(),
            "source_bytes": len(encoded),
        },
        "self_source": {"audit": audit},
        "qualification": {
            "static_preflight": "PASS",
            "prerequisite_capacity_report": "PASS_VALIDATED",
            "trivial_compile": "PASS",
            "parameter_verifier_to_emitter_boundary": "PASS",
            "capacity_guards": "PASS",
            "parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE",
        },
    }


def test_stage1_identifier_hash_constants_match_compiler_contract() -> None:
    assert identifier_hash_text("mut") == 87
    assert identifier_hash_text("fn") == 352
    assert identifier_hash_text("return") == 342
    assert identifier_hash_text("match") == 135
    assert identifier_hash_text("while") == 162


def test_stage1_scanner_matches_signed_number_and_punctuation_subset() -> None:
    tokens = stage1_tokens("mut x: i64 = -7\nmut a: i64[16] = [0]\n")
    assert any(token.kind == 1 and token.text == "mut" and token.value == 87 for token in tokens)
    assert any(token.kind == 2 and token.value == -7 for token in tokens)
    assert any(token.kind == 4 and token.value == 3 for token in tokens)  # colon
    assert any(token.kind == 4 and token.value == 10 for token in tokens)  # [
    assert any(token.kind == 4 and token.value == 11 for token in tokens)  # ]


def test_parameter_report_source_sha_is_mandatory() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    report = _native_parameter_report()
    report["candidate"]["source_sha256"] = "0" * 64
    with pytest.raises(LocalCandidateError, match="source SHA"):
        validate_parameter_prerequisite(report, canonical_source=canonical)


def test_local_transform_requires_parameter_candidate() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    with pytest.raises(LocalCandidateError, match="packed-parameter"):
        transform_locals(canonical, local_capacity=64)


def test_local_transform_is_deterministic_and_shape_preserving() -> None:
    parameter_source = _parameter_source()
    first = transform_locals(parameter_source, local_capacity=365)
    second = transform_locals(parameter_source, local_capacity=365)
    assert first == second
    assert "mut ir_local_records: i64[365]" in first
    assert "local_capture_storage_kind = 2" in first
    assert "local_capture_extent = value" in first
    assert "local_verify_storage_kind" in first
    assert "local_verify_extent" in first
    assert first.count("\nfn ") == parameter_source.count("\nfn ")
    assert first.count("\nforeign fn ") == parameter_source.count("\nforeign fn ")


def test_local_transform_rejects_unbounded_capacity() -> None:
    parameter_source = _parameter_source()
    with pytest.raises(LocalCandidateError, match="1..365"):
        transform_locals(parameter_source, local_capacity=366)


def test_native_local_count_mismatch_fails_closed_before_local_qualification() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    result = build_preflight(
        _native_parameter_report(local_count_delta=1),
        canonical_source=canonical,
    )
    assert result["status"] == "BLOCKED_STAGE1_NATIVE_LEXICAL_MODEL_MISMATCH"
    assert result["native_model_guards"]["local_count_matches_stage1_hash87_tokens"] is False
    assert result["local_native_qualification_allowed"] is False
    assert result["canonical_commit_allowed"] is False


def test_exact_preflight_consumes_native_report_and_never_promotes_source() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    result = build_preflight(_native_parameter_report(), canonical_source=canonical)
    assert result["native_parameter_evidence_consumed"] is True
    assert result["canonical_source_mutated"] is False
    assert result["canonical_commit_allowed"] is False
    assert all(result["native_model_guards"].values())
    local = result["local_candidate"]
    required = local["required_records_including_candidate_self_source"]
    selected = local["selected_capacity"]
    if required <= 365:
        assert selected == required
        assert local["capacity_headroom"] == 0
        assert local["storage_kind_preserved"] is True
        assert local["fixed_array_extent_preserved"] is True
    else:
        assert selected is None
        assert result["status"] == "BLOCKED_LOCAL_RECORDS_EXCEED_SINGLE_365_BANK"
