"""Explicit, conservative memory effects for reference-aware IR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .ir import IRFunction, IRInstruction, IROpcode, IRType


class MemoryEffect(Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    READ_WRITE = "read_write"


@dataclass(frozen=True, slots=True)
class MemoryRegion:
    """Logical storage identity, never a host or machine address."""

    root: object
    projection: object = None


def may_alias(left: MemoryRegion, right: MemoryRegion) -> bool:
    if left.root != right.root:
        return False
    if left.projection == right.projection:
        return True
    if left.projection is None or right.projection is None:
        return True
    if isinstance(left.projection, tuple) and isinstance(right.projection, tuple):
        if left.projection[0] == right.projection[0] == "element":
            if left.projection[1] is None or right.projection[1] is None:
                return True
            return left.projection[1] == right.projection[1]
    return True


def instruction_memory_effect(function: IRFunction, instruction: IRInstruction) -> MemoryEffect:
    if instruction.opcode is IROpcode.LOAD:
        return MemoryEffect.READ
    if instruction.opcode is IROpcode.STORE:
        return MemoryEffect.WRITE
    if instruction.opcode is IROpcode.REFERENCE_LOAD:
        return MemoryEffect.READ
    if instruction.opcode in {IROpcode.AGGREGATE_FIELD_LOAD, IROpcode.AGGREGATE_FIELD_ADDRESS}:
        return MemoryEffect.READ
    if instruction.opcode is IROpcode.REFERENCE_STORE:
        return MemoryEffect.READ_WRITE
    if instruction.opcode is IROpcode.CALL:
        effect = MemoryEffect.NONE
        for register in instruction.operands:
            info = next((item for item in function.registers if item.index == register), None)
            if info is None or info.type is not IRType.REFERENCE:
                continue
            current = MemoryEffect.READ_WRITE if info.reference_mutable else MemoryEffect.READ
            if current is MemoryEffect.READ_WRITE:
                return current
            if current is MemoryEffect.READ:
                effect = current
        return effect
    return MemoryEffect.NONE


def function_has_memory_effects(function: IRFunction) -> bool:
    return any(
        instruction_memory_effect(function, instruction) is not MemoryEffect.NONE
        for block in function.blocks
        for instruction in block.instructions
    )


def function_has_alias_observable_memory(function: IRFunction) -> bool:
    """Return whether IR exposes storage through a reference-capable path."""

    for instruction in function.instructions:
        if instruction.opcode in {
            IROpcode.ADDRESS_OF,
            IROpcode.AGGREGATE_ADDRESS_OF,
            IROpcode.AGGREGATE_FIELD_LOAD,
            IROpcode.AGGREGATE_FIELD_ADDRESS,
            IROpcode.REFERENCE_LOAD,
            IROpcode.REFERENCE_STORE,
        }:
            return True
        if instruction.opcode is IROpcode.CALL and any(
            next(
                (
                    register.type is IRType.REFERENCE
                    for register in function.registers
                    if register.index == operand
                ),
                False,
            )
            for operand in instruction.operands
        ):
            return True
    return False
