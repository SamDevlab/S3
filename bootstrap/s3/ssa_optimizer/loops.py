"""SSA loop and strength-reduction passes."""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Set, Tuple

from ..alias_analysis import AliasAnalysis
from ..builtin_effects import BuiltinEffect, builtin_effect
from ..cfg import ControlFlowGraph
from ..dominance import DominatorTree
from ..ir import IRBasicBlock, IRFunction, IRInstruction, IROpcode, IRType
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


def hoist_readonly_vector_length_queries(function: IRFunction) -> tuple[IRFunction, int]:
    """Hoist immutable parameter length queries from canonical loop headers."""
    cfg = ControlFlowGraph.build(function)
    dom_tree = DominatorTree.build(cfg)
    blocks_by_name = {block.name: block for block in function.blocks}
    parameters_by_register = {
        parameter.register: parameter for parameter in function.parameters
    }
    back_edges = [
        (tail, head)
        for tail in sorted(cfg.nodes)
        for head in sorted(cfg.nodes[tail].successors)
        if dom_tree.dominates(head, tail)
    ]
    if not back_edges:
        return function, 0

    moves: dict[tuple[str, int], str] = {}
    moved_calls: set[IRInstruction] = set()
    vector_length_builtins = {
        "tryte_vector_len",
        "i64_vector_len",
        "f64_vector_len",
    }

    for tail, header in back_edges:
        loop_blocks = {header, tail}
        worklist = [tail]
        while worklist:
            current = worklist.pop()
            for predecessor in sorted(cfg.nodes[current].predecessors, reverse=True):
                if (
                    predecessor not in loop_blocks
                    and dom_tree.dominates(header, predecessor)
                ):
                    loop_blocks.add(predecessor)
                    worklist.append(predecessor)

        loop_calls = [
            instruction
            for name in loop_blocks
            for instruction in blocks_by_name[name].instructions
            if instruction.opcode is IROpcode.CALL
        ]
        if any(
            builtin_effect(instruction.callee)
            not in {BuiltinEffect.PURE, BuiltinEffect.READ_ONLY}
            for instruction in loop_calls
        ):
            continue
        if any(
            instruction.opcode in {IROpcode.REFERENCE_STORE, IROpcode.SLICE_STORE}
            for name in loop_blocks
            for instruction in blocks_by_name[name].instructions
        ):
            continue

        outside_predecessors = sorted(
            predecessor
            for predecessor in cfg.nodes[header].predecessors
            if predecessor not in loop_blocks
        )
        if len(outside_predecessors) != 1:
            continue
        preheader = outside_predecessors[0]
        if not dom_tree.dominates(preheader, header):
            continue
        preheader_instructions = blocks_by_name[preheader].instructions
        if (
            not preheader_instructions
            or preheader_instructions[-1].opcode is not IROpcode.JUMP
            or preheader_instructions[-1].targets != (header,)
        ):
            continue

        header_block = blocks_by_name[header]
        for index, instruction in enumerate(header_block.instructions):
            if (
                instruction in moved_calls
                or instruction.opcode is not IROpcode.CALL
                or instruction.callee not in vector_length_builtins
                or len(instruction.operands) != 1
                or len(instruction.results) != 1
            ):
                continue
            parameter = parameters_by_register.get(instruction.operands[0])
            if (
                parameter is None
                or parameter.type is not IRType.REFERENCE
                or parameter.reference_mutable
            ):
                continue
            moves[(header, index)] = preheader
            moved_calls.add(instruction)

    if not moves:
        return function, 0

    removed: dict[str, set[int]] = {}
    insertions: dict[str, list[IRInstruction]] = {}
    for (source, index), destination in moves.items():
        removed.setdefault(source, set()).add(index)
        insertions.setdefault(destination, []).append(
            blocks_by_name[source].instructions[index]
        )

    updated_blocks: list[IRBasicBlock] = []
    for block in function.blocks:
        retained = [
            instruction
            for index, instruction in enumerate(block.instructions)
            if index not in removed.get(block.name, set())
        ]
        hoisted = insertions.get(block.name)
        if hoisted:
            terminator = retained.pop()
            retained.extend(hoisted)
            retained.append(terminator)
        updated_blocks.append(replace(block, instructions=tuple(retained)))

    return replace(function, blocks=tuple(updated_blocks)), len(moves)

