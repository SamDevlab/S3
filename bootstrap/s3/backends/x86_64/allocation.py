"""Deterministic physical register allocator for S3 Assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from ...assembly import AssemblyFunction, AssemblyOpcode, AssemblyType
from .liveness import analyze_liveness, instruction_use_def
from .registers import (
    FULL_ALLOCATABLE_REGISTERS,
)
from .policy import BASELINE_NATIVE_POLICY, NativePolicy


@dataclass(frozen=True, slots=True)
class AllocationPlan:
    allocations: dict[int, str | None]  # virtual register ID -> physical register name (or None)
    call_survivors: dict[int, frozenset[int]]
    address_taken: frozenset[int] = frozenset()
    rematerializable_values: dict[int, int | float] = field(default_factory=dict)
    spill_costs: dict[int, int] = field(default_factory=dict)
    loop_split_saves: dict[int, tuple[int, ...]] = field(default_factory=dict)
    loop_split_restores: dict[str, tuple[int, ...]] = field(default_factory=dict)
    split_points: tuple[str, ...] = ()

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


def analyze_allocation(
    function: AssemblyFunction,
    policy: NativePolicy = BASELINE_NATIVE_POLICY,
) -> AllocationPlan:
    """Perform deterministic physical register allocation on an AssemblyFunction."""
    policy.validate()
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

    rematerializable_values = _find_rematerializable_constants(
        function,
        address_taken,
        policy,
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

    # 4. Greedy Coloring. The baseline retains its historical degree ordering;
    # experimental spill policies use explicit, serialized cost coefficients.
    def get_degree(r: int) -> int:
        return len(interferences[r])

    call_survivors = {
        id(inst_liveness.instruction): liveness.live_across_call(inst_liveness.instruction)
        for block in liveness.blocks.values()
        for inst_liveness in block.instructions
        if inst_liveness.instruction.opcode.value == "TCALL"
    }
    call_crossing = set().union(*call_survivors.values()) if call_survivors else set()
    use_counts = {register: 0 for register in all_vregs}
    definition_counts = {register: 0 for register in all_vregs}
    live_range_lengths = {register: 0 for register in all_vregs}
    loop_depths = {register: 0 for register in all_vregs}
    for block_name, block_liveness in liveness.blocks.items():
        block_loop_depth = _block_loop_depth(function, block_name)
        for item in block_liveness.instructions:
            for register in item.uses:
                use_counts[register] += 1
            for register in item.defs:
                definition_counts[register] += 1
            for register in item.live_before | item.live_after:
                live_range_lengths[register] += 1
                loop_depths[register] += block_loop_depth

    coefficients = dict(policy.spill_cost_parameters)
    spill_costs = {
        register: (
            coefficients["use_count"] * use_counts[register]
            + coefficients["loop_depth"] * loop_depths[register]
            + coefficients["interference_degree"] * get_degree(register)
            + coefficients["call_crossing"] * int(register in call_crossing)
            + coefficients["rematerializable"] * int(register in rematerializable_values)
            + coefficients["live_range_length"] * live_range_lengths[register]
        )
        for register in all_vregs
    }
    if policy.spill_policy in {"cost_weighted", "region_aware"}:
        sorted_nodes = sorted(
            all_vregs,
            key=lambda register: (-spill_costs[register], -get_degree(register), register),
        )
    else:
        sorted_nodes = sorted(all_vregs, key=lambda r: (-get_degree(r), r))

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
            policy.call_register_order
            if node in call_crossing
            else policy.register_order
        )
        # Select the first available physical register in the call-aware pool
        chosen_phys = None
        for phys in physical_pool:
            if phys not in neighbor_colors:
                chosen_phys = phys
                break

        colors[node] = chosen_phys

    loop_split_saves, loop_split_restores, split_points = _loop_boundary_split(
        function,
        liveness,
        colors,
        policy,
    )
    assert set(color for color in colors.values() if color) <= set(FULL_ALLOCATABLE_REGISTERS)
    return AllocationPlan(
        allocations=colors,
        call_survivors=call_survivors,
        address_taken=address_taken,
        rematerializable_values=rematerializable_values,
        spill_costs=spill_costs,
        loop_split_saves=loop_split_saves,
        loop_split_restores=loop_split_restores,
        split_points=split_points,
    )


def _find_rematerializable_constants(
    function: AssemblyFunction,
    address_taken: frozenset[int],
    policy: NativePolicy,
) -> dict[int, int | float]:
    if policy.rematerialization != "const_only" or not function.blocks:
        return {}
    allowed = {AssemblyType.TRIT, AssemblyType.TRYTE, AssemblyType.I64, AssemblyType.F64}
    entry = function.blocks[0]
    definitions: dict[int, tuple[int, object]] = {}
    definition_counts: dict[int, int] = {}
    for block_index, block in enumerate(function.blocks):
        for instruction_index, instruction in enumerate(block.instructions):
            _, defs = instruction_use_def(instruction)
            for register in defs:
                definition_counts[register] = definition_counts.get(register, 0) + 1
            if instruction.opcode is AssemblyOpcode.TCONST:
                register = instruction.registers[0]
                if instruction.immediate is not None:
                    definitions[register] = (block_index, instruction)
    result: dict[int, int | float] = {}
    for register, (block_index, instruction) in definitions.items():
        type_name = function.type_of(register)
        if (
            block_index != 0
            or type_name not in allowed
            or register in address_taken
            or definition_counts.get(register) != 1
            or instruction not in entry.instructions
        ):
            continue
        position = entry.instructions.index(instruction)
        if any(item.is_terminator for item in entry.instructions[:position]):
            continue
        result[register] = instruction.immediate
    return result


def _block_loop_depth(function: AssemblyFunction, block_name: str) -> int:
    indices = {block.label: index for index, block in enumerate(function.blocks)}
    depth = 0
    for block in function.blocks:
        if not block.instructions:
            continue
        terminator = block.instructions[-1]
        if terminator.opcode not in {AssemblyOpcode.TJMP, AssemblyOpcode.TBR3}:
            continue
        if any(
            target == block_name and indices.get(target, 0) <= indices[block.label]
            for target in terminator.labels
        ):
            depth += 1
    return min(depth, 4)


def _loop_boundary_split(
    function: AssemblyFunction,
    liveness,
    colors: dict[int, str | None],
    policy: NativePolicy,
) -> tuple[dict[int, tuple[int, ...]], dict[str, tuple[int, ...]], tuple[str, ...]]:
    if policy.live_range_split != "loop_boundary":
        return {}, {}, ()
    indices = {block.label: index for index, block in enumerate(function.blocks)}
    saves: dict[int, set[int]] = {}
    restores: dict[str, set[int]] = {}
    points: set[str] = set()
    for block in function.blocks:
        if not block.instructions:
            continue
        terminator = block.instructions[-1]
        if terminator.opcode not in {AssemblyOpcode.TJMP, AssemblyOpcode.TBR3}:
            continue
        back_targets = tuple(
            target
            for target in terminator.labels
            if target in indices and indices[target] <= indices[block.label]
        )
        if not back_targets:
            continue
        for target in back_targets:
            carried = (
                liveness.blocks[block.label].live_out
                & liveness.blocks[target].live_in
            )
            carried = {
                register
                for register in carried
                if colors.get(register) is not None
            }
            if not carried:
                continue
            saves.setdefault(id(terminator), set()).update(carried)
            restores.setdefault(target, set()).update(carried)
            points.add(f"{block.label}->{target}")
    return (
        {instruction_id: tuple(sorted(registers)) for instruction_id, registers in saves.items()},
        {block: tuple(sorted(registers)) for block, registers in restores.items()},
        tuple(sorted(points)),
    )
