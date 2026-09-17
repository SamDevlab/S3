"""Compatibility shim for the pre-1.2 Compact EA canary API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ...assembly import AssemblyFunction
from .native_policy import (
    NativeCodegenPolicy,
    _compact_ea_safety_reason,
    resolve_native_policy,
)


class ExperimentalNativePolicyMode(StrEnum):
    OFF = "off"
    COMPACT_EA_CANARY = "compact-ea-canary"


@dataclass(frozen=True, slots=True)
class CompactEACanarySelection:
    applied: bool
    reason: str


def parse_experimental_native_policy_mode(
    value: str | ExperimentalNativePolicyMode | None,
) -> ExperimentalNativePolicyMode:
    if value is None:
        return ExperimentalNativePolicyMode.OFF
    try:
        return ExperimentalNativePolicyMode(value)
    except ValueError as error:
        raise ValueError(
            f"unsupported experimental native policy mode: {value!r}"
        ) from error


def _canary_safety_reason(function: AssemblyFunction) -> str | None:
    return _compact_ea_safety_reason(function)


def resolve_compact_ea_canary(
    function: AssemblyFunction,
    mode: ExperimentalNativePolicyMode | str | None,
) -> CompactEACanarySelection:
    normalized = parse_experimental_native_policy_mode(mode)
    if normalized is ExperimentalNativePolicyMode.OFF:
        return CompactEACanarySelection(False, "mode_off")
    decision = resolve_native_policy(function, NativeCodegenPolicy.COMPACT_EA)
    if not decision.applied:
        return CompactEACanarySelection(
            False,
            decision.reason.replace("compact_ea_fallback:", "canary_safety_fallback:"),
        )
    return CompactEACanarySelection(True, "canary_compact_ea_eligible")


def resolve_compact_ea_canaries(
    functions: tuple[AssemblyFunction, ...] | list[AssemblyFunction],
    mode: ExperimentalNativePolicyMode | str | None,
) -> dict[str, CompactEACanarySelection]:
    return {
        function.name: resolve_compact_ea_canary(function, mode)
        for function in functions
    }
