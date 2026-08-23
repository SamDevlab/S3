"""Fail-closed promotion decisions for experimental compiler components."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import re
from typing import Any


_SOURCE_SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_EVIDENCE_STATES = {"PASS", "FAIL", "NOT_RUN"}


class PromotionFrameworkError(ValueError):
    """Raised when an experimental promotion contract is unsafe or invalid."""


class PromotionStatus(StrEnum):
    OFF_BY_DEFAULT = "OFF_BY_DEFAULT"
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    FALLBACK = "FALLBACK"


def _require_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PromotionFrameworkError(f"{field} must be non-empty")


def _require_source_sha(value: object, field: str) -> None:
    if not isinstance(value, str) or _SOURCE_SHA.fullmatch(value) is None:
        raise PromotionFrameworkError(f"{field} must be a lowercase source SHA")


def _require_bool(value: object, field: str) -> None:
    if not isinstance(value, bool):
        raise PromotionFrameworkError(f"{field} must be boolean")


@dataclass(frozen=True, slots=True)
class PromotionContract:
    """Evidence and policy required before an experimental path is selected."""

    component_id: str
    source_lock_sha: str
    eligible: bool
    correctness_evidence: str
    structural_evidence: str
    fallback_available: bool = True
    default_enabled: bool = False

    def validate(self) -> None:
        _require_text(self.component_id, "component_id")
        _require_source_sha(self.source_lock_sha, "source_lock_sha")
        _require_bool(self.eligible, "eligible")
        _require_bool(self.fallback_available, "fallback_available")
        _require_bool(self.default_enabled, "default_enabled")
        for field, value in (
            ("correctness_evidence", self.correctness_evidence),
            ("structural_evidence", self.structural_evidence),
        ):
            if value not in _EVIDENCE_STATES:
                raise PromotionFrameworkError(f"{field} has invalid state: {value!r}")
        if self.default_enabled:
            raise PromotionFrameworkError(
                "experimental promotion must remain OFF by default"
            )
        if not self.fallback_available:
            raise PromotionFrameworkError(
                "experimental promotion requires an available fallback"
            )


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    component_id: str
    status: PromotionStatus
    selected: bool
    fallback_used: bool
    source_lock_match: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_promotion(
    contract: PromotionContract,
    *,
    observed_source_sha: str,
    explicit_opt_in: bool = False,
) -> PromotionDecision:
    """Resolve a candidate without ever enabling it implicitly."""

    contract.validate()
    _require_source_sha(observed_source_sha, "observed_source_sha")
    _require_bool(explicit_opt_in, "explicit_opt_in")

    source_lock_match = observed_source_sha == contract.source_lock_sha
    if not source_lock_match:
        return _fallback(contract, False, "source_lock_mismatch")
    if not explicit_opt_in:
        return PromotionDecision(
            contract.component_id,
            PromotionStatus.OFF_BY_DEFAULT,
            False,
            False,
            True,
            "explicit_opt_in_required",
        )
    for field, value in (
        ("eligibility", contract.eligible),
        ("correctness_evidence", contract.correctness_evidence == "PASS"),
        ("structural_evidence", contract.structural_evidence == "PASS"),
    ):
        if not value:
            return _fallback(contract, True, f"{field}_not_satisfied")
    return PromotionDecision(
        contract.component_id,
        PromotionStatus.CANDIDATE_SELECTED,
        True,
        False,
        True,
        "explicit_opt_in_and_all_gates_pass",
    )


def _fallback(
    contract: PromotionContract,
    source_lock_match: bool,
    reason: str,
) -> PromotionDecision:
    return PromotionDecision(
        contract.component_id,
        PromotionStatus.FALLBACK,
        False,
        True,
        source_lock_match,
        reason,
    )