# -----------------------------------------------------------------------------
# Milestone 0.87: Loop Invariant Code Motion (LICM)
# -----------------------------------------------------------------------------

def run_ssa_licm(
    ssa_fn: SSAFunction,
    *,
    hoist_pure_instructions: bool = True,
) -> Tuple[SSAFunction, int]:
    """Hoist safe invariants through a proven natural-loop preheader."""
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
    parameter_values = {parameter.value.name for parameter in ssa_fn.parameters}

    for tail_name, head_name in back_edges:
        loop_blocks: Set[str] = {head_name, tail_name}
        worklist = [tail_name]
        while worklist:
            curr = worklist.pop()
            if curr in cfg.nodes:
                for pred in sorted(cfg.nodes[curr].predecessors, reverse=True):
                    if pred not in loop_blocks and dom_tree.dominates(head_name, pred):
                        loop_blocks.add(pred)
                        worklist.append(pred)

        loop_instructions = [
            inst
            for block_name in loop_blocks
            if block_name in ssa_block_dict
            for inst in ssa_block_dict[block_name].instructions
        ]
        calls_are_read_only = all(
            inst.opcode is not IROpcode.CALL
            or builtin_effect(
                str(inst.immediate) if inst.immediate is not None else None
            )
            in {BuiltinEffect.PURE, BuiltinEffect.READ_ONLY}
            for inst in loop_instructions
        )
        loop_has_store = any(
            inst.opcode
            in {
                IROpcode.REFERENCE_STORE,
                IROpcode.SLICE_STORE,
            }
            for inst in loop_instructions
        )

        defined_in_loop = {
            inst.result.name
            for b_name in loop_blocks
            if b_name in ssa_block_dict
            for inst in ssa_block_dict[b_name].instructions
            if inst.result is not None
        } | {
            phi.target.name
            for b_name in loop_blocks
            if b_name in ssa_block_dict
            for phi in ssa_block_dict[b_name].phis
        }

        invariant_defs: Set[str] = set()
        hoistable_insts: List[Tuple[str, SSAInstruction]] = []

        changed = True
        while changed:
            changed = False
            for b_name in sorted(loop_blocks):
                block = ssa_block_dict[b_name]
                for inst in block.instructions:
                    is_safe_call = (
                        inst.opcode is IROpcode.CALL
                        and calls_are_read_only
                        and not loop_has_store
                        and builtin_effect(
                            str(inst.immediate) if inst.immediate is not None else None
                        ) is BuiltinEffect.READ_ONLY
                        and inst.immediate
                        in {
                            "tryte_vector_len",
                            "i64_vector_len",
                            "f64_vector_len",
                        }
                        and len(inst.operands) == 1
                        and inst.operands[0].type is IRType.REFERENCE
                        and not inst.operands[0].reference_mutable
                        and inst.operands[0].name in parameter_values
                    )
                    is_safe_pure_op = (
                        hoist_pure_instructions
                        and
                        inst.opcode in _PURE_REMOVABLE_OPCODES
                        and inst.opcode
                        not in {
                            IROpcode.JUMP,
                            IROpcode.BRANCH3,
                            IROpcode.CALL,
                            IROpcode.STORE,
                            IROpcode.LOAD,
                        }
                    )
                    if (
                        inst.result is not None
                        and inst.result.name not in invariant_defs
                        and (is_safe_call or is_safe_pure_op)
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
        if len(pre_header_candidates) != 1:
            continue
        target_pre_header = pre_header_candidates[0]
        if not dom_tree.dominates(target_pre_header, head_name):
            continue

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
