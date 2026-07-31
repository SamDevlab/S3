from __future__ import annotations

from bootstrap.s3.ir import IROpcode, IRMemoryObject, IRType
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABlock, SSAFunction, SSAInstruction, SSAValue, SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_dse


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


def _store_count(ssa_fn: SSAFunction) -> int:
    return sum(
        1
        for block in ssa_fn.blocks
        for inst in block.instructions
        if inst.opcode is IROpcode.STORE
    )


def test_dse_eliminates_overwritten_stores() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    x = 20\n"
        "    return x\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, removed = run_ssa_dse(ssa_fn)

    assert removed >= 1
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 20


def test_dse_preserves_stores_before_load() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 15\n"
        "    mut y: tryte = x + 5\n"
        "    x = 30\n"
        "    return y + x\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 50


def test_dse_removes_same_constant_cell_store_in_same_block() -> None:
    idx = _value("idx", 0)
    first_value = _value("first_value", 1)
    second_value = _value("second_value", 2)
    loaded = _value("loaded", 3)
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(idx, first_value, second_value, loaded),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, True),),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=idx, immediate=0),
                    SSAInstruction(IROpcode.CONST, result=first_value, immediate=1),
                    SSAInstruction(IROpcode.STORE, operands=(idx, first_value), memory=0),
                    SSAInstruction(IROpcode.CONST, result=second_value, immediate=2),
                    SSAInstruction(IROpcode.STORE, operands=(idx, second_value), memory=0),
                    SSAInstruction(IROpcode.LOAD, result=loaded, operands=(idx,), memory=0),
                    SSAInstruction(IROpcode.RETURN, operands=(loaded,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, removed = run_ssa_dse(ssa_fn)

    assert removed == 1
    assert _store_count(optimized) == _store_count(ssa_fn) - 1
    assert ssa_fn.blocks[0].instructions[2] not in optimized.blocks[0].instructions


def test_dse_preserves_different_constant_cells() -> None:
    idx0 = _value("idx0", 0)
    idx1 = _value("idx1", 1)
    first_value = _value("first_value", 2)
    second_value = _value("second_value", 3)
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(idx0, idx1, first_value, second_value),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 2, True),),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=idx0, immediate=0),
                    SSAInstruction(IROpcode.CONST, result=idx1, immediate=1),
                    SSAInstruction(IROpcode.CONST, result=first_value, immediate=1),
                    SSAInstruction(IROpcode.CONST, result=second_value, immediate=2),
                    SSAInstruction(IROpcode.STORE, operands=(idx0, first_value), memory=0),
                    SSAInstruction(IROpcode.STORE, operands=(idx1, second_value), memory=0),
                    SSAInstruction(IROpcode.RETURN, operands=(second_value,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, removed = run_ssa_dse(ssa_fn)

    assert removed == 0
    assert optimized.blocks == ssa_fn.blocks


def test_dse_preserves_different_dynamic_index_versions() -> None:
    idx_v0 = _value("idx_v0", 0)
    idx_v1 = _value("idx_v1", 0)
    first_value = _value("first_value", 1)
    second_value = _value("second_value", 2)
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(idx_v0, idx_v1, first_value, second_value),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 3, True),),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=first_value, immediate=5),
                    SSAInstruction(IROpcode.STORE, operands=(idx_v0, first_value), memory=0),
                    SSAInstruction(IROpcode.CONST, result=second_value, immediate=7),
                    SSAInstruction(IROpcode.STORE, operands=(idx_v1, second_value), memory=0),
                    SSAInstruction(IROpcode.RETURN, operands=(second_value,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, removed = run_ssa_dse(ssa_fn)

    assert removed == 0
    assert optimized.blocks == ssa_fn.blocks


def test_dse_preserves_store_observed_by_load() -> None:
    idx = _value("idx", 0)
    first_value = _value("first_value", 1)
    observed = _value("observed", 2)
    second_value = _value("second_value", 3)
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(idx, first_value, observed, second_value),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, True),),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=idx, immediate=0),
                    SSAInstruction(IROpcode.CONST, result=first_value, immediate=5),
                    SSAInstruction(IROpcode.STORE, operands=(idx, first_value), memory=0),
                    SSAInstruction(IROpcode.LOAD, result=observed, operands=(idx,), memory=0),
                    SSAInstruction(IROpcode.CONST, result=second_value, immediate=7),
                    SSAInstruction(IROpcode.STORE, operands=(idx, second_value), memory=0),
                    SSAInstruction(IROpcode.RETURN, operands=(observed,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, removed = run_ssa_dse(ssa_fn)

    assert removed == 0
    assert optimized.blocks == ssa_fn.blocks


def test_dse_preserves_store_across_unknown_call() -> None:
    idx = _value("idx", 0)
    first_value = _value("first_value", 1)
    call_result = _value("call_result", 2)
    second_value = _value("second_value", 3)
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(idx, first_value, call_result, second_value),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, True),),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=idx, immediate=0),
                    SSAInstruction(IROpcode.CONST, result=first_value, immediate=5),
                    SSAInstruction(IROpcode.STORE, operands=(idx, first_value), memory=0),
                    SSAInstruction(IROpcode.CALL, result=call_result, immediate="observer"),
                    SSAInstruction(IROpcode.CONST, result=second_value, immediate=7),
                    SSAInstruction(IROpcode.STORE, operands=(idx, second_value), memory=0),
                    SSAInstruction(IROpcode.RETURN, operands=(second_value,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, removed = run_ssa_dse(ssa_fn)

    assert removed == 0
    assert optimized.blocks == ssa_fn.blocks


def test_dse_preserves_stores_in_sibling_branches() -> None:
    idx = _value("idx", 0)
    condition = _value("condition", 1, IRType.TRIT)
    left_value = _value("left_value", 2, block="left")
    right_value = _value("right_value", 3, block="right")
    ssa_fn = SSAFunction(
        name="main",
        parameters=(),
        values=(idx, condition, left_value, right_value),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, True),),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=idx, immediate=0),
                    SSAInstruction(IROpcode.CONST, result=condition, immediate=1),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(condition,),
                        targets=("left", "neutral", "right"),
                    ),
                ],
            ),
            SSABlock(
                "left",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=left_value, immediate=5),
                    SSAInstruction(IROpcode.STORE, operands=(idx, left_value), memory=0),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock("neutral", instructions=[SSAInstruction(IROpcode.JUMP, targets=("join",))]),
            SSABlock(
                "right",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=right_value, immediate=7),
                    SSAInstruction(IROpcode.STORE, operands=(idx, right_value), memory=0),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock("join", instructions=[SSAInstruction(IROpcode.RETURN, operands=(idx,))]),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, removed = run_ssa_dse(ssa_fn)

    assert removed == 0
    assert optimized.blocks == ssa_fn.blocks


def test_dse_public_o0_o1_equivalence_for_dynamic_index_versions() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut values: tryte[3] = [0, 0, 0]\n"
        "    mut i: tryte = 0\n"
        "    values[i] = 5\n"
        "    i = 1\n"
        "    values[i] = 7\n"
        "    return values[0]\n"
    )

    assert run_source(source, optimization="O0", mode=SyntaxMode.V0_6) == 5
    assert run_source(source, optimization="O1", mode=SyntaxMode.V0_6) == 5
