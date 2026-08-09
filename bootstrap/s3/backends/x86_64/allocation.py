"""Deterministic physical register allocator for S3 Assembly."""

from __future__ import annotations

from dataclasses import dataclass
from ...assembly import AssemblyFunction
from .liveness import analyze_liveness
from .registers import (
    CALLER_SAVED_ALLOCATABLE_REGISTERS,
    CALLEE_SAVED_ALLOCATABLE_REGISTERS,
    FULL_ALLOCATABLE_REGISTERS,
)


@dataclass(frozen=True, slots=True)
class AllocationPlan:
    allocations: dict[int, str | None]  # virtual register ID -> physical register name (or None)
    call_survivors: dict[int, frozenset[int]]
    address_taken: frozenset[int] = frozenset()

    def physical_register(self, register: int) -> str | None:
        return self.allocations.get(register)

    def is_stack_resident(self, register: int) -> bool:
        return self.allocations.get(register) is None

    @property
    def used_physical_registers(self) -> tuple[str, ...]:
        used = {color for color in self.allocations.values() if color is not None}
        canonical_pool = FULL_ALLOCATABLE_REGISTERS
        return tuple(phys for phys in canonical_pool if phys in used)

    @property
    def stack_resident_registers(self) -> tuple[int, ...]:
        return tuple(sorted(r for r, color in self.allocations.items() if color is None))

    def call_survivors_for(self, instruction: object) -> frozenset[int]:
        return self.call_survivors.get(id(instruction), frozenset())


def analyze_allocation(function: AssemblyFunction) -> AllocationPlan:
    """Perform deterministic physical register allocation on an AssemblyFunction."""
    # 1. Run liveness analysis
    liveness = analyze_liveness(function)

    # 2. Collect all virtual registers used/defined/live in the function
    all_vregs = set()
    for param in function.parameters:
        all_vregs.add(param.register)
    for block in function.blocks:
        for inst in block.instructions:
            all_vregs.update(inst.registers)

    # Address-taken referents are canonical stack values for the whole
    # function.  The reference scalar itself remains allocatable.
    address_taken = frozenset(
        instruction.registers[1]
        for instruction in function.instructions
        if (
            instruction.opcode.value == "TADDR"
            and instruction.memory is None
            and len(instruction.registers) == 2
        )
    )

    # 3. Build interference graph
    # Node: virtual register ID (int)
    # Edge: interference
    interferences: dict[int, set[int]] = {r: set() for r in all_vregs}

    def add_edge(u: int, v: int) -> None:
        if u != v:
            interferences[u].add(v)
            interferences[v].add(u)

    for block_liveness in liveness.blocks.values():
        for inst_liveness in block_liveness.instructions:
            # All registers live before the instruction interfere
            live_before = list(inst_liveness.live_before)
            for i in range(len(live_before)):
                for j in range(i + 1, len(live_before)):
                    add_edge(live_before[i], live_before[j])

            # All registers live after the instruction interfere
            live_after = list(inst_liveness.live_after)
            for i in range(len(live_after)):
                for j in range(i + 1, len(live_after)):
                    add_edge(live_after[i], live_after[j])

            # Each DEF interferes with each register in live_after (except itself)
            # This protects against dead definitions (values that are written but die immediately)
            for d in inst_liveness.defs:
                for la in inst_liveness.live_after:
                    add_edge(d, la)

    # 4. Greedy Coloring
    # Sort nodes by degree descending, then by node ID ascending for determinism
    def get_degree(r: int) -> int:
        return len(interferences[r])

    sorted_nodes = sorted(all_vregs, key=lambda r: (-get_degree(r), r))

    call_survivors = {
        id(inst_liveness.instruction): liveness.live_across_call(inst_liveness.instruction)
        for block in liveness.blocks.values()
        for inst_liveness in block.instructions
        if inst_liveness.instruction.opcode.value == "TCALL"
    }
    call_crossing = set().union(*call_survivors.values()) if call_survivors else set()
    colors: dict[int, str | None] = {}

    for node in sorted_nodes:
        if node in address_taken:
            colors[node] = None
            continue
        # Get physical registers used by neighbors
        neighbor_colors = {
            colors[nb] for nb in interferences[node]
            if nb in colors and colors[nb] is not None
        }

        physical_pool = (
            (*CALLEE_SAVED_ALLOCATABLE_REGISTERS, *CALLER_SAVED_ALLOCATABLE_REGISTERS)
            if node in call_crossing
            else (*CALLER_SAVED_ALLOCATABLE_REGISTERS, *CALLEE_SAVED_ALLOCATABLE_REGISTERS)
        )
        # Select the first available physical register in the call-aware pool
        chosen_phys = None
        for phys in physical_pool:
            if phys not in neighbor_colors:
                chosen_phys = phys
                break

        colors[node] = chosen_phys

    assert set(color for color in colors.values() if color) <= set(FULL_ALLOCATABLE_REGISTERS)
    return AllocationPlan(
        allocations=colors,
        call_survivors=call_survivors,
        address_taken=address_taken,
    )
