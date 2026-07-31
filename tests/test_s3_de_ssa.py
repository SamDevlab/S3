from __future__ import annotations

from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.ir import IROpcode, IRModule, IRType
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source
from bootstrap.s3.ssa import (
    SSABlock,
    SSAFunction,
    SSAInstruction,
    SSAParameter,
    SSAPhiNode,
    SSAValue,
)
from bootstrap.s3.ssa_opt import to_ir
from bootstrap.s3.verifier import verify_ir


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


def _execute(ssa_fn: SSAFunction) -> int:
    ir_fn = to_ir(ssa_fn)
    module = IRModule((ir_fn,))
    verify_ir(module)
    return Emulator().execute(generate_assembly(module))


def test_de_ssa_lowers_simple_diamond_phi() -> None:
    cond = _value("cond", 0, IRType.TRIT)
    left = _value("left", 1, block="left")
    neutral = _value("neutral", 2, block="neutral")
    right = _value("right", 3, block="right")
    merged = _value("merged", 4, block="join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(cond, left, neutral, right, merged),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=cond, immediate=1),
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
                    SSAInstruction(IROpcode.CONST, result=left, immediate=5),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "neutral",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=neutral, immediate=7),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "right",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=right, immediate=9),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "join",
                phis=[
                    SSAPhiNode(
                        target=merged,
                        original_register=4,
                        operands={"left": left, "neutral": neutral, "right": right},
                    )
                ],
                instructions=[SSAInstruction(IROpcode.RETURN, operands=(merged,))],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    assert _execute(ssa_fn) == 9


