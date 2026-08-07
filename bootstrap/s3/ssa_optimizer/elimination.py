"""SSA dead-code and dead-store elimination passes."""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Set, Tuple

from ..alias_analysis import AliasAnalysis
from ..cfg import ControlFlowGraph
from ..dominance import DominatorTree
from ..ir import IROpcode, IRType
from ..ssa import SSABlock, SSAFunction, SSAInstruction, SSAPhiNode, SSAValue
from ..ternary import (
    TernaryRangeError,
    add,
    compare,
    invert,
    tritwise_max,
    tritwise_min,
)
from .common import _FOLDABLE_OPCODES, _PURE_REMOVABLE_OPCODES, _width
from .lowering import _cfg_from_ssa

# -----------------------------------------------------------------------------
# Milestone 0.83: Dead Code Elimination
# -----------------------------------------------------------------------------

def run_ssa_dead_code_elimination(ssa_fn: SSAFunction) -> SSAFunction:
    """Removes unused instructions and dead phi nodes without side effects."""
    blocks = list(ssa_fn.blocks)
    changed = True

    while changed:
        changed = False
        used: Set[str] = set()
        for block in blocks:
            for phi in block.phis:
                for val in phi.operands.values():
                    used.add(val.name)
            for inst in block.instructions:
                for op in inst.operands:
                    used.add(op.name)

        updated_blocks: List[SSABlock] = []
        for block in blocks:
            new_phis = [phi for phi in block.phis if phi.target.name in used]
            if len(new_phis) != len(block.phis):
                changed = True

            new_instructions: List[SSAInstruction] = []
            for inst in block.instructions:
                if (
                    inst.result is not None
                    and inst.result.name not in used
                    and inst.opcode in _PURE_REMOVABLE_OPCODES
                ):
                    changed = True
                else:
                    new_instructions.append(inst)

            updated_blocks.append(
                SSABlock(
                    name=block.name,
                    phis=new_phis,
                    instructions=new_instructions,
                )
            )

        blocks = updated_blocks

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
        result_types=ssa_fn.result_types,
    )


# -----------------------------------------------------------------------------
# Milestone 0.91: Aggressive Dead Code Elimination (ADCE)
# -----------------------------------------------------------------------------

