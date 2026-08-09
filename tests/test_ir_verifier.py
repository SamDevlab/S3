from __future__ import annotations

import pytest

from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRParameter,
    IRRegister,
    IRType,
)
from bootstrap.s3.verifier import IRVerificationError, verify_ir

pytestmark = [pytest.mark.s3_fast, pytest.mark.s3_contract]


def function(
    *,
    name: str = "main",
    parameters: tuple[IRParameter, ...] = (),
    return_type: IRType = IRType.TRYTE,
    registers: tuple[IRRegister, ...] = (IRRegister(0, IRType.TRYTE),),
    blocks: tuple[IRBasicBlock, ...] = (
        IRBasicBlock(
            "entry",
            (
                IRInstruction(IROpcode.CONST, result=0, immediate=0),
                IRInstruction(IROpcode.RETURN, operands=(0,)),
            ),
        ),
    ),
) -> IRFunction:
    return IRFunction(name, parameters, return_type, registers, blocks)


def test_valid_block_ir_verifies() -> None:
    verify_ir(IRModule((function(),)))


def test_function_without_entry_is_rejected() -> None:
    module = IRModule(
        (
            function(
                blocks=(
                    IRBasicBlock(
                        "other",
                        (IRInstruction(IROpcode.RETURN, operands=(0,)),),
                    ),
                ),
                parameters=(IRParameter("value", 0, IRType.TRYTE),),
            ),
        )
    )
    with pytest.raises(IRVerificationError, match="has no entry block"):
        verify_ir(module)


def test_duplicate_block_is_rejected() -> None:
    block = IRBasicBlock(
        "entry",
        (
            IRInstruction(IROpcode.CONST, result=0, immediate=0),
            IRInstruction(IROpcode.RETURN, operands=(0,)),
        ),
    )
    with pytest.raises(IRVerificationError, match="duplicate block 'entry'"):
        verify_ir(IRModule((function(blocks=(block, block)),)))


def test_missing_terminator_is_rejected() -> None:
    block = IRBasicBlock(
        "entry",
        (IRInstruction(IROpcode.CONST, result=0, immediate=0),),
    )
    with pytest.raises(IRVerificationError, match="has no terminator"):
        verify_ir(IRModule((function(blocks=(block,)),)))


def test_codegen_refuses_unverified_ir() -> None:
    block = IRBasicBlock(
        "entry",
        (IRInstruction(IROpcode.CONST, result=0, immediate=0),),
    )
    with pytest.raises(IRVerificationError, match="has no terminator"):
        generate_assembly(IRModule((function(blocks=(block,)),)))


def test_instruction_after_terminator_is_rejected() -> None:
    block = IRBasicBlock(
        "entry",
        (
            IRInstruction(IROpcode.RETURN, operands=(0,)),
            IRInstruction(IROpcode.CONST, result=0, immediate=0),
        ),
    )
    with pytest.raises(IRVerificationError, match="after its terminator"):
        verify_ir(IRModule((function(blocks=(block,)),)))


def test_jump_to_missing_block_is_rejected() -> None:
    block = IRBasicBlock(
        "entry",
        (IRInstruction(IROpcode.JUMP, targets=("missing",)),),
    )
    with pytest.raises(IRVerificationError, match="nonexistent block 'missing'"):
        verify_ir(IRModule((function(registers=(), blocks=(block,)),)))


def test_branch3_requires_trit_condition_and_distinct_targets() -> None:
    targets = tuple(
        IRBasicBlock(
            name,
            (IRInstruction(IROpcode.RETURN, operands=(0,)),),
        )
        for name in ("negative", "neutral", "positive")
    )
    entry = IRBasicBlock(
        "entry",
        (IRInstruction(IROpcode.BRANCH3, operands=(0,), targets=(
            "negative",
            "neutral",
            "positive",
        )),),
    )
    with pytest.raises(IRVerificationError, match="condition must be trit"):
        verify_ir(
            IRModule(
                (
                    function(
                        parameters=(IRParameter("value", 0, IRType.TRYTE),),
                        blocks=(entry, *targets),
                    ),
                )
            )
        )

    trit_register = IRRegister(0, IRType.TRIT)
    duplicate_entry = IRBasicBlock(
        "entry",
        (
            IRInstruction(
                IROpcode.BRANCH3,
                operands=(0,),
                targets=("negative", "negative", "positive"),
            ),
        ),
    )
    trit_targets = (
        IRBasicBlock(
            "negative",
            (IRInstruction(IROpcode.RETURN, operands=(0,)),),
        ),
        IRBasicBlock(
            "positive",
            (IRInstruction(IROpcode.RETURN, operands=(0,)),),
        ),
    )
    with pytest.raises(IRVerificationError, match="destinations must be distinct"):
        verify_ir(
            IRModule(
                (
                    function(
                        parameters=(IRParameter("value", 0, IRType.TRIT),),
                        return_type=IRType.TRIT,
                        registers=(trit_register,),
                        blocks=(duplicate_entry, *trit_targets),
                    ),
                )
            )
        )


def test_call_signature_is_verified() -> None:
    callee = function(
        name="callee",
        parameters=(IRParameter("value", 0, IRType.TRIT),),
        return_type=IRType.TRIT,
        registers=(IRRegister(0, IRType.TRIT),),
        blocks=(
            IRBasicBlock(
                "entry",
                (IRInstruction(IROpcode.RETURN, operands=(0,)),),
            ),
        ),
    )
    caller = function(
        registers=(
            IRRegister(0, IRType.TRYTE),
            IRRegister(1, IRType.TRIT),
        ),
        blocks=(
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.CONST, result=0, immediate=1),
                    IRInstruction(
                        IROpcode.CALL,
                        result=1,
                        operands=(0,),
                        callee="callee",
                    ),
                    IRInstruction(IROpcode.RETURN, operands=(0,)),
                ),
            ),
        ),
    )
    with pytest.raises(IRVerificationError, match="incompatible argument types"):
        verify_ir(IRModule((caller, callee)))


def test_wrong_return_type_is_rejected() -> None:
    bad = function(
        registers=(IRRegister(0, IRType.TRIT),),
        parameters=(IRParameter("value", 0, IRType.TRIT),),
        blocks=(
            IRBasicBlock(
                "entry",
                (IRInstruction(IROpcode.RETURN, operands=(0,)),),
            ),
        ),
    )
    with pytest.raises(IRVerificationError, match="return cell 0 has type trit"):
        verify_ir(IRModule((bad,)))


def test_nonexistent_value_is_rejected() -> None:
    bad = function(
        registers=(IRRegister(0, IRType.TRYTE),),
        blocks=(
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.MOVE, result=0, operands=(99,)),
                    IRInstruction(IROpcode.RETURN, operands=(0,)),
                ),
            ),
        ),
    )
    with pytest.raises(IRVerificationError, match="nonexistent value r99"):
        verify_ir(IRModule((bad,)))


def test_artificial_subtraction_opcode_is_rejected() -> None:
    bad_instruction = IRInstruction(  # type: ignore[arg-type]
        "subtract",
        result=1,
        operands=(0, 0),
    )
    bad = function(
        parameters=(IRParameter("value", 0, IRType.TRYTE),),
        registers=(
            IRRegister(0, IRType.TRYTE),
            IRRegister(1, IRType.TRYTE),
        ),
        blocks=(
            IRBasicBlock(
                "entry",
                (
                    bad_instruction,
                    IRInstruction(IROpcode.RETURN, operands=(0,)),
                ),
            ),
        ),
    )
    with pytest.raises(IRVerificationError, match="subtraction opcode is forbidden"):
        verify_ir(IRModule((bad,)))
