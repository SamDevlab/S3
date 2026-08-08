"""Deterministic stack-frame layout for the Linux x86-64 backend."""

from __future__ import annotations

from dataclasses import dataclass

from ...assembly import (
    AssemblyFunction,
    AssemblyMemoryObject,
    AssemblyType,
)
from .diagnostics import NativeBackendError


STACK_ALIGNMENT = 16
REGISTER_SLOT_SIZE = 8
REGISTER_SLOT_ALIGNMENT = 8
INITIALIZATION_BYTE_SIZE = 1


def align_up(value: int, alignment: int) -> int:
    if value < 0:
        raise ValueError("value must be non-negative")
    if alignment < 1 or alignment & (alignment - 1):
        raise ValueError("alignment must be a positive power of two")
    return (value + alignment - 1) & -alignment


@dataclass(frozen=True, slots=True)
class StackRegion:
    """A byte region addressed relative to RBP.

    ``offset`` is the negative displacement of the first logical byte.
    Increasing an array index increases the effective address.
    """

    offset: int
    size: int
    alignment: int

    @property
    def first_address(self) -> int:
        return self.offset

    @property
    def last_address(self) -> int:
        return self.offset + self.size - 1

    def addresses(self) -> range:
        return range(self.first_address, self.last_address + 1)


@dataclass(frozen=True, slots=True)
class RegisterSlot:
    index: int
    type: AssemblyType
    value: StackRegion
    initialized: StackRegion


@dataclass(frozen=True, slots=True)
class MemorySlot:
    index: int
    element_type: AssemblyType
    length: int
    mutable: bool
    data: StackRegion
    initialized: StackRegion

    @property
    def element_size(self) -> int:
        return _element_size(self.element_type)


@dataclass(frozen=True, slots=True)
class CalleeSavedSlot:
    register: str
    region: StackRegion


@dataclass(frozen=True, slots=True)
class FrameLayout:
    function_name: str
    registers: tuple[RegisterSlot, ...]
    memories: tuple[MemorySlot, ...]
    frame_size: int
    logical_memory_trits: int
    scratch_size: int = 0
    hidden_sret_pointer: StackRegion | None = None
    callee_saved_slots: tuple[CalleeSavedSlot, ...] = ()

    def register(self, index: int) -> RegisterSlot:
        for slot in self.registers:
            if slot.index == index:
                return slot
        raise NativeBackendError(
            f"function '{self.function_name}' has no register r{index}"
        )

    def memory(self, index: int) -> MemorySlot:
        for slot in self.memories:
            if slot.index == index:
                return slot
        raise NativeBackendError(
            f"function '{self.function_name}' has no memory object m{index}"
        )

    def callee_saved_slot(self, register: str) -> CalleeSavedSlot:
        for slot in self.callee_saved_slots:
            if slot.register == register:
                return slot
        raise NativeBackendError(
            f"function '{self.function_name}' has no callee-saved slot for {register}"
        )

    @property
    def regions(self) -> tuple[StackRegion, ...]:
        return (
            *(slot.value for slot in self.registers),
            *(slot.initialized for slot in self.registers),
            *(slot.data for slot in self.memories),
            *(slot.initialized for slot in self.memories),
            *((self.hidden_sret_pointer,) if self.hidden_sret_pointer else ()),
            *(slot.region for slot in self.callee_saved_slots),
        )


class _Allocator:
    def __init__(self) -> None:
        self.consumed = 0

    def allocate(self, size: int, alignment: int) -> StackRegion:
        if size < 1:
            raise ValueError("stack regions must be non-empty")
        end = align_up(self.consumed + size, alignment)
        region = StackRegion(-end, size, alignment)
        self.consumed = end
        return region


def _element_size(type_name: AssemblyType) -> int:
    if type_name is AssemblyType.TRIT:
        return 1
    if type_name is AssemblyType.TRYTE:
        return 2
    if type_name is AssemblyType.STRING:
        return 8
    raise NativeBackendError(f"unsupported memory element type {type_name!r}")


def _logical_cost(memory: AssemblyMemoryObject) -> int:
    return memory.length * (
        1 if memory.element_type is AssemblyType.TRIT else 6
    )


def layout_frame(
    function: AssemblyFunction,
    physical_registers: tuple[str, ...] = (),
) -> FrameLayout:
    allocator = _Allocator()
    register_types = tuple(sorted(function.all_register_types.items()))
    value_regions = {
        index: allocator.allocate(REGISTER_SLOT_SIZE, REGISTER_SLOT_ALIGNMENT)
        for index, _ in register_types
    }
    register_init_regions = {
        index: allocator.allocate(INITIALIZATION_BYTE_SIZE, 1)
        for index, _ in register_types
    }

    memories = tuple(sorted(function.memory_objects, key=lambda item: item.index))
    data_regions = {
        memory.index: allocator.allocate(
            memory.length * _element_size(memory.element_type),
            _element_size(memory.element_type),
        )
        for memory in memories
    }
    memory_init_regions = {
        memory.index: allocator.allocate(memory.length, 1)
        for memory in memories
    }
    hidden_sret_pointer = (
        allocator.allocate(REGISTER_SLOT_SIZE, REGISTER_SLOT_ALIGNMENT)
        if function.result_width > 1
        else None
    )

    # Allocate callee-saved slots in canonical order
    canonical_pool = ("rbx", "r12", "r13", "r14", "r15")
    ordered_phys = [r for r in canonical_pool if r in physical_registers]
    callee_saved_slots = []
    for phys in ordered_phys:
        region = allocator.allocate(REGISTER_SLOT_SIZE, REGISTER_SLOT_ALIGNMENT)
        callee_saved_slots.append(CalleeSavedSlot(phys, region))

    frame_size = align_up(allocator.consumed, STACK_ALIGNMENT)
    return FrameLayout(
        function.name,
        tuple(
            RegisterSlot(
                index,
                type_name,
                value_regions[index],
                register_init_regions[index],
            )
            for index, type_name in register_types
        ),
        tuple(
            MemorySlot(
                memory.index,
                memory.element_type,
                memory.length,
                memory.mutable,
                data_regions[memory.index],
                memory_init_regions[memory.index],
            )
            for memory in memories
        ),
        frame_size,
        sum(_logical_cost(memory) for memory in memories),
        hidden_sret_pointer=hidden_sret_pointer,
        callee_saved_slots=tuple(callee_saved_slots),
    )
