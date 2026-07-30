from __future__ import annotations

import pytest

from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.dominance import DominatorTree
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa import (
    SSABlock,
    SSABuilder,
    SSAFunction,
    SSAInstruction,
    SSAPhiNode,
    SSAValue,
    SSAValidationError,
    validate_ssa,
)
from bootstrap.s3.ir import IROpcode, IRType


def test_ssa_validation_valid_program() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    while i < 3:\n"
        "        i = i + 1\n"
        "    return i\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    cfg = ControlFlowGraph.build(fn)
    dom_tree = DominatorTree.build(cfg)
    ssa_fn = SSABuilder.build_function(fn)

    # Must validate cleanly without exception
    validate_ssa(ssa_fn, cfg, dom_tree)


def test_ssa_validation_duplicate_def_raises() -> None:
    v1 = SSAValue("r1_v0", original_register=1, type=IRType.TRYTE, def_block="entry")
    inst1 = SSAInstruction(opcode=IROpcode.CONST, result=v1, immediate=10)
    inst2 = SSAInstruction(opcode=IROpcode.CONST, result=v1, immediate=20)
    block = SSABlock(name="entry", instructions=[inst1, inst2])
    ssa_fn = SSAFunction(name="main", parameters=(), blocks=(block,), values=(v1,))

    from bootstrap.s3.ir import IRBasicBlock, IRFunction
    ir_b = IRBasicBlock(name="entry", instructions=())
    ir_fn = IRFunction(name="main", parameters=(), return_type=IRType.TRYTE, registers=(), blocks=(ir_b,))
    cfg = ControlFlowGraph.build(ir_fn)
    dom_tree = DominatorTree.build(cfg)

    with pytest.raises(SSAValidationError, match="duplicate definition"):
        validate_ssa(ssa_fn, cfg, dom_tree)
