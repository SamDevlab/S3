"""Non-production store-to-load forwarding experiment for S3 1.10."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from bootstrap.s3.initialization import analyze_initialization
from bootstrap.s3.ir import IRBasicBlock, IRInstruction, IRModule, IRRegister, IROpcode
from bootstrap.s3.memory_value_availability import (
    LoadAvailability,
    StorageIdentity,
    analyze_memory_value_availability,
)
from bootstrap.s3.ssa import SSABlock, SSABuilder, SSAValue
from bootstrap.s3.verifier import verify_ir


@dataclass(slots=True)
class _CandidateGroup:
    value: SSAValue
    loads: list[LoadAvailability] = field(default_factory=list)


def _direct_same_block_source(
    load: LoadAvailability,
    value: SSAValue,
    ssa_blocks: dict[str, SSABlock],
    ir_blocks: dict[str, IRBasicBlock],
) -> int | None:
    sites = load.state.store_sites
    if not sites or any(
        block_name != load.block or index >= load.instruction_index
        for block_name, index in sites
    ):
        return None
    ssa_block = ssa_blocks[load.block]
    ir_block = ir_blocks[load.block]
    source_registers: set[int] = set()
    for block_name, index in sites:
        ssa_store = ssa_blocks[block_name].instructions[index]
        ir_store = ir_blocks[block_name].instructions[index]
        if (
            ssa_store.opcode is not IROpcode.STORE
            or len(ssa_store.operands) < 2
            or ssa_store.operands[1].name != value.name
            or ir_store.opcode is not IROpcode.STORE
            or len(ir_store.operands) < 2
        ):
            raise RuntimeError("store provenance failed consistency check")
        source_registers.add(ir_store.operands[1])
    if len(source_registers) != 1:
        return None
    source_register = next(iter(source_registers))
    first_store = min(index for _, index in sites)
    if any(
        source_register in instruction.results
        for instruction in ir_block.instructions[first_store + 1 : load.instruction_index]
    ):
        return None
    return source_register


def forward_available_stores(module: IRModule) -> tuple[IRModule, int]:
    """Replace proven LOADs with MOVEs, preserving values in fresh registers.

    A copy is inserted at each reaching store site so later redefinitions of
    the original virtual register cannot invalidate the forwarded value. This
    helper is an experiment only and is not called by the compiler pipeline.
    """

    transformed_functions = []
    total_forwarded = 0
    for function in module.functions:
        if function.external:
            transformed_functions.append(function)
            continue

        ssa_function = SSABuilder.build_function(function)
        report = analyze_memory_value_availability(ssa_function)
        groups: dict[tuple[StorageIdentity, str], _CandidateGroup] = {}
        for load in report.loads:
            if not load.forwardable or load.storage is None or load.state.value is None:
                continue
            key = (load.storage, load.state.value.name)
            group = groups.setdefault(key, _CandidateGroup(load.state.value))
            group.loads.append(load)

        if not groups:
            transformed_functions.append(function)
            continue

        next_register = (
            max((register.index for register in function.registers), default=-1) + 1
        )
        copies: dict[tuple[str, int], list[tuple[int, int]]] = {}
        forwarded_loads: dict[tuple[str, int], int] = {}
        new_registers: list[IRRegister] = []
        ssa_blocks = {block.name: block for block in ssa_function.blocks}
        ir_blocks = {block.name: block for block in function.blocks}

        for group in groups.values():
            value = group.value
            temporary_loads: list[LoadAvailability] = []
            for load in group.loads:
                site = (load.block, load.instruction_index)
                if site in forwarded_loads:
                    raise RuntimeError("one LOAD was assigned multiple forwarding values")
                direct_source = _direct_same_block_source(
                    load, value, ssa_blocks, ir_blocks
                )
                if direct_source is None:
                    temporary_loads.append(load)
                else:
                    forwarded_loads[site] = direct_source

            if not temporary_loads:
                continue
            temporary = next_register
            next_register += 1
            new_registers.append(IRRegister(temporary, value.type))
            needed_stores = sorted(
                {
                    site
                    for load in temporary_loads
                    for site in load.state.store_sites
                }
            )
            if not needed_stores:
                raise RuntimeError("available load has no recorded reaching store")
            for block_name, instruction_index in needed_stores:
                ssa_store = ssa_blocks[block_name].instructions[instruction_index]
                ir_store = ir_blocks[block_name].instructions[instruction_index]
                if (
                    ssa_store.opcode is not IROpcode.STORE
                    or len(ssa_store.operands) < 2
                    or ssa_store.operands[1].name != value.name
                    or ir_store.opcode is not IROpcode.STORE
                    or len(ir_store.operands) < 2
                ):
                    raise RuntimeError("store provenance failed consistency check")
                copies.setdefault((block_name, instruction_index), []).append(
                    (temporary, ir_store.operands[1])
                )
            for load in temporary_loads:
                forwarded_loads[(load.block, load.instruction_index)] = temporary

        updated_blocks = []
        for block in function.blocks:
            instructions = []
            for instruction_index, instruction in enumerate(block.instructions):
                site = (block.name, instruction_index)
                for temporary, source_register in copies.get(site, ()):
                    instructions.append(
                        IRInstruction(
                            opcode=IROpcode.MOVE,
                            result=temporary,
                            operands=(source_register,),
                            location=instruction.location,
                        )
                    )
                forwarding = forwarded_loads.get(site)
                if forwarding is None:
                    instructions.append(instruction)
                    continue
                source_register = forwarding
                if instruction.opcode is not IROpcode.LOAD or instruction.result is None:
                    raise RuntimeError("forwarding provenance no longer points to LOAD")
                instructions.append(
                    replace(
                        instruction,
                        opcode=IROpcode.MOVE,
                        operands=(source_register,),
                        immediate=None,
                        static_string=None,
                        callee=None,
                        targets=(),
                        memory=None,
                        initialization=False,
                        reference_target=None,
                        reference_mutable=False,
                        reference_is_slice=False,
                        slice_length_result=None,
                        reference_aggregate=None,
                        aggregate_field_paths=(),
                        aggregate_field_path=(),
                        bounds_proven=False,
                    )
                )
                total_forwarded += 1
            updated_blocks.append(replace(block, instructions=tuple(instructions)))

        transformed_functions.append(
            replace(
                function,
                registers=function.registers + tuple(new_registers),
                blocks=tuple(updated_blocks),
            )
        )

    candidate = replace(module, functions=tuple(transformed_functions))
    verify_ir(candidate)
    analyze_initialization(candidate)
    return candidate, total_forwarded
