"""Local SSA peephole simplifications."""

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
# Milestone 0.85: Peephole SSA
# -----------------------------------------------------------------------------

def run_ssa_peephole(ssa_fn: SSAFunction) -> SSAFunction:
    """Applies local SSA algebraic and identity simplifications."""
    def_inst_map: Dict[str, SSAInstruction] = {}
    for block in ssa_fn.blocks:
        for inst in block.instructions:
            if inst.result:
                def_inst_map[inst.result.name] = inst

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_phis: List[SSAPhiNode] = []
        for phi in block.phis:
            ops = list(phi.operands.values())
            if ops and all(op.name == ops[0].name for op in ops):
                new_phis.append(phi)
            else:
                new_phis.append(phi)

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.opcode is IROpcode.MOVE and inst.result and inst.operands:
                if inst.result.name == inst.operands[0].name:
                    continue

            if inst.opcode is IROpcode.ADD and inst.result and len(inst.operands) == 2:
                op0, op1 = inst.operands[0], inst.operands[1]
                if op0.name in def_inst_map:
                    def0 = def_inst_map[op0.name]
                    if def0.opcode is IROpcode.CONST and def0.immediate == 0:
                        new_instructions.append(
                            SSAInstruction(
                                opcode=IROpcode.MOVE,
                                result=inst.result,
                                operands=(op1,),
                                location=inst.location,
                            )
                        )
                        continue
                if op1.name in def_inst_map:
                    def1 = def_inst_map[op1.name]
                    if def1.opcode is IROpcode.CONST and def1.immediate == 0:
                        new_instructions.append(
                            SSAInstruction(
                                opcode=IROpcode.MOVE,
                                result=inst.result,
                                operands=(op0,),
                                location=inst.location,
                            )
                        )
                        continue

            if inst.opcode is IROpcode.MINIMUM and inst.result and len(inst.operands) == 2:
                if inst.operands[0].name == inst.operands[1].name:
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.MOVE,
                            result=inst.result,
                            operands=(inst.operands[0],),
                            location=inst.location,
                        )
                    )
                    continue

            if inst.opcode is IROpcode.MAXIMUM and inst.result and len(inst.operands) == 2:
                if inst.operands[0].name == inst.operands[1].name:
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.MOVE,
                            result=inst.result,
                            operands=(inst.operands[0],),
                            location=inst.location,
                        )
                    )
                    continue

            if inst.opcode is IROpcode.COMPARE and inst.result and len(inst.operands) == 2:
                if inst.operands[0].name == inst.operands[1].name:
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.CONST,
                            result=inst.result,
                            immediate=0,
                            location=inst.location,
                        )
                    )
                    continue

            if inst.opcode is IROpcode.INVERT and inst.result and len(inst.operands) == 1:
                op0 = inst.operands[0]
                if op0.name in def_inst_map:
                    def0 = def_inst_map[op0.name]
                    if def0.opcode is IROpcode.INVERT and def0.operands:
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
