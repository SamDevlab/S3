"""M2.48 fail-closed experiment promotion contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.experiment_promotion import (
    PromotionContract,
    PromotionFrameworkError,
    PromotionStatus,
    resolve_promotion,
)


SOURCE = "a" * 40


def _contract(**changes: object) -> PromotionContract:
    values: dict[str, object] = {
        "component_id": "compact-ea-canary",
        "source_lock_sha": SOURCE,
        "eligible": True,
        "correctness_evidence": "PASS",
        "structural_evidence": "PASS",
    }
    values.update(changes)
    return PromotionContract(**values)


def test_candidate_stays_off_without_explicit_opt_in() -> None:
    decision = resolve_promotion(_contract(), observed_source_sha=SOURCE)
    assert decision.status is PromotionStatus.OFF_BY_DEFAULT
    assert decision.selected is False
    assert decision.fallback_used is False


def test_explicit_opt_in_selects_only_locked_eligible_candidate() -> None:
    decision = resolve_promotion(
        _contract(), observed_source_sha=SOURCE, explicit_opt_in=True
    )
    assert decision.status is PromotionStatus.CANDIDATE_SELECTED
    assert decision.selected is True
    assert decision.source_lock_match is True


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"eligible": False}, "eligibility_not_satisfied"),
        ({"correctness_evidence": "FAIL"}, "correctness_evidence_not_satisfied"),
        ({"structural_evidence": "NOT_RUN"}, "structural_evidence_not_satisfied"),
    ],
)
def test_failed_promotion_gate_uses_fallback(
    changes: dict[str, object], reason: str
) -> None:
    decision = resolve_promotion(
        _contract(**changes), observed_source_sha=SOURCE, explicit_opt_in=True
    )
    assert decision.status is PromotionStatus.FALLBACK
    assert decision.fallback_used is True
    assert decision.reason == reason


def test_source_lock_mismatch_uses_fallback() -> None:
    decision = resolve_promotion(
        _contract(), observed_source_sha="b" * 40, explicit_opt_in=True
    )
    assert decision.status is PromotionStatus.FALLBACK
    assert decision.source_lock_match is False
    assert decision.reason == "source_lock_mismatch"


def test_default_activation_is_rejected() -> None:
    with pytest.raises(PromotionFrameworkError, match="OFF by default"):
        resolve_promotion(
            _contract(default_enabled=True), observed_source_sha=SOURCE
        )


def test_missing_fallback_is_rejected() -> None:
    with pytest.raises(PromotionFrameworkError, match="fallback"):
        resolve_promotion(
            _contract(fallback_available=False), observed_source_sha=SOURCE
        )


def test_invalid_source_lock_is_rejected() -> None:
    with pytest.raises(PromotionFrameworkError, match="source SHA"):
        resolve_promotion(
            _contract(source_lock_sha="not-a-sha"), observed_source_sha=SOURCE
        )

