"""Conservative cross-block scalar residence planning."""

from __future__ import annotations

from ...assembly import AssemblyFunction, AssemblyOpcode, AssemblyType
from .allocation import AllocationPlan, analyze_allocation
from .liveness import analyze_liveness, instruction_use_def


_RESIDENT_TYPES = frozenset({AssemblyType.TRIT, AssemblyType.TRYTE, AssemblyType.I64})


def analyze_cross_block_residence(function: AssemblyFunction) -> AllocationPlan:
    """Select only proven scalar values whose lifetime crosses a CFG edge.

    The existing allocator supplies interference, call, and ABI-safe colors.
    This pass narrows that plan; it does not change coloring or allocator policy.
    Values without a single definition, with an address-sensitive referent, or
    outside the supported scalar representation stay frame-backed.
    """
    full_plan = analyze_allocation(function)
    liveness = analyze_liveness(function)
    # The default emitter has no independent call-preservation lowering. Keep
    # call-containing functions on the canonical frame path until that barrier
    # can be proven without adding whole-function ABI traffic.
    if any(instruction.opcode is AssemblyOpcode.TCALL for instruction in function.instructions):
        return AllocationPlan(
            allocations={register: None for register in full_plan.allocations},
            call_survivors={},
            address_taken=full_plan.address_taken,
        )
    defs_by_register: dict[int, set[str]] = {}
    uses_by_register: dict[int, set[str]] = {}
    address_taken = set(full_plan.address_taken)
    for block_name, block_liveness in liveness.blocks.items():
        for item in block_liveness.instructions:
            uses, defs = instruction_use_def(item.instruction)
            for register in uses:
                uses_by_register.setdefault(register, set()).add(block_name)
            for register in defs:
                defs_by_register.setdefault(register, set()).add(block_name)

    selected: dict[int, str | None] = {
        register: None for register in full_plan.allocations
    }
    for register, physical in full_plan.allocations.items():
        type_name = function.all_register_types.get(register)
        if type_name not in _RESIDENT_TYPES or physical is None:
            continue
        if register in address_taken:
            continue
        definition_blocks = defs_by_register.get(register, set())
        use_blocks = uses_by_register.get(register, set())
        if len(definition_blocks) != 1:
            continue
        if not any(block != next(iter(definition_blocks)) for block in use_blocks):
            continue
        selected[register] = physical

    selected_registers = frozenset(
        register for register, physical in selected.items() if physical is not None
    )
    call_survivors = {
        site: frozenset(
            register for register in survivors if register in selected_registers
        )
        for site, survivors in full_plan.call_survivors.items()
    }
    return AllocationPlan(
        allocations=selected,
        call_survivors=call_survivors,
        address_taken=full_plan.address_taken,
    )
