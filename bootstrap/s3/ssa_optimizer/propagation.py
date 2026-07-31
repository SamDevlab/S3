"""SSA constant and copy propagation passes."""

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
# Milestone 0.81: Sparse Constant Propagation (SSA)
# -----------------------------------------------------------------------------

def run_ssa_constant_propagation(ssa_fn: SSAFunction) -> SSAFunction:
    """Propagates constants across SSA assignments, phi nodes, and branches."""
    known_constants: Dict[str, int] = {}
    val_by_name: Dict[str, SSAValue] = {}

    for val in ssa_fn.values:
        val_by_name[val.name] = val

    def evaluate_inst(
        opcode: IROpcode, operands: Tuple[int, ...], res_type: IRType, op0_type: IRType
    ) -> int | None:
        try:
            if opcode is IROpcode.MOVE:
                return operands[0]
            elif opcode is IROpcode.INVERT:
                return invert(operands[0], _width(res_type))
            elif opcode is IROpcode.ADD:
                return add(operands[0], operands[1], _width(res_type))
            elif opcode is IROpcode.MINIMUM:
                return tritwise_min(operands[0], operands[1], _width(res_type))
            elif opcode is IROpcode.MAXIMUM:
                return tritwise_max(operands[0], operands[1], _width(res_type))
            elif opcode is IROpcode.COMPARE:
                return compare(operands[0], operands[1], _width(op0_type))
        except TernaryRangeError:
            return None
        return None

    changed = True
    while changed:
        changed = False

        for block in ssa_fn.blocks:
            for phi in block.phis:
                if phi.target.name in known_constants:
                    continue
                vals = [
                    known_constants[op.name]
                    for op in phi.operands.values()
                    if op.name in known_constants
                ]
                if vals and len(vals) == len(phi.operands) and len(set(vals)) == 1:
                    known_constants[phi.target.name] = vals[0]
                    changed = True

            for inst in block.instructions:
                if inst.result is None or inst.result.name in known_constants:
                    continue

                if inst.opcode is IROpcode.CONST and isinstance(inst.immediate, int):
                    known_constants[inst.result.name] = inst.immediate
                    changed = True
                elif inst.opcode in _FOLDABLE_OPCODES:
                    op_vals: List[int] = []
                    all_const = True
                    for op in inst.operands:
                        if op.name in known_constants:
                            op_vals.append(known_constants[op.name])
                        else:
                            all_const = False
                            break
                    if all_const and op_vals:
                        op0_type = inst.operands[0].type if inst.operands else IRType.TRYTE
                        folded = evaluate_inst(
                            inst.opcode, tuple(op_vals), inst.result.type, op0_type
                        )
                        if folded is not None:
                            known_constants[inst.result.name] = folded
                            changed = True

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
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
            else:
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
    )


# -----------------------------------------------------------------------------
# Milestone 0.82: Copy Propagation
# -----------------------------------------------------------------------------

def run_ssa_copy_propagation(ssa_fn: SSAFunction) -> SSAFunction:
    """Propagates aliases (MOVEs and single-value phis) across SSA form."""
    copies: Dict[str, SSAValue] = {}

    def get_canonical(val: SSAValue) -> SSAValue:
        curr = val
        visited: Set[str] = set()
        while curr.name in copies and curr.name not in visited:
            visited.add(curr.name)
            curr = copies[curr.name]
        return curr

    changed = True
    while changed:
        changed = False
        for block in ssa_fn.blocks:
            for phi in block.phis:
                if phi.target.name in copies:
                    continue
                resolved_ops = [
                    get_canonical(op).name for op in phi.operands.values()
                ]
                if resolved_ops and len(set(resolved_ops)) == 1:
                    copies[phi.target.name] = get_canonical(next(iter(phi.operands.values())))
                    changed = True

            for inst in block.instructions:
                if inst.opcode is IROpcode.MOVE and inst.result and inst.operands:
                    if inst.result.name not in copies:
                        canonical_src = get_canonical(inst.operands[0])
                        if canonical_src.name != inst.result.name and canonical_src.type == inst.result.type:
                            copies[inst.result.name] = canonical_src
                            changed = True


    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_phis: List[SSAPhiNode] = []
        for phi in block.phis:
            if phi.target.name in copies:
                continue
            updated_ops = {
                pred: get_canonical(val) for pred, val in phi.operands.items()
            }
            new_phis.append(
                SSAPhiNode(
                    target=phi.target,
                    original_register=phi.original_register,
                    operands=updated_ops,
                    location=phi.location,
                )
            )

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.result and inst.result.name in copies:
                continue
            updated_operands = tuple(get_canonical(op) for op in inst.operands)
            new_instructions.append(
                SSAInstruction(
                    opcode=inst.opcode,
                    result=inst.result,
                    operands=updated_operands,
                    immediate=inst.immediate,
                    targets=inst.targets,
                    memory=inst.memory,
                    initialization=inst.initialization,
                    location=inst.location,
                )
            )

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=new_phis,
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
    )
