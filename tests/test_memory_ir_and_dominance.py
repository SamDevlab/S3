from __future__ import annotations

import pytest

from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRMemoryObject,
    IRModule,
    IROpcode,
    IRParameter,
    IRRegister,
    IRType,
)
from bootstrap.s3.verifier import IRVerificationError, verify_ir


def memory_function(
    *,
    memory: tuple[IRMemoryObject, ...] = (
        IRMemoryObject(0, IRType.TRYTE, 1, True),
    ),
    registers: tuple[IRRegister, ...] = (
        IRRegister(0, IRType.TRYTE),
        IRRegister(1, IRType.TRYTE),
        IRRegister(2, IRType.TRYTE),
    ),
    instructions: tuple[IRInstruction, ...] = (
        IRInstruction(IROpcode.CONST, result=0, immediate=0),
        IRInstruction(IROpcode.CONST, result=1, immediate=5),
        IRInstruction(IROpcode.STORE, operands=(0, 1), memory=0),
        IRInstruction(IROpcode.LOAD, result=2, operands=(0,), memory=0),
        IRInstruction(IROpcode.RETURN, operands=(2,)),
    ),
) -> IRFunction:
    return IRFunction(
        "main",
        (),
        IRType.TRYTE,
        registers,
        (IRBasicBlock("entry", instructions),),
        memory_objects=memory,
    )


def test_valid_memory_object_load_store_and_debug_serialization() -> None:
    module = IRModule((memory_function(),))
    verify_ir(module)
    payload = module.to_dict()
    function = payload["module"]["functions"][0]  # type: ignore[index]
    assert function["memory_objects"][0] == {  # type: ignore[index]
        "name": "m0",
        "index": 0,
        "element_type": "tryte",
        "length": 1,
        "mutable": True,
    }
    opcodes = [
        item["opcode"]
        for item in function["blocks"][0]["instructions"]  # type: ignore[index]
    ]
    assert opcodes == ["const", "const", "store", "load", "return"]


def test_duplicate_and_invalid_memory_objects_are_rejected() -> None:
    duplicate = IRMemoryObject(0, IRType.TRYTE, 2, True)
    with pytest.raises(IRVerificationError, match="duplicate memory object m0"):
        verify_ir(
            IRModule(
                (
                    memory_function(
                        memory=(
                            IRMemoryObject(0, IRType.TRYTE, 1, True),
                            duplicate,
                        )
                    ),
                )
            )
        )
    with pytest.raises(IRVerificationError, match="invalid length 0"):
        verify_ir(
            IRModule(
                (
                    memory_function(
                        memory=(IRMemoryObject(0, IRType.TRYTE, 0, True),)
                    ),
                )
            )
        )
    invalid = IRMemoryObject(0, "array", 1, True)  # type: ignore[arg-type]
    with pytest.raises(IRVerificationError, match="invalid element type"):
        verify_ir(IRModule((memory_function(memory=(invalid,)),)))
    with pytest.raises(IRVerificationError, match="indexable maximum 365"):
        verify_ir(
            IRModule(
                (
                    memory_function(
                        memory=(IRMemoryObject(0, IRType.TRIT, 366, True),)
                    ),
                )
            )
        )


def test_memory_reference_and_index_type_are_verified() -> None:
    missing = list(memory_function().blocks[0].instructions)
    missing[2] = IRInstruction(IROpcode.STORE, operands=(0, 1), memory=99)
    with pytest.raises(IRVerificationError, match="nonexistent memory object m99"):
        verify_ir(
            IRModule((memory_function(instructions=tuple(missing)),))
        )

    wrong_index_registers = (
        IRRegister(0, IRType.TRIT),
        IRRegister(1, IRType.TRYTE),
        IRRegister(2, IRType.TRYTE),
    )
    with pytest.raises(IRVerificationError, match="store index must have type tryte"):
        verify_ir(
            IRModule(
                (
                    memory_function(registers=wrong_index_registers),
                )
            )
        )


def test_load_result_and_store_value_types_are_verified() -> None:
    wrong_load_registers = (
        IRRegister(0, IRType.TRYTE),
        IRRegister(1, IRType.TRYTE),
        IRRegister(2, IRType.TRIT),
    )
    with pytest.raises(IRVerificationError, match="load result has type trit"):
        verify_ir(IRModule((memory_function(registers=wrong_load_registers),)))

    wrong_store_registers = (
        IRRegister(0, IRType.TRYTE),
        IRRegister(1, IRType.TRIT),
        IRRegister(2, IRType.TRYTE),
    )
    wrong_store_instructions = list(memory_function().blocks[0].instructions)
    wrong_store_instructions[1] = IRInstruction(
        IROpcode.CONST,
        result=1,
        immediate=1,
    )
    with pytest.raises(IRVerificationError, match="store value has type trit"):
        verify_ir(
            IRModule(
                (
                    memory_function(
                        registers=wrong_store_registers,
                        instructions=tuple(wrong_store_instructions),
                    ),
                )
            )
        )


def test_immutable_memory_only_accepts_initializing_store() -> None:
    immutable = (IRMemoryObject(0, IRType.TRYTE, 1, False),)
    with pytest.raises(IRVerificationError, match="is not initialization"):
        verify_ir(IRModule((memory_function(memory=immutable),)))

    instructions = list(memory_function().blocks[0].instructions)
    instructions[2] = IRInstruction(
        IROpcode.STORE,
        operands=(0, 1),
        memory=0,
        initialization=True,
    )
    verify_ir(
        IRModule(
            (
                memory_function(
                    memory=immutable,
                    instructions=tuple(instructions),
                ),
            )
        )
    )