def test_de_ssa_lowers_multiple_phis_with_parallel_sources() -> None:
    cond = _value("cond", 0, IRType.TRIT)
    left_a = _value("left_a", 1, block="left")
    left_b = _value("left_b", 2, block="left")
    right_a = _value("right_a", 3, block="right")
    right_b = _value("right_b", 4, block="right")
    merged_a = _value("merged_a", 5, block="join")
    merged_b = _value("merged_b", 6, block="join")
    total = _value("total", 7, block="join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(cond, left_a, left_b, right_a, right_b, merged_a, merged_b, total),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
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
                    SSAInstruction(IROpcode.CONST, result=left_a, immediate=1),
                    SSAInstruction(IROpcode.CONST, result=left_b, immediate=2),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "neutral",
                instructions=[SSAInstruction(IROpcode.JUMP, targets=("right",))],
            ),
            SSABlock(
                "right",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=right_a, immediate=3),
                    SSAInstruction(IROpcode.CONST, result=right_b, immediate=4),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "join",
                phis=[
                    SSAPhiNode(
                        target=merged_a,
                        original_register=5,
                        operands={"left": left_b, "right": right_a},
                    ),
                    SSAPhiNode(
                        target=merged_b,
                        original_register=6,
                        operands={"left": left_a, "right": right_b},
                    ),
                ],
                instructions=[
                    SSAInstruction(IROpcode.ADD, result=total, operands=(merged_a, merged_b)),
                    SSAInstruction(IROpcode.RETURN, operands=(total,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    assert _execute(ssa_fn) == 3


def test_de_ssa_lowers_three_value_parallel_cycle_shape() -> None:
    cond = _value("cond", 0, IRType.TRIT)
    left_a = _value("left_a", 1, block="left")
    left_b = _value("left_b", 2, block="left")
    left_c = _value("left_c", 3, block="left")
    right_a = _value("right_a", 9, block="right")
    right_b = _value("right_b", 10, block="right")
    right_c = _value("right_c", 11, block="right")
    merged_a = _value("merged_a", 4, block="join")
    merged_b = _value("merged_b", 5, block="join")
    merged_c = _value("merged_c", 6, block="join")
    sum_ab = _value("sum_ab", 7, block="join")
    total = _value("total", 8, block="join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(
            cond,
            left_a,
            left_b,
            left_c,
            right_a,
            right_b,
            right_c,
            merged_a,
            merged_b,
            merged_c,
            sum_ab,
            total,
        ),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
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
                    SSAInstruction(IROpcode.CONST, result=left_a, immediate=1),
                    SSAInstruction(IROpcode.CONST, result=left_b, immediate=2),
                    SSAInstruction(IROpcode.CONST, result=left_c, immediate=3),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock("neutral", instructions=[SSAInstruction(IROpcode.JUMP, targets=("right",))]),
            SSABlock(
                "right",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=right_a, immediate=4),
                    SSAInstruction(IROpcode.CONST, result=right_b, immediate=5),
                    SSAInstruction(IROpcode.CONST, result=right_c, immediate=6),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "join",
                phis=[
                    SSAPhiNode(
                        target=merged_a,
                        original_register=1,
                        operands={"left": left_b, "right": right_b},
                    ),
                    SSAPhiNode(
                        target=merged_b,
                        original_register=2,
                        operands={"left": left_c, "right": right_c},
                    ),
                    SSAPhiNode(
                        target=merged_c,
                        original_register=3,
                        operands={"left": left_a, "right": right_a},
                    ),
                ],
                instructions=[
                    SSAInstruction(IROpcode.ADD, result=sum_ab, operands=(merged_a, merged_b)),
                    SSAInstruction(IROpcode.ADD, result=total, operands=(sum_ab, merged_c)),
                    SSAInstruction(IROpcode.RETURN, operands=(total,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    assert _execute(ssa_fn) == 6


def test_de_ssa_lowers_loop_header_phi_and_back_edge() -> None:
    initial = _value("initial", 0, IRType.TRIT)
    loop_value = _value("loop_value", 1, IRType.TRIT, block="header")
    next_value = _value("next_value", 2, IRType.TRIT, block="body")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(initial, loop_value, next_value),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=initial, immediate=-1),
                    SSAInstruction(IROpcode.JUMP, targets=("header",)),
                ],
            ),
            SSABlock(
                "header",
                phis=[
                    SSAPhiNode(
                        target=loop_value,
                        original_register=1,
                        operands={"entry": initial, "body": next_value},
                    )
                ],
                instructions=[
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(loop_value,),
                        targets=("body", "exit_zero", "exit_pos"),
                    )
                ],
            ),
            SSABlock(
                "body",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=next_value, immediate=0),
                    SSAInstruction(IROpcode.JUMP, targets=("header",)),
                ],
            ),
            SSABlock("exit_zero", instructions=[SSAInstruction(IROpcode.RETURN, operands=(loop_value,))]),
            SSABlock("exit_pos", instructions=[SSAInstruction(IROpcode.RETURN, operands=(loop_value,))]),
        ),
        return_type=IRType.TRIT,
    )

    assert _execute(ssa_fn) == 0


