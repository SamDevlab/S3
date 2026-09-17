"""Supported native code-generation policy selection for x86-64."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ...assembly import AssemblyFunction, AssemblyOpcode, AssemblyType
from .register_init_safety import proven_initialized_register_reads


class NativeCodegenPolicy(StrEnum):
    """Explicit policies understood by the native x86-64 backend."""

    BASELINE = "baseline"
    COMPACT_EA = "compact-ea"


def parse_native_codegen_policy(
    value: str | NativeCodegenPolicy | None,
) -> NativeCodegenPolicy:
    if value is None:
        return NativeCodegenPolicy.BASELINE
    try:
        return NativeCodegenPolicy(value)
    except ValueError as error:
        raise ValueError(f"unsupported native codegen policy: {value!r}") from error


@dataclass(frozen=True, slots=True)
class NativePolicyDecision:
    requested_policy: NativeCodegenPolicy
    effective_policy: NativeCodegenPolicy
    applied: bool
    reason: str
    sites_considered: int

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy": self.requested_policy.value,
            "effective_policy": self.effective_policy.value,
            "applied": self.applied,
            "reason": self.reason,
            "sites_considered": self.sites_considered,
        }


@dataclass(frozen=True, slots=True)
class NativePolicySummary:
    requested_policy: NativeCodegenPolicy
    effective_policy: NativeCodegenPolicy
    functions_considered: int
    functions_optimized: int
    functions_fallback: int
    fallback_reason_counts: dict[str, int]
    compact_ea_sites_considered: int
    compact_ea_sites_applied: int
    function_decisions: dict[str, NativePolicyDecision]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy": self.requested_policy.value,
            "effective_policy": self.effective_policy.value,
            "functions_considered": self.functions_considered,
            "functions_optimized": self.functions_optimized,
            "functions_fallback": self.functions_fallback,
            "fallback_reason_counts": dict(self.fallback_reason_counts),
            "compact_ea_sites_considered": self.compact_ea_sites_considered,
            "compact_ea_sites_applied": self.compact_ea_sites_applied,
            "function_decisions": {
                name: decision.to_dict()
                for name, decision in self.function_decisions.items()
            },
        }


def _index_register(instruction: object) -> int | None:
    opcode = getattr(instruction, "opcode", None)
    registers = getattr(instruction, "registers", ())
    if opcode is AssemblyOpcode.TLOAD:
        return registers[1] if len(registers) >= 2 else None
    if opcode is AssemblyOpcode.TSTORE:
        return registers[0] if registers else None
    return None


def _indexed_site_count(function: AssemblyFunction) -> int:
    return sum(
        _index_register(instruction) is not None
        for instruction in function.instructions
    )


def indexed_site_count(function: AssemblyFunction) -> int:
    """Return the number of indexed memory sites considered by Compact EA."""

    return _indexed_site_count(function)


def _compact_ea_safety_reason(function: AssemblyFunction) -> str | None:
    indexed_memory_ops = False
    initialized_reads = proven_initialized_register_reads(function)
    memory_types = {
        memory.index: memory.element_type
        for memory in function.memory_objects
    }
    supported_element_types = {
        AssemblyType.TRIT,
        AssemblyType.TRYTE,
        AssemblyType.I64,
        AssemblyType.F64,
    }

    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode in {
                AssemblyOpcode.TADDR,
                AssemblyOpcode.TREFLOAD,
                AssemblyOpcode.TREFSTORE,
                AssemblyOpcode.TSLEN,
                AssemblyOpcode.TSLOAD,
                AssemblyOpcode.TSSTORE,
            }:
                return "reference_operations_present"
            index_register = _index_register(instruction)
            if index_register is None:
                continue
            indexed_memory_ops = True
            if (block.label, index, index_register) not in initialized_reads:
                return "index_initialization_not_proven"
            if function.type_of(index_register) not in {
                AssemblyType.TRYTE,
                AssemblyType.I64,
            }:
                return "unsupported_index_type"
            element_type = memory_types.get(instruction.memory)
            if element_type not in supported_element_types:
                return "unsupported_memory_element_type"

    if any(instruction.opcode is AssemblyOpcode.TCALL for instruction in function.instructions):
        return "calls_or_cross_call_liveness_present"
    if not indexed_memory_ops:
        return "no_indexed_memory_operations"
    return None


def resolve_native_policy(
    function: AssemblyFunction,
    policy: NativeCodegenPolicy | str | None,
) -> NativePolicyDecision:
    requested = parse_native_codegen_policy(policy)
    sites = _indexed_site_count(function)
    if requested is NativeCodegenPolicy.BASELINE:
        return NativePolicyDecision(
            requested,
            NativeCodegenPolicy.BASELINE,
            False,
            "baseline_default",
            0,
        )
    reason = _compact_ea_safety_reason(function)
    if reason is not None:
        return NativePolicyDecision(
            requested,
            NativeCodegenPolicy.BASELINE,
            False,
            f"compact_ea_fallback:{reason}",
            sites,
        )
    return NativePolicyDecision(
        requested,
        NativeCodegenPolicy.COMPACT_EA,
        True,
        "compact_ea_applied",
        sites,
    )


def resolve_native_policies(
    functions: tuple[AssemblyFunction, ...] | list[AssemblyFunction],
    policy: NativeCodegenPolicy | str | None,
) -> dict[str, NativePolicyDecision]:
    requested = parse_native_codegen_policy(policy)
    return {
        function.name: resolve_native_policy(function, requested)
        for function in sorted(functions, key=lambda item: item.name)
    }


def summarize_native_policy(
    functions: tuple[AssemblyFunction, ...] | list[AssemblyFunction],
    policy: NativeCodegenPolicy | str | None,
    *,
    decisions: dict[str, NativePolicyDecision] | None = None,
) -> NativePolicySummary:
    requested = parse_native_codegen_policy(policy)
    considered = tuple(
        sorted(
            (function for function in functions if not function.external),
            key=lambda item: item.name,
        )
    )
    resolved_decisions = decisions or {
        function.name: resolve_native_policy(function, requested)
        for function in considered
    }
    resolved_decisions = {
        function.name: resolved_decisions[function.name]
        for function in considered
    }
    optimized = tuple(
        decision for decision in resolved_decisions.values() if decision.applied
    )
    fallbacks = tuple(
        decision
        for decision in resolved_decisions.values()
        if decision.reason.startswith("compact_ea_fallback:")
    )
    reason_counts: dict[str, int] = {}
    for decision in fallbacks:
        reason = decision.reason.split(":", 1)[1]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    reason_counts = dict(sorted(reason_counts.items()))
    sites_considered = (
        sum(decision.sites_considered for decision in resolved_decisions.values())
        if requested is NativeCodegenPolicy.COMPACT_EA
        else 0
    )
    sites_applied = sum(
        decision.sites_considered for decision in optimized
    )
    effective = (
        NativeCodegenPolicy.COMPACT_EA
        if optimized
        else NativeCodegenPolicy.BASELINE
    )
    return NativePolicySummary(
        requested,
        effective,
        len(considered),
        len(optimized),
        len(fallbacks),
        reason_counts,
        sites_considered,
        sites_applied,
        resolved_decisions,
    )
