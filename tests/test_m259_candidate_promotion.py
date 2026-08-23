"""M2.59 candidate metadata and promotion integration contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from bootstrap.s3.differential import DifferentialHarness
from bootstrap.s3.experiment_promotion import PromotionFrameworkError, PromotionStatus
from bootstrap.s3.promotion_integration import (
    CandidateMetadata,
    CandidatePromotionError,
    resolve_candidate_promotion,
)


SOURCE = "a" * 40
COMPONENT = "self-hosted-text"


def _metadata(*, matching: bool = True, **changes: object) -> CandidateMetadata:
    provenance = {
        "component_id": COMPONENT,
        "source_lock_sha": SOURCE,
        "origin": "m2.59-fixture",
    }
    result = DifferentialHarness().run(
        "candidate-case",
        {"value": 4, "order": ["a", "b"]},
        lambda value: {"result": value["value"] + 1},
        (lambda value: {"result": value["value"] + 1})
        if matching
        else (lambda value: {"result": value["value"] + 2}),
        provenance=provenance,
    )
    values: dict[str, object] = {
        "component_id": COMPONENT,
        "source_lock_sha": SOURCE,
        "provenance": provenance,
        "differential_result": result,
    }
    values.update(changes)
    return CandidateMetadata(**values)


def test_valid_metadata_stays_off_by_default_and_selects_with_exact_opt_in() -> None:
    metadata = _metadata()
    off = resolve_candidate_promotion(metadata, observed_source_sha=SOURCE)
    assert off.status is PromotionStatus.OFF_BY_DEFAULT
    assert off.selected is False

    selected = resolve_candidate_promotion(
        metadata, observed_source_sha=SOURCE, explicit_opt_in=True
    )
    assert selected.status is PromotionStatus.CANDIDATE_SELECTED
    assert selected.source_lock_match is True


def test_source_mismatch_uses_shared_fallback() -> None:
    decision = resolve_candidate_promotion(
        _metadata(), observed_source_sha="b" * 40, explicit_opt_in=True
    )
    assert decision.status is PromotionStatus.FALLBACK
    assert decision.reason == "source_lock_mismatch"


def test_differential_mismatch_becomes_correctness_fallback() -> None:
    decision = resolve_candidate_promotion(
        _metadata(matching=False), observed_source_sha=SOURCE, explicit_opt_in=True
    )
    assert decision.status is PromotionStatus.FALLBACK
    assert decision.reason == "correctness_evidence_not_satisfied"


def test_provenance_must_bind_component_and_source_lock() -> None:
    metadata = _metadata()
    with pytest.raises(CandidatePromotionError, match="source mismatch"):
        resolve_candidate_promotion(
            replace(metadata, source_lock_sha="b" * 40),
            observed_source_sha="b" * 40,
            explicit_opt_in=True,
        )


def test_tampered_input_digest_fails_closed() -> None:
    metadata = _metadata()
    tampered = replace(
        metadata.differential_result,
        input_json='{"value":5}\n',
    )
    with pytest.raises(CandidatePromotionError, match="input digest"):
        resolve_candidate_promotion(
            replace(metadata, differential_result=tampered),
            observed_source_sha=SOURCE,
            explicit_opt_in=True,
        )


def test_structural_failure_uses_shared_fallback() -> None:
    decision = resolve_candidate_promotion(
        _metadata(structural_evidence="FAIL"),
        observed_source_sha=SOURCE,
        explicit_opt_in=True,
    )
    assert decision.status is PromotionStatus.FALLBACK
    assert decision.reason == "structural_evidence_not_satisfied"


def test_default_enabled_candidate_is_rejected() -> None:
    with pytest.raises(PromotionFrameworkError, match="OFF by default"):
        resolve_candidate_promotion(
            _metadata(default_enabled=True),
            observed_source_sha=SOURCE,
            explicit_opt_in=True,
        )
