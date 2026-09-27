"""Experimental proof-gated cross-block exact-cell LOAD reuse for S3 1.10."""

from __future__ import annotations

from dataclasses import replace

from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.dominance import DominatorTree
from bootstrap.s3.initialization import analyze_initialization
from bootstrap.s3.ir import IRInstruction, IRModule, IRRegister, IROpcode
from bootstrap.s3.memory_value_availability import (
    RepeatedLoadCandidate,
    StorageIdentity,
    analyze_repeated_load_availability,
)
from bootstrap.s3.ssa import SSABlock, SSABuilder
from bootstrap.s3.verifier import verify_ir


def _move_from(instruction: IRInstruction, source: int) -> IRInstruction:
    if instruction.opcode is not IROpcode.LOAD or instruction.result is None:
        raise RuntimeError("forwarding provenance no longer points to LOAD")
    return replace(
        instruction,
        opcode=IROpcode.MOVE,
        operands=(source,),
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


def _source_sites(
    candidate: RepeatedLoadCandidate,
    ssa_blocks: dict[str, SSABlock],
    ir_blocks: dict[str, object],
) -> tuple[tuple[str, int], ...]:
    sites = candidate.state.load_sites
    if not sites:
        raise RuntimeError("available repeated load has no source LOAD site")
    for block_name, index in sites:
        if block_name not in ssa_blocks or block_name not in ir_blocks:
            raise RuntimeError("source LOAD block is absent from IR/SSA")
        ssa_instruction = ssa_blocks[block_name].instructions[index]
        ir_instruction = ir_blocks[block_name].instructions[index]
        if (
            ssa_instruction.opcode is not IROpcode.LOAD
            or ssa_instruction.result is None
            or candidate.state.value is None
            or ssa_instruction.result.name != candidate.state.value.name
            or ssa_instruction.result.type is not candidate.state.value.type
            or ir_instruction.opcode is not IROpcode.LOAD
            or ir_instruction.result is None
        ):
            raise RuntimeError("source LOAD provenance failed consistency check")
        if candidate.storage is None or ir_instruction.memory != candidate.storage.memory_object:
            raise RuntimeError("source LOAD storage differs from analyzed storage")
    return sites


def forward_available_loads(
    module: IRModule,
    *,
    selected_sites: set[tuple[str, str, int]] | None = None,
) -> tuple[IRModule, int]:
    """Reuse proven cross-block load values through fresh local temporaries.

    The helper is research-only. It inserts a copy immediately after each
    proven source LOAD, then replaces eligible later LOADs with MOVEs. Any
    missing or inconsistent proof fails closed; the production pipeline is
    never modified or invoked by this module.
    """

    transformed_functions = []
    total_forwarded = 0
    selected_sites_seen: set[tuple[str, str, int]] = set()
    for function in module.functions:
        if function.external:
            transformed_functions.append(function)
            continue

        ssa_function = SSABuilder.build_function(function)
        report = analyze_repeated_load_availability(ssa_function)
        groups: dict[tuple[StorageIdentity, str], list[RepeatedLoadCandidate]] = {}
        for candidate in report.candidates:
            if (
                candidate.cross_block_available
                and candidate.storage is not None
                and candidate.state.value is not None
                and (
                    selected_sites is None
                    or (function.name, candidate.block, candidate.instruction_index)
                    in selected_sites
                )
            ):
                selected_sites_seen.add(
                    (function.name, candidate.block, candidate.instruction_index)
                )
                groups.setdefault(
                    (candidate.storage, candidate.state.value.name), []
                ).append(candidate)

        if not groups:
            transformed_functions.append(function)
            continue

        ssa_blocks = {block.name: block for block in ssa_function.blocks}
        ir_blocks = {block.name: block for block in function.blocks}
        next_register = max(
            (register.index for register in function.registers), default=-1
        ) + 1
        inserted_copies: dict[tuple[str, int], list[tuple[int, int]]] = {}
        forwarded_loads: dict[tuple[str, int], int] = {}
        new_registers: list[IRRegister] = []

        for (storage, value_name), candidates in groups.items():
            source_value = candidates[0].state.value
            if source_value is None or source_value.name != value_name:
                raise RuntimeError("load reuse group lost its source SSA value")
            if any(
                candidate.state.value is None
                or candidate.state.value.name != value_name
                or candidate.storage != storage
                or not candidate.forwardable
                for candidate in candidates
            ):
                raise RuntimeError("load reuse group contains inconsistent proof facts")

            source_sites = tuple(
                sorted(
                    {
                        site
                        for candidate in candidates
                        for site in _source_sites(candidate, ssa_blocks, ir_blocks)
                    }
                )
            )
            if len(source_sites) != 1:
                raise RuntimeError("one SSA LOAD value must have exactly one definition site")
            source_block, source_index = source_sites[0]
            source_register = ir_blocks[source_block].instructions[source_index].result
            if source_register is None:
                raise RuntimeError("source LOAD has no IR result register")
            temporary = next_register
            next_register += 1
            new_registers.append(IRRegister(temporary, source_value.type))
            inserted_copies.setdefault((source_block, source_index), []).append(
                (temporary, source_register)
            )

            for candidate in candidates:
                site = (candidate.block, candidate.instruction_index)
                if site in forwarded_loads:
                    raise RuntimeError("one LOAD was assigned multiple reuse values")
                forwarded_loads[site] = temporary

        updated_blocks = []
        for block in function.blocks:
            instructions = []
            for instruction_index, instruction in enumerate(block.instructions):
                forwarding = forwarded_loads.get((block.name, instruction_index))
                instructions.append(
                    _move_from(instruction, forwarding)
                    if forwarding is not None
                    else instruction
                )
                for temporary, source_register in inserted_copies.get(
                    (block.name, instruction_index), ()
                ):
                    instructions.append(
                        IRInstruction(
                            opcode=IROpcode.MOVE,
                            result=temporary,
                            operands=(source_register,),
                            location=instruction.location,
                        )
                    )
                if forwarding is not None:
                    total_forwarded += 1
            updated_blocks.append(replace(block, instructions=tuple(instructions)))

        transformed_functions.append(
            replace(
                function,
                registers=function.registers + tuple(new_registers),
                blocks=tuple(updated_blocks),
            )
        )

    candidate_module = replace(module, functions=tuple(transformed_functions))
    if selected_sites is not None and selected_sites_seen != selected_sites:
        missing = sorted(selected_sites - selected_sites_seen)
        raise RuntimeError(f"selected load sites are not proven cross-block candidates: {missing}")
    verify_ir(candidate_module)
    analyze_initialization(candidate_module)
    return candidate_module, total_forwarded


def forward_available_loads_by_ssa_substitution(
    module: IRModule,
    *,
    selected_sites: set[tuple[str, str, int]] | None = None,
) -> tuple[IRModule, int]:
    """Remove proven repeated LOADs using SSA def-use facts on original IR.

    This is an isolated research prototype, not part of the production
    optimizer. It requires one exact source LOAD that dominates every target,
    unique source/target IR register definitions, and no target use through a
    phi. The rewrite removes only the selected LOAD and substitutes its SSA
    uses in the corresponding original IR operands. It deliberately avoids
    SSA-to-IR lowering, which can be invalid for memory-observable functions.
    """

    transformed_functions = []
    total_forwarded = 0
    selected_sites_seen: set[tuple[str, str, int]] = set()
    for function in module.functions:
        if function.external:
            transformed_functions.append(function)
            continue

        ssa_function = SSABuilder.build_function(function)
        report = analyze_repeated_load_availability(ssa_function)
        selected = [
            candidate
            for candidate in report.candidates
            if candidate.cross_block_available
            and candidate.result is not None
            and candidate.state.value is not None
            and candidate.storage is not None
            and (
                selected_sites is None
                or (function.name, candidate.block, candidate.instruction_index)
                in selected_sites
            )
        ]
        if not selected:
            transformed_functions.append(function)
            continue

        cfg = ControlFlowGraph.build(function)
        dominators = DominatorTree.build(cfg)
        ssa_blocks = {block.name: block for block in ssa_function.blocks}
        ir_blocks = {block.name: block for block in function.blocks}
        ir_registers = {register.index: register for register in function.registers}
        substitutions: dict[int, int] = {}
        removed_load_sites: set[tuple[str, int]] = set()
        accepted_sites: set[tuple[str, str, int]] = set()

        definitions: dict[int, list[tuple[str, int]]] = {}
        for block in function.blocks:
            for index, instruction in enumerate(block.instructions):
                for register in instruction.results:
                    definitions.setdefault(register, []).append((block.name, index))
        for parameter in function.parameters:
            definitions.setdefault(parameter.register, []).append(("<parameter>", -1))

        for candidate in selected:
            if not candidate.forwardable or candidate.result is None:
                raise RuntimeError("selected repeated LOAD lacks a complete proof")
            source = candidate.state.value
            if (
                source is None
                or source.type is not candidate.result.type
                or source.original_register is None
                or candidate.result.original_register is None
            ):
                raise RuntimeError("source and target LOAD register/type facts are incomplete")
            source_sites = candidate.state.load_sites
            if len(source_sites) != 1:
                raise RuntimeError("available SSA value must have one LOAD definition")
            source_block, source_index = source_sites[0]
            source_block_ir = ssa_blocks.get(source_block)
            target_block_ir = ssa_blocks.get(candidate.block)
            if source_block_ir is None or target_block_ir is None:
                raise RuntimeError("source or target SSA block is absent")
            if source_index >= len(source_block_ir.instructions):
                raise RuntimeError("source LOAD instruction index is out of range")
            source_inst = source_block_ir.instructions[source_index]
            target_inst = target_block_ir.instructions[candidate.instruction_index]
            source_original_block = ir_blocks.get(source_block)
            target_original_block = ir_blocks.get(candidate.block)
            if (
                source_inst.opcode is not IROpcode.LOAD
                or source_inst.result is None
                or source_inst.result.name != source.name
                or source_inst.result.type is not source.type
                or source_inst.memory != candidate.storage.memory_object
                or target_inst.opcode is not IROpcode.LOAD
                or target_inst.result is None
                or target_inst.result.name != candidate.result.name
                or target_inst.memory != candidate.storage.memory_object
                or source_original_block is None
                or target_original_block is None
                or source_index >= len(source_original_block.instructions)
                or candidate.instruction_index >= len(target_original_block.instructions)
            ):
                raise RuntimeError("SSA/original IR LOAD provenance does not match analysis")
            source_ir_inst = source_original_block.instructions[source_index]
            target_ir_inst = target_original_block.instructions[candidate.instruction_index]
            source_register = source.original_register
            target_register = candidate.result.original_register
            source_register_info = ir_registers.get(source_register)
            target_register_info = ir_registers.get(target_register)
            if (
                source_ir_inst.opcode is not IROpcode.LOAD
                or source_ir_inst.result != source_register
                or source_ir_inst.memory != candidate.storage.memory_object
                or target_ir_inst.opcode is not IROpcode.LOAD
                or target_ir_inst.result != target_register
                or target_ir_inst.memory != candidate.storage.memory_object
                or source_register_info is None
                or target_register_info is None
                or source_register == target_register
                or definitions.get(source_register) != [(source_block, source_index)]
                or definitions.get(target_register)
                != [(candidate.block, candidate.instruction_index)]
            ):
                continue
            if (
                source.reference_target != candidate.result.reference_target
                or source.reference_mutable != candidate.result.reference_mutable
                or source.reference_is_slice != candidate.result.reference_is_slice
                or source.slice_length_register != candidate.result.slice_length_register
                or (
                    source_register_info.type,
                    source_register_info.reference_target,
                    source_register_info.reference_mutable,
                    source_register_info.reference_is_slice,
                    source_register_info.slice_length_register,
                    source_register_info.reference_aggregate,
                )
                != (
                    target_register_info.type,
                    target_register_info.reference_target,
                    target_register_info.reference_mutable,
                    target_register_info.reference_is_slice,
                    target_register_info.slice_length_register,
                    target_register_info.reference_aggregate,
                )
                or (
                    source_ir_inst.reference_target,
                    source_ir_inst.reference_mutable,
                    source_ir_inst.reference_is_slice,
                    source_ir_inst.slice_length_result,
                    source_ir_inst.reference_aggregate,
                    source_ir_inst.aggregate_field_paths,
                    source_ir_inst.aggregate_field_path,
                )
                != (
                    target_ir_inst.reference_target,
                    target_ir_inst.reference_mutable,
                    target_ir_inst.reference_is_slice,
                    target_ir_inst.slice_length_result,
                    target_ir_inst.reference_aggregate,
                    target_ir_inst.aggregate_field_paths,
                    target_ir_inst.aggregate_field_path,
                )
                or (
                    source_inst.reference_target,
                    source_inst.reference_mutable,
                    source_inst.reference_is_slice,
                    source_inst.slice_length_result,
                )
                != (
                    target_inst.reference_target,
                    target_inst.reference_mutable,
                    target_inst.reference_is_slice,
                    target_inst.slice_length_result,
                )
            ):
                continue
            if source_block == candidate.block:
                if source_index >= candidate.instruction_index:
                    continue
            elif not dominators.dominates(source_block, candidate.block):
                continue

            target_has_phi_use = any(
                value.name == candidate.result.name
                for block in ssa_function.blocks
                for phi in block.phis
                for value in phi.operands.values()
            )
            if target_has_phi_use:
                continue

            target_uses = [
                (block.name, index, operand_index)
                for block in ssa_function.blocks
                for index, instruction in enumerate(block.instructions)
                for operand_index, value in enumerate(instruction.operands)
                if value.name == candidate.result.name
            ]
            if any(
                block_name not in ir_blocks
                or instruction_index >= len(ir_blocks[block_name].instructions)
                or operand_index
                >= len(ir_blocks[block_name].instructions[instruction_index].operands)
                or ir_blocks[block_name].instructions[instruction_index].operands[
                    operand_index
                ]
                != target_register
                for block_name, instruction_index, operand_index in target_uses
            ):
                continue

            existing = substitutions.get(target_register)
            if existing is not None and existing != source_register:
                raise RuntimeError("one target LOAD has conflicting source registers")
            substitutions[target_register] = source_register
            removed_load_sites.add((candidate.block, candidate.instruction_index))
            accepted_sites.add(
                (function.name, candidate.block, candidate.instruction_index)
            )

        def canonical_register(register: int) -> int:
            current = register
            visited: set[int] = set()
            while current in substitutions:
                if current in visited:
                    raise RuntimeError("cyclic IR register substitutions")
                visited.add(current)
                current = substitutions[current]
            return current

        rewritten_blocks = []
        for block in function.blocks:
            instructions = []
            for index, instruction in enumerate(block.instructions):
                if (block.name, index) in removed_load_sites:
                    continue
                operands = tuple(canonical_register(value) for value in instruction.operands)
                instructions.append(replace(instruction, operands=operands))
            rewritten_blocks.append(replace(block, instructions=tuple(instructions)))
        transformed_functions.append(
            replace(
                function,
                registers=tuple(
                    register
                    for register in function.registers
                    if register.index not in substitutions
                ),
                blocks=tuple(rewritten_blocks),
            )
        )
        total_forwarded += len(removed_load_sites)
        selected_sites_seen.update(accepted_sites)

    if selected_sites is not None and selected_sites_seen != selected_sites:
        missing = sorted(selected_sites - selected_sites_seen)
        raise RuntimeError(f"selected load sites are not proven candidates: {missing}")

    candidate_module = replace(module, functions=tuple(transformed_functions))
    verify_ir(candidate_module)
    analyze_initialization(candidate_module)
    return candidate_module, total_forwarded
