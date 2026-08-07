from __future__ import annotations

from bootstrap.s3.ir import IRMemoryObject, IROpcode, IRType
from bootstrap.s3.ssa import SSABlock, SSAFunction, SSAInstruction, SSAValue
from bootstrap.s3.ssa_opt import run_ssa_global_dse


def _value(name: str, register: int, block: str = "entry") -> SSAValue:
    return SSAValue(name, original_register=register, def_block=block)


def _store_only_function() -> SSAFunction:
    index = _value("index", 0)
    value = _value("value", 1, "write")
    return SSAFunction(
        name="main",
        parameters=(),
        values=(index, value),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, True),),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=index, immediate=0),
                    SSAInstruction(IROpcode.JUMP, targets=("write",)),
                ],
            ),
            SSABlock(
                "write",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=value, immediate=7),
                    SSAInstruction(IROpcode.STORE, operands=(index, value), memory=0),
                    SSAInstruction(IROpcode.RETURN, operands=(value,)),
                ],
            ),
        ),
        return_type=IRType.TRYTE,
    )


def test_global_dse_removes_store_across_blocks_without_load() -> None:
    function = _store_only_function()

    optimized, removed = run_ssa_global_dse(function)

    assert removed == 1
    assert all(
        instruction.opcode is not IROpcode.STORE
        for block in optimized.blocks
        for instruction in block.instructions
    )


def test_global_dse_preserves_object_with_any_load() -> None:
    function = _store_only_function()
    index = function.values[0]
    loaded = _value("loaded", 2, "write")
    block = function.blocks[1]
    with_load = SSAFunction(
        name=function.name,
        parameters=function.parameters,
        values=function.values + (loaded,),
        memory_objects=function.memory_objects,
        blocks=(
            function.blocks[0],
            SSABlock(
                block.name,
                instructions=block.instructions[:-1]
                + [
                    SSAInstruction(IROpcode.LOAD, result=loaded, operands=(index,), memory=0),
                    block.instructions[-1],
                ],
            ),
        ),
        return_type=function.return_type,
    )

    optimized, removed = run_ssa_global_dse(with_load)

    assert removed == 0
    assert optimized.blocks == with_load.blocks
