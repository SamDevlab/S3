from __future__ import annotations

from bootstrap.s3.ir import IRMemoryObject, IROpcode, IRType
from bootstrap.s3.ssa import SSABlock, SSAFunction, SSAInstruction, SSAValue
from bootstrap.s3.ssa_opt import run_ssa_gvn


def _value(name: str, register: int) -> SSAValue:
    return SSAValue(name, original_register=register, def_block="entry")


def _function(mutable: bool) -> SSAFunction:
    index = _value("index", 0)
    first = _value("first", 1)
    second = _value("second", 2)
    return SSAFunction(
        name="main",
        parameters=(),
        values=(index, first, second),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, mutable),),
        blocks=(SSABlock("entry", instructions=[
            SSAInstruction(IROpcode.CONST, result=index, immediate=0),
            SSAInstruction(IROpcode.LOAD, result=first, operands=(index,), memory=0),
            SSAInstruction(IROpcode.LOAD, result=second, operands=(index,), memory=0),
            SSAInstruction(IROpcode.RETURN, operands=(second,)),
        ]),),
        return_type=IRType.TRYTE,
    )


def test_gvn_reuses_repeated_load_from_immutable_memory() -> None:
    optimized, eliminated = run_ssa_gvn(_function(mutable=False))

    assert eliminated == 1
    assert sum(
        instruction.opcode is IROpcode.LOAD
        for block in optimized.blocks
        for instruction in block.instructions
    ) == 1


def test_gvn_keeps_repeated_load_from_mutable_memory() -> None:
    function = _function(mutable=True)

    optimized, eliminated = run_ssa_gvn(function)

    assert eliminated == 0
    assert optimized.blocks == function.blocks
