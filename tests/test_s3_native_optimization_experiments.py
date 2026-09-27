from __future__ import annotations

from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRMemoryObject,
    IRModule,
    IROpcode,
    IRRegister,
    IRType,
)
from bootstrap.s3.initialization import analyze_initialization
from bootstrap.s3.verifier import verify_ir
from tools.s3_native_optimization_experiments import forward_repeated_mutable_loads


def _function(*, barrier: IROpcode | None = None, distinct_index: bool = False,
              block_boundary: bool = False, mutable: bool = True,
              pure_between: bool = False, reassign_index: bool = False,
              overwrite_cached_result: bool = False) -> IRFunction:
    registers = (
        IRRegister(0, IRType.I64),
        IRRegister(1, IRType.TRYTE),
        IRRegister(2, IRType.TRYTE),
        IRRegister(3, IRType.TRYTE),
        *((IRRegister(4, IRType.TRYTE),) if distinct_index or pure_between else ()),
    )
    setup = [
        IRInstruction(IROpcode.CONST, result=0, immediate=0),
        IRInstruction(IROpcode.CONST, result=1, immediate=1),
        IRInstruction(IROpcode.STORE, operands=(0, 1), memory=0, initialization=True),
        IRInstruction(IROpcode.LOAD, result=2, operands=(0,), memory=0),
    ]
    if distinct_index:
        setup.extend((
            IRInstruction(IROpcode.CONST, result=4, immediate=1),
            IRInstruction(IROpcode.LOAD, result=3, operands=(4,), memory=0),
        ))
    elif block_boundary:
        setup.append(IRInstruction(IROpcode.JUMP, targets=("next",)))
    else:
        if pure_between:
            setup.append(IRInstruction(IROpcode.MOVE, result=4, operands=(1,)))
        if reassign_index:
            setup.append(IRInstruction(IROpcode.CONST, result=0, immediate=0))
        if overwrite_cached_result:
            setup.append(IRInstruction(IROpcode.CONST, result=2, immediate=1))
        if barrier is IROpcode.STORE:
            setup.append(IRInstruction(IROpcode.STORE, operands=(0, 1), memory=0))
        elif barrier is IROpcode.CALL:
            setup.append(IRInstruction(IROpcode.CALL, callee="mutate"))
        setup.append(IRInstruction(IROpcode.LOAD, result=3, operands=(0,), memory=0))

    blocks = [IRBasicBlock("entry", tuple(setup))]
    if block_boundary:
        blocks.append(IRBasicBlock("next", (
            IRInstruction(IROpcode.LOAD, result=3, operands=(0,), memory=0),
            IRInstruction(IROpcode.RETURN, operands=(3,)),
        )))
    elif not (setup[-1].opcode is IROpcode.JUMP):
        blocks[0] = IRBasicBlock("entry", tuple(setup + [IRInstruction(IROpcode.RETURN, operands=(3,))]))
    memory = IRMemoryObject(0, IRType.TRYTE, 2, mutable)
    return IRFunction(
        "read_cell", (), IRType.TRYTE, registers, tuple(blocks),
        memory_objects=(memory,),
    )


def test_candidate_forwards_exact_same_mutable_cell_load_in_one_block() -> None:
    candidate, forwarded = forward_repeated_mutable_loads(_function())

    assert forwarded == 1
    ops = [instruction.opcode for block in candidate.blocks for instruction in block.instructions]
    assert ops.count(IROpcode.LOAD) == 1
    assert ops.count(IROpcode.MOVE) == 1
    module = IRModule((candidate,))
    verify_ir(module)
    analyze_initialization(module)


def test_candidate_can_forward_across_pure_op_when_register_versions_are_stable() -> None:
    candidate, forwarded = forward_repeated_mutable_loads(_function(pure_between=True))

    assert forwarded == 1
    ops = [instruction.opcode for block in candidate.blocks for instruction in block.instructions]
    assert ops.count(IROpcode.LOAD) == 1
    verify_ir(IRModule((candidate,)))


def test_candidate_does_not_forward_across_store_or_call() -> None:
    for barrier in (IROpcode.STORE, IROpcode.CALL):
        candidate, forwarded = forward_repeated_mutable_loads(
            _function(barrier=barrier)
        )
        assert forwarded == 0
        assert sum(instruction.opcode is IROpcode.LOAD
                   for block in candidate.blocks for instruction in block.instructions) == 2


def test_candidate_does_not_forward_different_indices_or_across_blocks() -> None:
    for function in (_function(distinct_index=True), _function(block_boundary=True)):
        candidate, forwarded = forward_repeated_mutable_loads(function)
        assert forwarded == 0


def test_candidate_does_not_forward_after_index_or_cached_value_redefinition() -> None:
    for function in (
        _function(reassign_index=True),
        _function(overwrite_cached_result=True),
    ):
        candidate, forwarded = forward_repeated_mutable_loads(function)
        assert forwarded == 0


def test_candidate_does_not_forward_immutable_memory_loads() -> None:
    candidate, forwarded = forward_repeated_mutable_loads(_function(mutable=False))

    assert forwarded == 0
    assert sum(instruction.opcode is IROpcode.LOAD
               for block in candidate.blocks for instruction in block.instructions) == 2
