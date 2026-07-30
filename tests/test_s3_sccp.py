from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IROpcode,
    IRRegister,
    IRType,
)
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_sccp



def test_sccp_prunes_unreachable_branches() -> None:
    fn = IRFunction(
        "main",
        (),
        IRType.TRYTE,
        (
            IRRegister(0, IRType.TRYTE),
            IRRegister(1, IRType.TRIT),
            IRRegister(2, IRType.TRYTE),
        ),
        (
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.CONST, result=0, immediate=1),
                    IRInstruction(IROpcode.CONST, result=2, immediate=0),
                    IRInstruction(IROpcode.COMPARE, result=1, operands=(0, 2)),
                    IRInstruction(IROpcode.BRANCH3, operands=(1,), targets=("neg", "neut", "pos")),
                ),
            ),
            IRBasicBlock("neg", (IRInstruction(IROpcode.CONST, result=0, immediate=-1), IRInstruction(IROpcode.RETURN, operands=(0,)))),
            IRBasicBlock("neut", (IRInstruction(IROpcode.CONST, result=0, immediate=0), IRInstruction(IROpcode.RETURN, operands=(0,)))),
            IRBasicBlock("pos", (IRInstruction(IROpcode.CONST, result=0, immediate=42), IRInstruction(IROpcode.RETURN, operands=(0,)))),
        ),
    )
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, folded, br_removed = run_ssa_sccp(ssa_fn)
    assert br_removed >= 1




def test_sccp_propagates_constants_through_phi() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 0\n"
        "    mut i: tryte = 10\n"
        "    match i <=> 0:\n"
        "        1:\n"
        "            x = 100\n"
        "        else:\n"
        "            x = 100\n"
        "    return x\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 100
