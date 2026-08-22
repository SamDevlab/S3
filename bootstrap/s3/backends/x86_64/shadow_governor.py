"""Research-only static Shadow Governor for native policy experiments.

The compiler does not call this module from the normal backend path.  It is a
small, deterministic decision rule used by the attribution laboratory to
select a counterfactual policy from a caller-provided eligible set.
"""

from __future__ import annotations

from dataclasses import dataclass

from .features import FunctionFeatureVector
from .policy import NativePolicy


@dataclass(frozen=True, slots=True)
class ShadowDecision:
    policy_id: str
    reason: str
    fallback_used: bool


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
    ) -> ShadowDecision:
        if self.baseline_policy_id not in policies:
            raise ValueError("eligible policies must include the baseline")
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

        ordered = sorted(policies.items())
        if features.indexed_memory_ops:
            for policy_id, policy in ordered:
                if policy.indexed_memory_policy == "compact_ea":
                    if features.mutable_scalar_candidates and policy.scalar_promotion == "conservative_mem2reg":
                        return ShadowDecision(policy_id, "indexed_memory_and_proven_scalar", False)
                    return ShadowDecision(policy_id, "indexed_memory_without_escape", False)
        if features.mutable_scalar_candidates:
            for policy_id, policy in ordered:
                if policy.scalar_promotion == "conservative_mem2reg":
                    return ShadowDecision(policy_id, "alias_safe_scalar_memory", False)
        if features.loop_count and features.estimated_spill_pressure:
            for policy_id, policy in ordered:
                if policy.spill_policy == "region_aware":
                    return ShadowDecision(policy_id, "localized_loop_pressure", False)
        if features.rematerializable_value_count and features.estimated_spill_pressure:
            for policy_id, policy in ordered:
                if policy.rematerialization == "const_only":
                    return ShadowDecision(policy_id, "pure_constant_under_pressure", False)
        return ShadowDecision(self.baseline_policy_id, "insufficient_structural_evidence", True)