def run_ssa_adce(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Mark-and-sweep Aggressive Dead Code Elimination (ADCE) for SSA form."""
    live_values: Set[str] = set()
    live_instructions: Set[SSAInstruction] = set()
    worklist: List[SSAInstruction] = []

    # Map SSA values to defining instructions/phis
    def_map: Dict[str, SSAInstruction] = {}
    phi_def_map: Dict[str, SSAPhiNode] = {}
    for block in ssa_fn.blocks:
        for phi in block.phis:
            phi_def_map[phi.target.name] = phi
        for inst in block.instructions:
            if inst.result:
                def_map[inst.result.name] = inst

    # Root marking: Control flow, side-effecting operations (STORE, CALL, RETURN, etc.)
    for block in ssa_fn.blocks:
        for inst in block.instructions:
            if inst.opcode in {IROpcode.STORE, IROpcode.CALL, IROpcode.RETURN, IROpcode.JUMP, IROpcode.BRANCH3}:
                live_instructions.add(inst)
                worklist.append(inst)

    # Transitive marking phase
    while worklist:
        inst = worklist.pop()
        for op in inst.operands:
            if op.name not in live_values:
                live_values.add(op.name)
                if op.name in def_map:
                    parent_inst = def_map[op.name]
                    if parent_inst not in live_instructions:
                        live_instructions.add(parent_inst)
                        worklist.append(parent_inst)

    # Mark live Phis whose target is live
    live_phis: Set[SSAPhiNode] = set()
    for block in ssa_fn.blocks:
        for phi in block.phis:
            if phi.target.name in live_values:
                live_phis.add(phi)
                for op in phi.operands.values():
                    if op.name in def_map and def_map[op.name] not in live_instructions:
                        live_instructions.add(def_map[op.name])
                        worklist.append(def_map[op.name])

    # Sweep phase
    removed_count = 0
    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        filtered_phis = [phi for phi in block.phis if phi in live_phis or phi.target.name in live_values]
        filtered_insts: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst in live_instructions or (inst.result and inst.result.name in live_values):
                filtered_insts.append(inst)
            else:
                removed_count += 1

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=filtered_phis,
                instructions=filtered_insts,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
        result_types=ssa_fn.result_types,
    ), removed_count


# -----------------------------------------------------------------------------
# Milestone 0.92: Dead Store Elimination (DSE)
# -----------------------------------------------------------------------------

def run_ssa_dse(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Eliminates intra-block redundant STORE operations using Alias Analysis."""
    dead_stores: Set[SSAInstruction] = set()
    known_consts: Dict[str, int] = {}
    for block in ssa_fn.blocks:
        for inst in block.instructions:
            if inst.opcode is IROpcode.CONST and inst.result and isinstance(inst.immediate, int):
                known_consts[inst.result.name] = inst.immediate

    def index_key(value: SSAValue) -> int | str:
        if value.name in known_consts:
            return known_consts[value.name]
        return value.name

    for block in ssa_fn.blocks:
        last_store_per_cell: Dict[Tuple[int, int | str], SSAInstruction] = {}

        for inst in block.instructions:
            if inst.opcode is IROpcode.STORE and inst.operands and inst.memory is not None:
                idx_op = inst.operands[0]
                idx_key = index_key(idx_op)
                cell_key = (inst.memory, idx_key)
                for pending_key, pending_store in tuple(last_store_per_cell.items()):
                    if AliasAnalysis.must_alias_cell(
                        pending_key[0],
                        pending_key[1],
                        cell_key[0],
                        cell_key[1],
                    ):
                        dead_stores.add(pending_store)
                        del last_store_per_cell[pending_key]
                last_store_per_cell[cell_key] = inst

            elif inst.opcode is IROpcode.LOAD and inst.memory is not None:
                # A load may observe any pending store that aliases its cell.
                mem_idx = inst.memory
                load_idx = index_key(inst.operands[0]) if inst.operands else None
                to_clear = [
                    c for c in last_store_per_cell
                    if AliasAnalysis.may_alias_cell(c[0], c[1], mem_idx, load_idx)
                ]
                for c in to_clear:
                    del last_store_per_cell[c]
            elif inst.opcode is IROpcode.CALL:
                # Calls may observe any memory location
                last_store_per_cell.clear()


    if not dead_stores:
        return ssa_fn, 0

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        filtered_insts = [inst for inst in block.instructions if inst not in dead_stores]
        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=list(block.phis),
                instructions=filtered_insts,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
        result_types=ssa_fn.result_types,
    ), len(dead_stores)


# -----------------------------------------------------------------------------
# Milestone 4: conservative global dead-store elimination
# -----------------------------------------------------------------------------

def run_ssa_global_dse(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Remove stores to frame objects that are never loaded in the function.

    S3 memory objects are frame-local and pointers are not part of the language,
    so a store to an object with no LOAD has no observable consumer. Calls cannot
    access a caller's frame-local objects. Objects that have any LOAD remain
    untouched because this pass does not claim a path-sensitive memory proof.
    """
    loaded_memory = {
        instruction.memory
        for block in ssa_fn.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.LOAD
        and instruction.memory is not None
    }
    dead_stores = {
        instruction
        for block in ssa_fn.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.STORE
        and instruction.memory is not None
        and instruction.memory not in loaded_memory
    }
    if not dead_stores:
        return ssa_fn, 0

    blocks = tuple(
        SSABlock(
            name=block.name,
            phis=list(block.phis),
            instructions=[
                instruction
                for instruction in block.instructions
                if instruction not in dead_stores
            ],
        )
        for block in ssa_fn.blocks
    )
    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=blocks,
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
        result_types=ssa_fn.result_types,
    ), len(dead_stores)
