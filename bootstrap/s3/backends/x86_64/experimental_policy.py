"""Explicitly opt-in policy modes for the native-policy research lab.

This module is intentionally disconnected from the default backend entrypoint.
It provides a narrow internal boundary for V2.2 experiments; no mode is a
stable public API and the default remains ``off``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from ...assembly import AssemblyFunction, AssemblyOpcode, AssemblyType
from .features import FunctionFeatureVector, extract_function_features
from .policy import BASELINE_NATIVE_POLICY, NativePolicy, policy_with
from .register_init_safety import proven_initialized_register_reads
from .shadow_governor import ALLOWED_V22_POLICY_IDS


class ExperimentalNativePolicyMode(StrEnum):
    OFF = "off"
    SHADOW = "shadow"
    COMPACT_EA_CANARY = "compact-ea-canary"


@dataclass(frozen=True, slots=True)
class ExperimentalPolicySelection:
    """Function-local result of the explicit experimental policy gate."""

    policy: NativePolicy
    policy_id: str
    applied: bool
    reason: str


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


def compact_ea_canary_policy() -> NativePolicy:
    """Return the V2.3 canary with exactly one experimental policy dimension."""

    return policy_with(
        BASELINE_NATIVE_POLICY,
        name="v23_compact_ea_canary",
        indexed_memory_policy="compact_ea",
    )


def _index_register(instruction: object) -> int | None:
    if getattr(instruction, "opcode", None) is AssemblyOpcode.TLOAD:
        registers = getattr(instruction, "registers", ())
        return registers[1] if len(registers) >= 2 else None
    if getattr(instruction, "opcode", None) is AssemblyOpcode.TSTORE:
        registers = getattr(instruction, "registers", ())
        return registers[0] if registers else None
    return None


def _canary_safety_reason(function: AssemblyFunction) -> str | None:
    """Return a conservative fallback reason, or ``None`` when safe."""

    features = extract_function_features(function)
    if not features.indexed_memory_ops:
        return "no_indexed_memory_operations"
    if features.reference_ops:
        return "reference_operations_present"
    if features.address_taken_values:
        return "address_taken_values_present"
    if features.call_count or features.live_across_call_count:
        return "calls_or_cross_call_liveness_present"

    initialized_reads = proven_initialized_register_reads(function)
    memory_types = {
        memory.index: memory.element_type for memory in function.memory_objects
    }
    supported_element_types = {
        AssemblyType.TRIT,
        AssemblyType.TRYTE,
        AssemblyType.I64,
        AssemblyType.F64,
    }
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            index_register = _index_register(instruction)
            if index_register is None:
                continue
            if (block.label, index, index_register) not in initialized_reads:
                return "index_initialization_not_proven"
            if function.type_of(index_register) not in {
                AssemblyType.TRYTE,
                AssemblyType.I64,
            }:
                return "unsupported_index_type"
            element_type = memory_types.get(getattr(instruction, "memory", None))
            if element_type not in supported_element_types:
                return "unsupported_memory_element_type"
    return None


def resolve_experimental_policy(
    function: AssemblyFunction,
    mode: ExperimentalNativePolicyMode | str | None,
) -> ExperimentalPolicySelection:
    """Resolve one function's explicit V2.3 mode without benchmark identity."""

    normalized = parse_experimental_native_policy_mode(mode)
    if normalized is ExperimentalNativePolicyMode.OFF:
        return ExperimentalPolicySelection(
            BASELINE_NATIVE_POLICY,
            BASELINE_NATIVE_POLICY.name,
            False,
            "mode_off",
        )
    if normalized is ExperimentalNativePolicyMode.SHADOW:
        return ExperimentalPolicySelection(
            BASELINE_NATIVE_POLICY,
            BASELINE_NATIVE_POLICY.name,
            False,
            "shadow_keeps_official_output_baseline",
        )
    reason = _canary_safety_reason(function)
    if reason is not None:
        return ExperimentalPolicySelection(
            BASELINE_NATIVE_POLICY,
            BASELINE_NATIVE_POLICY.name,
            False,
            f"canary_safety_fallback:{reason}",
        )
    policy = compact_ea_canary_policy()
    return ExperimentalPolicySelection(
        policy,
        policy.name,
        True,
        "canary_compact_ea_eligible",
    )


def resolve_experimental_policies(
    functions: Mapping[str, AssemblyFunction] | object,
    mode: ExperimentalNativePolicyMode | str | None,
) -> dict[str, ExperimentalPolicySelection]:
    """Resolve policies independently for every function in a program."""

    if hasattr(functions, "functions"):
        functions = getattr(functions, "functions")
    if isinstance(functions, Mapping):
        items = functions.items()
    else:
        items = ((function.name, function) for function in functions)
    return {
        name: resolve_experimental_policy(function, mode)
        for name, function in items
    }


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
