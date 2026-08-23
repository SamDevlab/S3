"""Explicit, fail-closed Compact EA canary selection for the native backend.

This is an internal experimental boundary. The default backend path remains
canonical and the canary is enabled only by an explicit backend mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ...assembly import AssemblyFunction, AssemblyOpcode, AssemblyType
from .register_init_safety import proven_initialized_register_reads


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


def _index_register(instruction: object) -> int | None:
    opcode = getattr(instruction, "opcode", None)
    registers = getattr(instruction, "registers", ())
    if opcode is AssemblyOpcode.TLOAD:
        return registers[1] if len(registers) >= 2 else None
    if opcode is AssemblyOpcode.TSTORE:
        return registers[0] if registers else None
    return None


def _canary_safety_reason(function: AssemblyFunction) -> str | None:
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


def resolve_compact_ea_canary(
    function: AssemblyFunction,
    mode: ExperimentalNativePolicyMode | str | None,
) -> CompactEACanarySelection:
    normalized = parse_experimental_native_policy_mode(mode)
    if normalized is ExperimentalNativePolicyMode.OFF:
        return CompactEACanarySelection(False, "mode_off")
    reason = _canary_safety_reason(function)
    if reason is not None:
        return CompactEACanarySelection(False, f"canary_safety_fallback:{reason}")
    return CompactEACanarySelection(True, "canary_compact_ea_eligible")


def resolve_compact_ea_canaries(
    functions: tuple[AssemblyFunction, ...] | list[AssemblyFunction],
    mode: ExperimentalNativePolicyMode | str | None,
) -> dict[str, CompactEACanarySelection]:
    return {
        function.name: resolve_compact_ea_canary(function, mode)
        for function in functions
    }
