"""Explicitly opt-in policy modes for the native-policy research lab.

This module is intentionally disconnected from the default backend entrypoint.
It provides a narrow internal boundary for V2.2 experiments; no mode is a
stable public API and the default remains ``off``.
"""

from __future__ import annotations

from enum import StrEnum

from .features import FunctionFeatureVector
from .policy import BASELINE_NATIVE_POLICY, NativePolicy
from .shadow_governor import ALLOWED_V22_POLICY_IDS


class ExperimentalNativePolicyMode(StrEnum):
    OFF = "off"
    SHADOW = "shadow"
    COMPACT_EA_CANARY = "compact-ea-canary"


def parse_experimental_native_policy_mode(value: str | None) -> ExperimentalNativePolicyMode:
    if value is None:
        return ExperimentalNativePolicyMode.OFF
    try:
        return ExperimentalNativePolicyMode(value)
    except ValueError as error:
        raise ValueError(f"unsupported experimental native policy mode: {value!r}") from error


def compact_ea_canary_eligible(features: FunctionFeatureVector) -> bool:
    """Return the conservative static safety proof used by the canary."""

    return bool(
        features.indexed_memory_ops
        and not features.reference_ops
        and not features.address_taken_values
        and not features.call_count
    )


def select_experimental_policy(
    mode: ExperimentalNativePolicyMode,
    features: FunctionFeatureVector,
    policies: dict[str, NativePolicy],
) -> tuple[str, str]:
    """Select an internal policy and explain every fallback."""

    if "BASELINE" not in policies:
        raise ValueError("experimental policy set must include BASELINE")
    if any(policy_id not in ALLOWED_V22_POLICY_IDS for policy_id in policies):
        return "BASELINE", "non_v22_policy_set_fallback"
    if mode is ExperimentalNativePolicyMode.OFF:
        return "BASELINE", "mode_off"
    if mode is ExperimentalNativePolicyMode.SHADOW:
        return "BASELINE", "shadow_keeps_official_output_baseline"
    if not compact_ea_canary_eligible(features):
        return "BASELINE", "canary_safety_fallback"
    if "COMPACT_EA" not in policies:
        return "BASELINE", "canary_policy_unavailable"
    return "COMPACT_EA", "canary_compact_ea_eligible"


def default_policy() -> NativePolicy:
    """Return the canonical policy used by the default/off path."""

    return BASELINE_NATIVE_POLICY
