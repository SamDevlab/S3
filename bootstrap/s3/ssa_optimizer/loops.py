"""SSA loop and strength-reduction passes."""

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
# Milestone 0.87: Loop Invariant Code Motion (LICM)
# -----------------------------------------------------------------------------

def run_ssa_licm(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Hoists pure loop-invariant computations out of loops into pre-headers."""
    cfg = _cfg_from_ssa(ssa_fn)
    dom_tree = DominatorTree.build(cfg)

    back_edges: List[Tuple[str, str]] = []
    for node_name in sorted(cfg.nodes):
        node = cfg.nodes[node_name]
        for succ in sorted(node.successors):
            if dom_tree.dominates(succ, node_name):
                back_edges.append((node_name, succ))

    if not back_edges:
        return ssa_fn, 0

    hoisted_count = 0
    ssa_block_dict = {b.name: b for b in ssa_fn.blocks}

    for tail_name, head_name in back_edges:
        loop_blocks: Set[str] = {head_name, tail_name}
        worklist = [tail_name]
        while worklist:
            curr = worklist.pop()
            if curr in cfg.nodes:
                for pred in sorted(cfg.nodes[curr].predecessors, reverse=True):
                    if pred not in loop_blocks:
                        loop_blocks.add(pred)
                        worklist.append(pred)

        defined_in_loop = {
            inst.result.name
            for b_name in loop_blocks
            if b_name in ssa_block_dict
            for inst in ssa_block_dict[b_name].instructions
            if inst.result is not None
        }

        invariant_defs: Set[str] = set()
        hoistable_insts: List[Tuple[str, SSAInstruction]] = []

        changed = True
        while changed:
            changed = False
            for b_name in sorted(loop_blocks):
                block = ssa_block_dict[b_name]
                for inst in block.instructions:
                    if (
                        inst.result is not None
                        and inst.result.name not in invariant_defs
                        and inst.opcode in _PURE_REMOVABLE_OPCODES
                        and inst.opcode not in {IROpcode.JUMP, IROpcode.BRANCH3, IROpcode.CALL, IROpcode.STORE, IROpcode.LOAD}

                    ):
                        if all(
                            (op.name not in defined_in_loop or op.name in invariant_defs)
                            for op in inst.operands
                        ):
                            invariant_defs.add(inst.result.name)
                            hoistable_insts.append((b_name, inst))
                            changed = True

        if not hoistable_insts:
            continue

        pre_header_candidates = sorted(
            p
            for p in cfg.nodes[head_name].predecessors
            if p not in loop_blocks
        ) if head_name in cfg.nodes else []

        target_pre_header = pre_header_candidates[0] if pre_header_candidates else ssa_fn.blocks[0].name

        hoist_inst_set = {inst for _, inst in hoistable_insts}
        hoisted_count += len(hoist_inst_set)

        new_blocks: List[SSABlock] = []
        for block in ssa_fn.blocks:
            if block.name == target_pre_header:
                insts = [i for i in block.instructions if i not in hoist_inst_set]
                hoist_copies = [inst for _, inst in hoistable_insts]
                if insts and insts[-1].opcode in {IROpcode.JUMP, IROpcode.BRANCH3, IROpcode.RETURN}:
                    term = insts.pop()
                    insts.extend(hoist_copies)
                    insts.append(term)
                else:
                    insts.extend(hoist_copies)
                new_blocks.append(SSABlock(name=block.name, phis=list(block.phis), instructions=insts))
            else:
                insts = [i for i in block.instructions if i not in hoist_inst_set]
                new_blocks.append(SSABlock(name=block.name, phis=list(block.phis), instructions=insts))

        ssa_fn = SSAFunction(
            name=ssa_fn.name,
            parameters=ssa_fn.parameters,
            blocks=tuple(new_blocks),
            values=ssa_fn.values,
            memory_objects=ssa_fn.memory_objects,
            return_type=ssa_fn.return_type,
            result_types=ssa_fn.result_types,
        )

    return ssa_fn, hoisted_count


# -----------------------------------------------------------------------------
# Milestone 0.88: Strength Reduction
# -----------------------------------------------------------------------------

def run_ssa_strength_reduction(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Reduces operational complexity (e.g. repeated addition, algebraic reductions)."""
    def_inst_map: Dict[str, SSAInstruction] = {}
    for block in ssa_fn.blocks:
        for inst in block.instructions:
            if inst.result:
                def_inst_map[inst.result.name] = inst

    reductions_count = 0
    new_blocks: List[SSABlock] = []

    for block in ssa_fn.blocks:
        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.opcode is IROpcode.INVERT and inst.result and len(inst.operands) == 1:
                op0 = inst.operands[0]
                def0 = def_inst_map.get(op0.name)
                while def0 and def0.opcode is IROpcode.MOVE and def0.operands:
                    def0 = def_inst_map.get(def0.operands[0].name)
                if def0 and def0.opcode is IROpcode.INVERT and def0.operands:
                    reductions_count += 1
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.MOVE,
                            result=inst.result,
                            operands=(def0.operands[0],),
                            location=inst.location,
                        )
                    )
                    continue


            new_instructions.append(inst)

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=list(block.phis),
                instructions=new_instructions,
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
    ), reductions_count
