"""Sparse conditional constant propagation for SSA."""

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
# Milestone 0.89: Sparse Conditional Constant Propagation (SCCP)
# -----------------------------------------------------------------------------

def run_ssa_sccp(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int, int]:
    """Sparse Conditional Constant Propagation using dual CFG and SSA edge tracking."""
    cfg = _cfg_from_ssa(ssa_fn)

    known_constants: Dict[str, int] = {}
    executable_blocks: Set[str] = {cfg.entry_name}
    executable_edges: Set[Tuple[str, str]] = set()

    cfg_worklist: List[Tuple[str, str]] = []
    if cfg.entry_name in cfg.nodes:
        for succ in sorted(cfg.nodes[cfg.entry_name].successors):
            cfg_worklist.append((cfg.entry_name, succ))

    expressions_folded = 0
    branches_removed = 0

    changed = True
    while changed or cfg_worklist:
        changed = False

        while cfg_worklist:
            u, v = cfg_worklist.pop(0)
            if (u, v) not in executable_edges:
                executable_edges.add((u, v))
                first_visit = v not in executable_blocks
                executable_blocks.add(v)

                if first_visit and v in cfg.nodes:
                    for succ in sorted(cfg.nodes[v].successors):
                        cfg_worklist.append((v, succ))

        for block in ssa_fn.blocks:
            if block.name not in executable_blocks:
                continue

            for phi in block.phis:
                if phi.target.name in known_constants:
                    continue
                incoming_vals = [
                    known_constants[val.name]
                    for pred, val in phi.operands.items()
                    if (pred, block.name) in executable_edges and val.name in known_constants
                ]
                if incoming_vals and len(set(incoming_vals)) == 1:
                    known_constants[phi.target.name] = incoming_vals[0]
                    changed = True

            for inst in block.instructions:
                if inst.result is not None and inst.result.name not in known_constants:
                    if inst.opcode is IROpcode.CONST and isinstance(inst.immediate, int):
                        known_constants[inst.result.name] = inst.immediate
                        changed = True
                    elif inst.opcode in _FOLDABLE_OPCODES:
                        op_vals = [
                            known_constants[op.name]
                            for op in inst.operands
                            if op.name in known_constants
                        ]
                        if len(op_vals) == len(inst.operands) and op_vals:
                            try:
                                res_type = inst.result.type
                                op0_type = inst.operands[0].type if inst.operands else IRType.TRYTE
                                folded = None
                                if inst.opcode is IROpcode.MOVE:
                                    folded = op_vals[0]
                                elif inst.opcode is IROpcode.INVERT:
                                    folded = invert(op_vals[0], _width(res_type))
                                elif inst.opcode is IROpcode.ADD:
                                    folded = add(op_vals[0], op_vals[1], _width(res_type))
                                elif inst.opcode is IROpcode.MINIMUM:
                                    folded = tritwise_min(op_vals[0], op_vals[1], _width(res_type))
                                elif inst.opcode is IROpcode.MAXIMUM:
                                    folded = tritwise_max(op_vals[0], op_vals[1], _width(res_type))
                                elif inst.opcode is IROpcode.COMPARE:
                                    folded = compare(op_vals[0], op_vals[1], _width(op0_type))

                                if folded is not None:
                                    known_constants[inst.result.name] = folded
                                    changed = True
                            except TernaryRangeError:
                                pass

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        if block.name not in executable_blocks:
            branches_removed += 1
            continue

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.opcode is IROpcode.BRANCH3 and inst.operands:
                cond_val = inst.operands[0]
                if cond_val.name in known_constants:
                    c = known_constants[cond_val.name]
                    target = (
                        inst.targets[0]
                        if c < 0
                        else (inst.targets[1] if c == 0 else inst.targets[2])
                    )
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.JUMP,
                            targets=(target,),
                            location=inst.location,
                        )
                    )
                    branches_removed += 1
                    continue

            if (
                inst.result is not None
                and inst.result.name in known_constants
                and inst.opcode not in {IROpcode.CONST, IROpcode.CONST_STR}
            ):
                new_instructions.append(
                    SSAInstruction(
                        opcode=IROpcode.CONST,
                        result=inst.result,
                        immediate=known_constants[inst.result.name],
                        location=inst.location,
                    )
                )
                expressions_folded += 1
            else:
                new_instructions.append(inst)

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=list(block.phis),
                instructions=new_instructions,
            )
        )

    if not any(
        inst.opcode is IROpcode.RETURN
        for block in new_blocks
        for inst in block.instructions
    ):
        for block in ssa_fn.blocks:
            if any(inst.opcode is IROpcode.RETURN for inst in block.instructions):
                new_blocks.append(block)
                branches_removed -= 1
                break

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
        result_types=ssa_fn.result_types,
    ), expressions_folded, branches_removed