def test_de_ssa_splits_branch_edge_for_phi_copy() -> None:
    cond = _value("cond", 0, IRType.TRIT)
    direct = _value("direct", 1)
    other = _value("other", 2, block="other")
    merged = _value("merged", 3, block="join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(cond, direct, other, merged),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=cond, immediate=0),
                    SSAInstruction(IROpcode.CONST, result=direct, immediate=11),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(cond,),
                        targets=("join", "other", "exit"),
                    ),
                ],
            ),
            SSABlock(
                "other",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=other, immediate=13),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock("exit", instructions=[SSAInstruction(IROpcode.RETURN, operands=(direct,))]),
            SSABlock(
                "join",
                phis=[
                    SSAPhiNode(
                        target=merged,
                        original_register=3,
                        operands={"entry": direct, "other": other},
                    )
                ],
                instructions=[SSAInstruction(IROpcode.RETURN, operands=(merged,))],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    ir_fn = to_ir(ssa_fn)
    verify_ir(IRModule((ir_fn,)))
    assert any("ssa_edge_entry_to_join" in block.name for block in ir_fn.blocks)
    assert Emulator().execute(generate_assembly(IRModule((ir_fn,)))) == 13


def test_de_ssa_verifies_unreachable_phi_block() -> None:
    live = _value("live", 0)
    dead_source = _value("dead_source", 1, block="dead_pred")
    dead_phi = _value("dead_phi", 2, block="dead_join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(live, dead_source, dead_phi),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=live, immediate=1),
                    SSAInstruction(IROpcode.RETURN, operands=(live,)),
                ],
            ),
            SSABlock(
                "dead_pred",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=dead_source, immediate=5),
                    SSAInstruction(IROpcode.JUMP, targets=("dead_join",)),
                ],
            ),
            SSABlock(
                "dead_join",
                phis=[
                    SSAPhiNode(
                        target=dead_phi,
                        original_register=2,
                        operands={"dead_pred": dead_source},
                    )
                ],
                instructions=[SSAInstruction(IROpcode.RETURN, operands=(dead_phi,))],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    assert _execute(ssa_fn) == 1


def test_de_ssa_lowers_parameter_phi_operand_on_split_edge() -> None:
    param = _value("param", 0, IRType.TRIT)
    other = _value("other", 1, IRType.TRIT, block="other")
    merged = _value("merged", 2, IRType.TRIT, block="join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(SSAParameter(param),),
        values=(param, other, merged),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(param,),
                        targets=("join", "other", "exit"),
                    )
                ],
            ),
            SSABlock(
                "other",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=other, immediate=0),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock("exit", instructions=[SSAInstruction(IROpcode.RETURN, operands=(param,))]),
            SSABlock(
                "join",
                phis=[
                    SSAPhiNode(
                        target=merged,
                        original_register=2,
                        operands={"entry": param, "other": other},
                    )
                ],
                instructions=[SSAInstruction(IROpcode.RETURN, operands=(merged,))],
            ),
        ),
        return_type=IRType.TRIT,
    )

    ir_fn = to_ir(ssa_fn)

    verify_ir(IRModule((ir_fn,)))
    assert any("ssa_edge_entry_to_join" in block.name for block in ir_fn.blocks)


def test_de_ssa_preserves_trit_return_type_and_entry_block() -> None:
    param = _value("param", 0, IRType.TRIT)
    left = _value("left", 1, IRType.TRIT, block="left")
    right = _value("right", 2, IRType.TRIT, block="right")
    merged = _value("merged", 3, IRType.TRIT, block="join")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(SSAParameter(param),),
        values=(param, left, right, merged),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(param,),
                        targets=("left", "neutral", "right"),
                    ),
                ],
            ),
            SSABlock(
                "left",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=left, immediate=-1),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock("neutral", instructions=[SSAInstruction(IROpcode.JUMP, targets=("right",))]),
            SSABlock(
                "right",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=right, immediate=1),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "join",
                phis=[
                    SSAPhiNode(
                        target=merged,
                        original_register=3,
                        operands={"left": left, "right": right},
                    )
                ],
                instructions=[SSAInstruction(IROpcode.RETURN, operands=(merged,))],
            ),
        ),
        return_type=IRType.TRIT,
    )

    ir_fn = to_ir(ssa_fn)

    verify_ir(IRModule((ir_fn,)))
    assert ir_fn.return_type is IRType.TRIT
    assert ir_fn.blocks[0].name == "entry"


def test_de_ssa_public_o0_o1_equivalence_for_phi_heavy_control_flow() -> None:
    source = (
        "fn choose(value: tryte) -> tryte:\n"
        "    mut result: tryte = 0\n"
        "    match value <=> 0:\n"
        "        -1:\n"
        "            result = 3\n"
        "        0:\n"
        "            result = 5\n"
        "        else:\n"
        "            result = 7\n"
        "    return result\n"
        "fn main() -> tryte:\n"
        "    return choose(1)\n"
    )

    assert run_source(source, optimization="O0", mode=SyntaxMode.V0_6) == 7
    assert run_source(source, optimization="O1", mode=SyntaxMode.V0_6) == 7
