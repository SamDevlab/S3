from __future__ import annotations

from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.dominance import DominatorTree
from bootstrap.s3.ir import IROpcode, IRType
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import (
    SSABlock,
    SSAFunction,
    SSAInstruction,
    SSAPhiNode,
    SSAValue,
    validate_ssa,
)
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_gvn


def _value(
    name: str,
    original_register: int,
    type_name: IRType = IRType.TRYTE,
    block: str = "entry",
) -> SSAValue:
    return SSAValue(
        name,
        original_register=original_register,
        type=type_name,
        def_block=block,
    )


def _instruction_count(ssa_fn: SSAFunction) -> int:
    return sum(len(block.instructions) for block in ssa_fn.blocks)


def _operand_names(ssa_fn: SSAFunction) -> set[str]:
    return {
        operand.name
        for block in ssa_fn.blocks
        for inst in block.instructions
        for operand in inst.operands
    }


def _validate_returned_ssa(ssa_fn: SSAFunction) -> None:
    ir_fn = ssa_fn.to_ir()
    cfg = ControlFlowGraph.build(ir_fn)
    dom_tree = DominatorTree.build(cfg)
    validate_ssa(ssa_fn, cfg, dom_tree)


def test_gvn_detects_equivalent_expressions() -> None:
    source = (
        "fn helper(a: tryte, b: tryte) -> tryte:\n"
        "    x: tryte = a + b\n"
        "    y: tryte = a + b\n"
        "    return x + y\n"
        "fn main() -> tryte:\n"
        "    return helper(10, 20)\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, eliminated = run_ssa_gvn(ssa_fn)

    assert eliminated >= 1
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 60


def test_gvn_across_dominating_blocks() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut cond: tryte = 1\n"
        "    a: tryte = 15\n"
        "    b: tryte = 25\n"
        "    base: tryte = a + b\n"
        "    mut res: tryte = 0\n"
        "    match cond <=> 0:\n"
        "        1:\n"
        "            res = a + b\n"
        "        else:\n"
        "            res = base\n"
        "    return res\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 40


def test_gvn_returned_function_contains_same_block_elimination() -> None:
    left = _value("left", 0)
    right = _value("right", 1)
    first = _value("first", 2)
    second = _value("second", 3)
    total = _value("total", 4)
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(left, right, first, second, total),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=left, immediate=10),
                    SSAInstruction(IROpcode.CONST, result=right, immediate=20),
                    SSAInstruction(IROpcode.ADD, result=first, operands=(left, right)),
                    SSAInstruction(IROpcode.ADD, result=second, operands=(left, right)),
                    SSAInstruction(IROpcode.ADD, result=total, operands=(second, second)),
                    SSAInstruction(IROpcode.RETURN, operands=(total,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, eliminated = run_ssa_gvn(ssa_fn)

    assert eliminated == 1
    assert _instruction_count(optimized) == _instruction_count(ssa_fn) - 1
    assert "second" not in _operand_names(optimized)
    assert "first" in _operand_names(optimized)
    _validate_returned_ssa(optimized)


def test_gvn_does_not_reuse_value_from_sibling_branch() -> None:
    left = _value("left", 0)
    right = _value("right", 1)
    cond = _value("cond", 2, IRType.TRIT)
    left_sum = _value("left_sum", 3, block="left")
    right_sum = _value("right_sum", 4, block="right")
    neutral_sum = _value("neutral_sum", 5, block="neutral")
    merged = _value("merged", 6, block="join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(left, right, cond, left_sum, right_sum, neutral_sum, merged),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=left, immediate=10),
                    SSAInstruction(IROpcode.CONST, result=right, immediate=20),
                    SSAInstruction(IROpcode.CONST, result=cond, immediate=-1),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(cond,),
                        targets=("left", "neutral", "right"),
                    ),
                ],
            ),
            SSABlock(
                "left",
                instructions=[
                    SSAInstruction(IROpcode.ADD, result=left_sum, operands=(left, right)),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "neutral",
                instructions=[
                    SSAInstruction(IROpcode.ADD, result=neutral_sum, operands=(left, right)),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "right",
                instructions=[
                    SSAInstruction(IROpcode.ADD, result=right_sum, operands=(left, right)),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "join",
                phis=[
                    SSAPhiNode(
                        target=merged,
                        original_register=4,
                        operands={
                            "left": left_sum,
                            "neutral": neutral_sum,
                            "right": right_sum,
                        },
                    )
                ],
                instructions=[SSAInstruction(IROpcode.RETURN, operands=(merged,))],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, eliminated = run_ssa_gvn(ssa_fn)

    assert eliminated == 0
    assert optimized.blocks == ssa_fn.blocks


def test_gvn_reuses_value_from_dominating_block() -> None:
    left = _value("left", 0)
    right = _value("right", 1)
    cond = _value("cond", 2, IRType.TRIT)
    base = _value("base", 3)
    right_sum = _value("right_sum", 4, block="right")
    merged = _value("merged", 5, block="join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(left, right, cond, base, right_sum, merged),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=left, immediate=10),
                    SSAInstruction(IROpcode.CONST, result=right, immediate=20),
                    SSAInstruction(IROpcode.CONST, result=cond, immediate=1),
                    SSAInstruction(IROpcode.ADD, result=base, operands=(left, right)),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(cond,),
                        targets=("left", "neutral", "right"),
                    ),
                ],
            ),
            SSABlock("left", instructions=[SSAInstruction(IROpcode.JUMP, targets=("join",))]),
            SSABlock("neutral", instructions=[SSAInstruction(IROpcode.JUMP, targets=("join",))]),
            SSABlock(
                "right",
                instructions=[
                    SSAInstruction(IROpcode.ADD, result=right_sum, operands=(left, right)),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "join",
                phis=[
                    SSAPhiNode(
                        target=merged,
                        original_register=4,
                        operands={"left": base, "neutral": base, "right": right_sum},
                    )
                ],
                instructions=[SSAInstruction(IROpcode.RETURN, operands=(merged,))],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, eliminated = run_ssa_gvn(ssa_fn)

    assert eliminated == 1
    assert "right_sum" not in _operand_names(optimized)
    assert _instruction_count(optimized) == _instruction_count(ssa_fn) - 1


def test_gvn_keeps_different_types_immediates_memory_and_effects_distinct() -> None:
    index = _value("index", 0)
    left = _value("left", 1)
    right = _value("right", 2)
    trit_left = _value("trit_left", 3, IRType.TRIT)
    trit_right = _value("trit_right", 4, IRType.TRIT)
    tryte_add = _value("tryte_add", 5)
    trit_add = _value("trit_add", 6, IRType.TRIT)
    invert_zero = _value("invert_zero", 7)
    invert_one = _value("invert_one", 8)
    load_first = _value("load_first", 9)
    load_second = _value("load_second", 10)
    call_first = _value("call_first", 11)
    call_second = _value("call_second", 12)
    result = _value("result", 13)
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(
            index,
            left,
            right,
            trit_left,
            trit_right,
            tryte_add,
            trit_add,
            invert_zero,
            invert_one,
            load_first,
            load_second,
            call_first,
            call_second,
            result,
        ),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=index, immediate=0),
                    SSAInstruction(IROpcode.CONST, result=left, immediate=10),
                    SSAInstruction(IROpcode.CONST, result=right, immediate=20),
                    SSAInstruction(IROpcode.CONST, result=trit_left, immediate=-1),
                    SSAInstruction(IROpcode.CONST, result=trit_right, immediate=1),
                    SSAInstruction(IROpcode.ADD, result=tryte_add, operands=(left, right)),
                    SSAInstruction(IROpcode.ADD, result=trit_add, operands=(trit_left, trit_right)),
                    SSAInstruction(IROpcode.INVERT, result=invert_zero, operands=(left,), immediate=0),
                    SSAInstruction(IROpcode.INVERT, result=invert_one, operands=(left,), immediate=1),
                    SSAInstruction(IROpcode.LOAD, result=load_first, operands=(index,), memory=0),
                    SSAInstruction(IROpcode.LOAD, result=load_second, operands=(index,), memory=0),
                    SSAInstruction(IROpcode.CALL, result=call_first, immediate="helper"),
                    SSAInstruction(IROpcode.CALL, result=call_second, immediate="helper"),
                    SSAInstruction(IROpcode.ADD, result=result, operands=(tryte_add, load_second)),
                    SSAInstruction(IROpcode.RETURN, operands=(result,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, eliminated = run_ssa_gvn(ssa_fn)

    assert eliminated == 0
    assert optimized.blocks == ssa_fn.blocks


def test_gvn_public_o0_o1_equivalence_for_redundant_expression() -> None:
    source = (
        "fn helper(a: tryte, b: tryte) -> tryte:\n"
        "    x: tryte = a + b\n"
        "    y: tryte = a + b\n"
        "    return x + y\n"
        "fn main() -> tryte:\n"
        "    return helper(9, 12)\n"
    )

    assert run_source(source, optimization="O0", mode=SyntaxMode.V0_6) == 42
    assert run_source(source, optimization="O1", mode=SyntaxMode.V0_6) == 42
