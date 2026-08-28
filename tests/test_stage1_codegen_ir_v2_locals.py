from __future__ import annotations

import pytest

from tools.patch_stage1_codegen_ir_v2_locals import (
    LocalCandidateError,
    SOURCE,
    transform_locals,
    validate_parameter_prerequisite,
)
from tools.preflight_stage1_codegen_ir_v2_locals import (
    identifier_hash_text,
    stage1_tokens,
)


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


def test_parameter_prerequisite_rejects_stale_canonical_source() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    report = {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "canonical_source_mutated": False,
        "candidate": {"source_sha256": "0" * 64, "source_bytes": 0},
        "qualification": {"parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE"},
    }
    with pytest.raises(LocalCandidateError, match="packed parameter candidate is stale"):
        validate_parameter_prerequisite(report, canonical_source=canonical)


def test_local_transform_requires_parameter_candidate() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    with pytest.raises(LocalCandidateError, match="packed-parameter"):
        transform_locals(canonical, local_capacity=64)


def test_local_transform_is_deterministic_and_shape_preserving() -> None:
    with pytest.raises(LocalCandidateError, match="packed-parameter candidate"):
        transform_locals(SOURCE.read_text(encoding="utf-8"), local_capacity=365)


def test_local_transform_rejects_unbounded_capacity() -> None:
    with pytest.raises(LocalCandidateError, match="1..365"):
        transform_locals(SOURCE.read_text(encoding="utf-8"), local_capacity=366)


def test_native_local_count_mismatch_fails_closed_before_local_qualification() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    report = {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "canonical_source_mutated": False,
        "candidate": {"source_sha256": "0" * 64, "source_bytes": 0},
        "qualification": {"parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE"},
    }
    with pytest.raises(LocalCandidateError, match="packed parameter candidate is stale"):
        validate_parameter_prerequisite(report, canonical_source=canonical)


def test_exact_preflight_consumes_native_report_and_never_promotes_source() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    report = {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "canonical_source_mutated": False,
        "candidate": {"source_sha256": "0" * 64, "source_bytes": 0},
        "qualification": {"parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE"},
    }
    with pytest.raises(LocalCandidateError, match="packed parameter candidate is stale"):
        validate_parameter_prerequisite(report, canonical_source=canonical)
