"""SSA CSE and GVN passes."""

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

from .propagation import run_ssa_copy_propagation

# -----------------------------------------------------------------------------
# Milestone 0.84: Common Subexpression Elimination (CSE)
# -----------------------------------------------------------------------------

def run_ssa_cse(ssa_fn: SSAFunction) -> SSAFunction:
    """Eliminates common subexpressions in SSA form using dominator tree traversal."""
    cfg = _cfg_from_ssa(ssa_fn)
    dom_tree = DominatorTree.build(cfg)

    ssa_block_dict = {b.name: b for b in ssa_fn.blocks}
    expr_table: Dict[Tuple, SSAValue] = {}
    replacements: Dict[str, SSAValue] = {}

    def visit(block_name: str) -> None:
        block = ssa_block_dict[block_name]
        saved_keys: List[Tuple] = []

        for inst in block.instructions:
            if (
                inst.result is not None
                and inst.opcode in _PURE_REMOVABLE_OPCODES
                and inst.opcode not in {IROpcode.CONST, IROpcode.CONST_STR, IROpcode.MOVE}
            ):
                key = (
                    inst.opcode,
                    tuple(op.name for op in inst.operands),
                    inst.immediate,
                    inst.memory,
                    inst.result.type,
                )
                if key in expr_table:
                    existing = expr_table[key]
                    replacements[inst.result.name] = existing
                else:
                    expr_table[key] = inst.result
                    saved_keys.append(key)

        for child in dom_tree.children.get(block_name, set()):
            visit(child)

        for key in saved_keys:
            del expr_table[key]

    if ssa_fn.blocks:
        visit(cfg.entry_name)

    if not replacements:
        return ssa_fn

    def get_rep(val: SSAValue) -> SSAValue:
        curr = val
        visited: Set[str] = set()
        while curr.name in replacements and curr.name not in visited:
            visited.add(curr.name)
            curr = replacements[curr.name]
        return curr

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_phis: List[SSAPhiNode] = []
        for phi in block.phis:
            if phi.target.name in replacements:
                continue
            new_phis.append(
                SSAPhiNode(
                    target=phi.target,
                    original_register=phi.original_register,
                    operands={p: get_rep(v) for p, v in phi.operands.items()},
                    location=phi.location,
                )
            )

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.result and inst.result.name in replacements:
                rep_src = get_rep(replacements[inst.result.name])
                new_instructions.append(
                    SSAInstruction(
                        opcode=IROpcode.MOVE,
                        result=inst.result,
                        operands=(rep_src,),
                        location=inst.location,
                    )
                )
            else:
                updated_ops = tuple(get_rep(op) for op in inst.operands)
                new_instructions.append(
                    replace(inst, operands=updated_ops)
                )

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=new_phis,
                instructions=new_instructions,
            )
        )

    return run_ssa_copy_propagation(replace(ssa_fn, blocks=tuple(new_blocks)))


# -----------------------------------------------------------------------------
# Milestone 0.86: Global Value Numbering (GVN)
# -----------------------------------------------------------------------------

def run_ssa_gvn(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Computes Global Value Numbers for SSA expressions and eliminates redundant computations."""
    cfg = _cfg_from_ssa(ssa_fn)
    dom_tree = DominatorTree.build(cfg)

    ssa_block_dict = {b.name: b for b in ssa_fn.blocks}
    value_table: Dict[Tuple, SSAValue] = {}
    replacements: Dict[str, SSAValue] = {}
    eliminated_count = 0
    eligible_opcodes = _PURE_REMOVABLE_OPCODES - {
        IROpcode.LOAD,
        IROpcode.CONST,
        IROpcode.CONST_STR,
        IROpcode.MOVE,
    }

    def value_key(value: SSAValue) -> int | str:
        if value.original_register is not None:
            return value.original_register
        return value.name

    def visit(block_name: str) -> None:
        nonlocal eliminated_count
        block = ssa_block_dict[block_name]
        saved_keys: List[Tuple] = []

        for inst in block.instructions:
            if (
                inst.result is not None
                and inst.opcode in eligible_opcodes
            ):
                op_keys = tuple(
                    value_key(replacements.get(op.name, op))
                    for op in inst.operands
                )
                key = (
                    inst.opcode,
                    op_keys,
                    inst.immediate,
                    inst.memory,
                    inst.targets,
                    inst.initialization,
                    inst.result.type,
                )

                if key in value_table:
                    canonical_val = value_table[key]
                    replacements[inst.result.name] = canonical_val
                    eliminated_count += 1
                else:
                    value_table[key] = inst.result
                    saved_keys.append(key)

        for child in dom_tree.children.get(block_name, set()):
            visit(child)

        for key in saved_keys:
            del value_table[key]

    if ssa_fn.blocks:
        visit(cfg.entry_name)

    if not replacements:
        return ssa_fn, 0

    def get_rep(val: SSAValue) -> SSAValue:
        curr = val
        visited: Set[str] = set()
        while curr.name in replacements and curr.name not in visited:
            visited.add(curr.name)
            curr = replacements[curr.name]
        return curr

    removed_count = 0
    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_phis: List[SSAPhiNode] = []
        for phi in block.phis:
            new_phis.append(
                SSAPhiNode(
                    target=phi.target,
                    original_register=phi.original_register,
                    operands={p: get_rep(v) for p, v in phi.operands.items()},
                    location=phi.location,
                )
            )

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.result and inst.result.name in replacements:
                removed_count += 1
                continue
            updated_ops = tuple(get_rep(op) for op in inst.operands)
            new_instructions.append(
                replace(inst, operands=updated_ops)
            )

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=new_phis,
                instructions=new_instructions,
            )
        )

    if removed_count == 0:
        return ssa_fn, 0

    transformed = replace(ssa_fn, blocks=tuple(new_blocks))
    opt_fn = run_ssa_copy_propagation(transformed)
    return opt_fn, removed_count
