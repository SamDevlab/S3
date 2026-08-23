"""Deterministic static features for native-policy research experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ...assembly import AssemblyFunction, AssemblyOpcode
from .allocation import analyze_allocation
from .liveness import analyze_liveness
from .policy import BASELINE_NATIVE_POLICY, NativePolicy, policy_with


@dataclass(frozen=True, slots=True)
class FunctionFeatureVector:
    instruction_count: int
    block_count: int
    edge_count: int
    loop_count: int
    max_loop_depth: int
    branch_count: int
    virtual_register_count: int
    max_live: int
    mean_live: float
    interference_edges: int
    register_pressure_peak: int
    call_count: int
    live_across_call_count: int
    call_argument_pressure: int
    memory_loads: int
    memory_stores: int
    indexed_memory_ops: int
    address_recomputations: int
    mutable_scalar_candidates: int
    address_taken_values: int
    reference_ops: int
    rematerializable_value_count: int
    estimated_spill_pressure: int
    existing_spills: int
    existing_reloads: int

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PerFunctionPolicyPortfolio:
    """Research-only static decision table; never used by the default backend."""

    baseline_policy_id: str

    def select(
        self,
        function: AssemblyFunction,
        policies: dict[str, NativePolicy],
    ) -> tuple[str, str]:
        features = extract_function_features(function)
        if self.baseline_policy_id not in policies:
            raise ValueError("portfolio requires an explicit baseline policy")
        if features.reference_ops or features.address_taken_values:
            return self.baseline_policy_id, "reference_or_address_escape_fallback"
        if features.memory_loads or features.memory_stores:
            for policy_id, policy in sorted(policies.items()):
                if policy.scalar_promotion == "conservative_mem2reg":
                    return policy_id, "alias_safe_scalar_memory"
                if policy.indexed_memory_policy == "compact_ea":
                    return policy_id, "indexed_memory_pressure"
        if features.loop_count:
            for policy_id, policy in sorted(policies.items()):
                if policy.live_range_split == "loop_boundary":
                    return policy_id, "loop_boundary_liveness"
                if policy.spill_policy == "region_aware":
                    return policy_id, "loop_pressure_spill_cost"
        if features.rematerializable_value_count:
            for policy_id, policy in sorted(policies.items()):
                if policy.rematerialization == "const_only":
                    return policy_id, "pure_constant_recreation"
        return self.baseline_policy_id, "conservative_baseline_fallback"


def extract_function_features(
    function: AssemblyFunction,
    policy: NativePolicy = BASELINE_NATIVE_POLICY,
) -> FunctionFeatureVector:
    """Extract only stable source/Assembly facts; no timing or filesystem state."""

    policy.validate()
    liveness = analyze_liveness(function)
    instructions = function.instructions
    block_indices = {block.label: index for index, block in enumerate(function.blocks)}
    edges: set[tuple[str, str]] = set()
    back_edges: set[tuple[str, str]] = set()
    live_sizes: list[int] = []
    interference: set[tuple[int, int]] = set()
    for block in function.blocks:
        if not block.instructions:
            continue
        terminator = block.instructions[-1]
        if terminator.opcode in {AssemblyOpcode.TJMP, AssemblyOpcode.TBR3}:
            for target in terminator.labels:
                if target not in block_indices:
                    continue
                edge = (block.label, target)
                edges.add(edge)
                if block_indices[target] <= block_indices[block.label]:
                    back_edges.add(edge)
        for item in liveness.blocks[block.label].instructions:
            live = item.live_before | item.live_after
            live_sizes.append(len(live))
            ordered = sorted(live)
            interference.update(
                (left, right)
                for position, left in enumerate(ordered)
                for right in ordered[position + 1 :]
            )

    calls = [
        item.instruction
        for block in liveness.blocks.values()
        for item in block.instructions
        if item.instruction.opcode is AssemblyOpcode.TCALL
    ]
    call_argument_pressure = max(
        (len(call.argument_registers) for call in calls),
        default=0,
    )
    memory_loads = sum(item.opcode is AssemblyOpcode.TLOAD for item in instructions)
    memory_stores = sum(item.opcode is AssemblyOpcode.TSTORE for item in instructions)
    indexed_memory_ops = memory_loads + memory_stores
    address_taken = {
        instruction.registers[1]
        for instruction in instructions
        if instruction.opcode is AssemblyOpcode.TADDR
        and instruction.memory is None
        and len(instruction.registers) > 1
    }
    mutable_scalar_candidates = sum(
        memory.mutable and memory.length == 1
        for memory in function.memory_objects
        if not any(
            instruction.opcode is AssemblyOpcode.TADDR
            and instruction.memory == memory.index
            for instruction in instructions
        )
    )
    reference_ops = sum(
        instruction.opcode
        in {
            AssemblyOpcode.TADDR,
            AssemblyOpcode.TREFLOAD,
            AssemblyOpcode.TREFSTORE,
            AssemblyOpcode.TSLEN,
            AssemblyOpcode.TSLOAD,
            AssemblyOpcode.TSSTORE,
        }
        for instruction in instructions
    )
    remat_plan = analyze_allocation(
        function,
        policy_with(policy, rematerialization="const_only"),
    )
    plan = analyze_allocation(function, policy)
    max_live = max(live_sizes, default=0)
    return FunctionFeatureVector(
        instruction_count=len(instructions),
        block_count=len(function.blocks),
        edge_count=len(edges),
        loop_count=len(back_edges),
        max_loop_depth=min(len(back_edges), 4),
        branch_count=sum(
            instruction.opcode in {AssemblyOpcode.TJMP, AssemblyOpcode.TBR3}
            for instruction in instructions
        ),
        virtual_register_count=len(function.all_register_types),
        max_live=max_live,
        mean_live=(sum(live_sizes) / len(live_sizes)) if live_sizes else 0.0,
        interference_edges=len(interference),
        register_pressure_peak=max_live,
        call_count=len(calls),
        live_across_call_count=sum(
            len(liveness.live_across_call(call)) for call in calls
        ),
        call_argument_pressure=call_argument_pressure,
        memory_loads=memory_loads,
        memory_stores=memory_stores,
        indexed_memory_ops=indexed_memory_ops,
        address_recomputations=indexed_memory_ops + sum(
            instruction.opcode is AssemblyOpcode.TADDR for instruction in instructions
        ),
        mutable_scalar_candidates=mutable_scalar_candidates,
        address_taken_values=len(address_taken),
        reference_ops=reference_ops,
        rematerializable_value_count=len(remat_plan.rematerializable_values),
        estimated_spill_pressure=max(0, max_live - len(plan.used_physical_registers)),
        existing_spills=len(plan.stack_resident_registers),
        existing_reloads=len(plan.stack_resident_registers),
    )
