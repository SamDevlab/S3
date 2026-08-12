"""Research-only logical-value trace over current S3 Assembly/x86 allocation.

This does not yet identify the true *earliest* memory-identity layer because it
starts at AssemblyFunction.  It is a useful first corpus builder and explicitly
labels what it cannot establish.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from bootstrap.s3.assembly import AssemblyFunction
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.liveness import analyze_liveness, instruction_use_def


@dataclass(frozen=True, slots=True)
class AssemblyValueTrace:
    register: int
    type_name: str
    definition_blocks: tuple[str, ...]
    use_blocks: tuple[str, ...]
    live_out_blocks: tuple[str, ...]
    crosses_block: bool
    address_taken: bool
    live_across_call: bool
    allocator_physical: str | None
    allocator_stack_resident: bool
    earliest_memory_identity_layer: str
    note: str


def trace_assembly_values(function: AssemblyFunction) -> tuple[AssemblyValueTrace, ...]:
    liveness = analyze_liveness(function)
    allocation = analyze_allocation(function)

    definitions: dict[int, set[str]] = {}
    uses: dict[int, set[str]] = {}
    live_out: dict[int, set[str]] = {}

    for block_name, block_liveness in liveness.blocks.items():
        for register in block_liveness.live_out:
            live_out.setdefault(register, set()).add(block_name)
        for item in block_liveness.instructions:
            instruction_uses, instruction_defs = instruction_use_def(item.instruction)
            for register in instruction_uses:
                uses.setdefault(register, set()).add(block_name)
            for register in instruction_defs:
                definitions.setdefault(register, set()).add(block_name)

    call_crossing: set[int] = set()
    for survivors in allocation.call_survivors.values():
        call_crossing.update(survivors)

    all_registers = set(allocation.allocations)
    all_registers.update(definitions)
    all_registers.update(uses)
    all_registers.update(live_out)

    traces: list[AssemblyValueTrace] = []
    for register in sorted(all_registers):
        def_blocks = tuple(sorted(definitions.get(register, ())))
        use_blocks = tuple(sorted(uses.get(register, ())))
        live_out_blocks = tuple(sorted(live_out.get(register, ())))
        crosses_block = bool(live_out_blocks) or any(
            use_block not in set(def_blocks) for use_block in use_blocks
        )
        physical = allocation.physical_register(register)
        address_taken = register in allocation.address_taken

        if address_taken:
            layer = "ASSEMBLY_BACKEND_REQUIRED_ADDRESS_IDENTITY"
            note = "Address-taken referent is intentionally canonical stack storage."
        elif physical is None:
            layer = "AT_OR_BEFORE_REGISTER_ALLOCATION"
            note = (
                "Assembly-level trace sees stack residency but cannot yet distinguish "
                "pre-RA canonicalization from a true RA spill; inspect earlier IR/frame decisions."
            )
        else:
            layer = "NOT_MEMORY_ONLY_AT_RA_OUTPUT"
            note = "Current allocator assigned a physical register."

        type_value = function.all_register_types.get(register)
        type_name = getattr(type_value, "value", str(type_value))
        traces.append(
            AssemblyValueTrace(
                register=register,
                type_name=type_name,
                definition_blocks=def_blocks,
                use_blocks=use_blocks,
                live_out_blocks=live_out_blocks,
                crosses_block=crosses_block,
                address_taken=address_taken,
                live_across_call=register in call_crossing,
                allocator_physical=physical,
                allocator_stack_resident=physical is None,
                earliest_memory_identity_layer=layer,
                note=note,
            )
        )

    return tuple(traces)


def trace_as_jsonable(function: AssemblyFunction) -> list[dict[str, object]]:
    return [asdict(trace) for trace in trace_assembly_values(function)]