def test_same_block_definition_must_precede_use() -> None:
    function = IRFunction(
        "main",
        (),
        IRType.TRYTE,
        (
            IRRegister(0, IRType.TRYTE),
            IRRegister(1, IRType.TRYTE),
        ),
        (
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.MOVE, result=1, operands=(0,)),
                    IRInstruction(IROpcode.CONST, result=0, immediate=1),
                    IRInstruction(IROpcode.RETURN, operands=(1,)),
                ),
            ),
        ),
    )
    with pytest.raises(IRVerificationError, match="does not precede its use"):
        verify_ir(IRModule((function,)))


def branching_function(*, use_branch_value_at_join: bool) -> IRFunction:
    registers = (
        IRRegister(0, IRType.TRIT),
        IRRegister(1, IRType.TRYTE),
        IRRegister(2, IRType.TRYTE),
    )
    entry = IRBasicBlock(
        "entry",
        (
            IRInstruction(IROpcode.CONST, result=0, immediate=0),
            IRInstruction(IROpcode.CONST, result=1, immediate=7),
            IRInstruction(
                IROpcode.BRANCH3,
                operands=(0,),
                targets=("negative", "neutral", "positive"),
            ),
        ),
    )
    negative = IRBasicBlock(
        "negative",
        (
            IRInstruction(IROpcode.CONST, result=2, immediate=1),
            IRInstruction(IROpcode.JUMP, targets=("join",)),
        ),
    )
    neutral = IRBasicBlock(
        "neutral",
        (IRInstruction(IROpcode.JUMP, targets=("join",)),),
    )
    positive = IRBasicBlock(
        "positive",
        (IRInstruction(IROpcode.JUMP, targets=("join",)),),
    )
    returned = 2 if use_branch_value_at_join else 1
    join = IRBasicBlock(
        "join",
        (IRInstruction(IROpcode.RETURN, operands=(returned,)),),
    )
    return IRFunction(
        "main",
        (),
        IRType.TRYTE,
        registers,
        (entry, negative, neutral, positive, join),
    )


def test_entry_definition_dominates_successors_and_join() -> None:
    verify_ir(IRModule((branching_function(use_branch_value_at_join=False),)))


def test_branch_definition_does_not_dominate_join() -> None:
    with pytest.raises(IRVerificationError, match="does not dominate block 'join'"):
        verify_ir(IRModule((branching_function(use_branch_value_at_join=True),)))


def test_branch_definition_can_be_used_inside_its_branch() -> None:
    function = branching_function(use_branch_value_at_join=False)
    blocks = list(function.blocks)
    blocks[1] = IRBasicBlock(
        "negative",
        (
            IRInstruction(IROpcode.CONST, result=2, immediate=1),
            IRInstruction(IROpcode.RETURN, operands=(2,)),
        ),
    )
    verify_ir(
        IRModule(
            (
                IRFunction(
                    function.name,
                    function.parameters,
                    function.return_type,
                    function.registers,
                    tuple(blocks),
                ),
            )
        )
    )


def test_parameter_dominates_every_reachable_block() -> None:
    parameter = IRParameter("value", 0, IRType.TRYTE)
    function = IRFunction(
        "identity",
        (parameter,),
        IRType.TRYTE,
        (IRRegister(0, IRType.TRYTE),),
        (
            IRBasicBlock(
                "entry",
                (IRInstruction(IROpcode.JUMP, targets=("result",)),),
            ),
            IRBasicBlock(
                "result",
                (IRInstruction(IROpcode.RETURN, operands=(0,)),),
            ),
        ),
    )
    verify_ir(IRModule((function,)))


def test_cfg_cycle_is_valid_for_dominance() -> None:
    function = IRFunction(
        "main",
        (),
        IRType.TRYTE,
        (),
        (
            IRBasicBlock(
                "entry",
                (IRInstruction(IROpcode.JUMP, targets=("loop",)),),
            ),
            IRBasicBlock(
                "loop",
                (IRInstruction(IROpcode.JUMP, targets=("loop",)),),
            ),
        ),
    )
    verify_ir(IRModule((function,)))


def test_unreachable_block_still_requires_valid_structure() -> None:
    function = IRFunction(
        "main",
        (),
        IRType.TRYTE,
        (),
        (
            IRBasicBlock(
                "entry",
                (IRInstruction(IROpcode.JUMP, targets=("entry",)),),
            ),
            IRBasicBlock("unreachable", ()),
        ),
    )
    with pytest.raises(IRVerificationError, match="has no terminator"):
        verify_ir(IRModule((function,)))


def test_pointer_opcode_is_rejected() -> None:
    pointer = IRInstruction("ptr_add")  # type: ignore[arg-type]
    function = IRFunction(
        "main",
        (),
        IRType.TRYTE,
        (),
        (
            IRBasicBlock(
                "entry",
                (
                    pointer,
                    IRInstruction(IROpcode.JUMP, targets=("entry",)),
                ),
            ),
        ),
    )
    with pytest.raises(IRVerificationError, match="pointer/address opcodes"):
        verify_ir(IRModule((function,)))
