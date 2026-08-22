"""Research-only static Shadow Governor for native policy experiments.

The compiler does not call this module from the normal backend path.  It is a
small, deterministic decision rule used by the attribution laboratory to
select a counterfactual policy from a caller-provided eligible set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .features import FunctionFeatureVector
from .policy import NativePolicy


@dataclass(frozen=True, slots=True)
class ShadowDecision:
    policy_id: str
    reason: str
    fallback_used: bool


ALLOWED_V22_POLICY_IDS = frozenset({
    "BASELINE",
    "COMPACT_EA",
    "SCALAR",
    "COMPACT_EA_SCALAR",
})


def _hard_regression(candidate: Mapping[str, int], baseline: Mapping[str, int]) -> bool:
    for key, limit in (
        ("instructions", 1.03),
        ("total_load_store", 1.05),
        ("stack_ops", 1.05),
        ("spills_reload", 1.05),
        ("frame_bytes", 1.05),
    ):
        base = int(baseline.get(key, 0))
        value = int(candidate.get(key, 0))
        if base and value / base > limit:
            return True
    return False


class ShadowGovernor:
    """Select a conservative research policy from static function facts only."""

    def __init__(self, baseline_policy_id: str) -> None:
        if not baseline_policy_id:
            raise ValueError("baseline_policy_id must be non-empty")
        self.baseline_policy_id = baseline_policy_id

    def recommend(
        self,
        features: FunctionFeatureVector,
        policies: dict[str, NativePolicy],
        *,
        baseline_metrics: Mapping[str, int] | None = None,
        candidate_metrics: Mapping[str, Mapping[str, int]] | None = None,
    ) -> ShadowDecision:
        if self.baseline_policy_id not in policies:
            raise ValueError("eligible policies must include the baseline")
        if any(policy_id not in ALLOWED_V22_POLICY_IDS for policy_id in policies):
            return ShadowDecision(
                self.baseline_policy_id,
                "non_v22_policy_set_fallback",
                True,
            )
        if features.reference_ops or features.address_taken_values:
            return ShadowDecision(
                self.baseline_policy_id,
                "reference_or_address_escape_fallback",
                True,
            )
        if features.call_count or features.live_across_call_count:
            return ShadowDecision(
                self.baseline_policy_id,
                "call_barrier_fallback",
                True,
            )

        if features.indexed_memory_ops and features.mutable_scalar_candidates:
            selected = "COMPACT_EA_SCALAR"
            reason = "indexed_memory_and_alias_safe_scalar"
        elif features.indexed_memory_ops:
            selected = "COMPACT_EA"
            reason = "indexed_memory_without_escape"
        elif features.mutable_scalar_candidates and not features.estimated_spill_pressure:
            selected = "SCALAR"
            reason = "alias_safe_scalar_without_pressure"
        else:
            return ShadowDecision(self.baseline_policy_id, "insufficient_structural_evidence", True)

        if selected not in policies:
            return ShadowDecision(self.baseline_policy_id, "qualified_policy_unavailable", True)
        if baseline_metrics is not None and candidate_metrics is not None:
            candidate = candidate_metrics.get(selected)
            if candidate is None or _hard_regression(candidate, baseline_metrics):
                return ShadowDecision(
                    self.baseline_policy_id,
                    reason + "_hard_regression_fallback",
                    True,
                )
        return ShadowDecision(selected, reason, False)
