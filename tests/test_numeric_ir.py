from __future__ import annotations

import pytest

from bootstrap.s3.numeric import NumericError, NumericType, NumericValue
from bootstrap.s3.numeric_ir import (
    NumericIRFunction,
    NumericIRInstruction,
    NumericIROpcode,
    evaluate_numeric_ir,
)
from bootstrap.s3.numeric_emulator import NumericEmulator
from bootstrap.s3.ir import IRBasicBlock, IRFunction, IRInstruction, IRModule, IRRegister, IROpcode, IRType
from bootstrap.s3.ir_emulator import execute_ir


def test_numeric_ir_evaluates_i64_constant_and_addition() -> None:
    result = evaluate_numeric_ir(
        NumericIRFunction(
            (
                NumericIRInstruction(NumericIROpcode.CONST, 0, value=NumericValue.i64(2)),
                NumericIRInstruction(NumericIROpcode.CONST, 1, value=NumericValue.i64(3)),
                NumericIRInstruction(NumericIROpcode.ADD, 2, (0, 1)),
                NumericIRInstruction(NumericIROpcode.RETURN, operands=(2,)),
            ),
            NumericType.I64,
        )
    )
    assert result == NumericValue.i64(5)


def test_numeric_emulator_uses_the_canonical_numeric_evaluator() -> None:
    function = NumericIRFunction(
        (
            NumericIRInstruction(NumericIROpcode.CONST, 0, value=NumericValue.i64(7)),
            NumericIRInstruction(NumericIROpcode.RETURN, operands=(0,)),
        ),
        NumericType.I64,
    )
    assert NumericEmulator().execute(function) == NumericValue.i64(7)


def test_numeric_ir_evaluates_f64_without_coercing_to_i64() -> None:
    result = evaluate_numeric_ir(
        NumericIRFunction(
            (
                NumericIRInstruction(NumericIROpcode.CONST, 0, value=NumericValue.f64(0.5)),
                NumericIRInstruction(NumericIROpcode.CONST, 1, value=NumericValue.f64(0.25)),
                NumericIRInstruction(NumericIROpcode.ADD, 2, (0, 1)),
                NumericIRInstruction(NumericIROpcode.RETURN, operands=(2,)),
            ),
            NumericType.F64,
        )
    )
    assert result == NumericValue.f64(0.75)


def test_numeric_ir_rejects_mixed_domain_addition() -> None:
    with pytest.raises(NumericError):
        evaluate_numeric_ir(
            NumericIRFunction(
                (
                    NumericIRInstruction(NumericIROpcode.CONST, 0, value=NumericValue.i64(1)),
                    NumericIRInstruction(NumericIROpcode.CONST, 1, value=NumericValue.f64(1.0)),
                    NumericIRInstruction(NumericIROpcode.ADD, 2, (0, 1)),
                ),
                NumericType.I64,
            )
        )


def test_numeric_ir_rejects_invalid_return_type_contract() -> None:
    with pytest.raises(ValueError, match="return type"):
        evaluate_numeric_ir(
            NumericIRFunction(
                (
                    NumericIRInstruction(
                        NumericIROpcode.CONST,
                        0,
                        value=NumericValue.i64(1),
                    ),
                    NumericIRInstruction(NumericIROpcode.RETURN, operands=(0,)),
                ),
                NumericType.F64,
            )
        )


def test_main_ir_emulator_executes_numeric_i64_addition() -> None:
    function = IRFunction(
        "main",
        (),
        IRType.I64,
        registers=(IRRegister(0, IRType.I64), IRRegister(1, IRType.I64), IRRegister(2, IRType.I64)),
        blocks=(IRBasicBlock("entry", (
            IRInstruction(IROpcode.CONST, result=0, immediate=2),
            IRInstruction(IROpcode.CONST, result=1, immediate=3),
            IRInstruction(IROpcode.ADD, result=2, operands=(0, 1)),
            IRInstruction(IROpcode.RETURN, operands=(2,)),
        )),),
    )
    assert execute_ir(IRModule((function,))) == 5


def test_main_ir_emulator_executes_numeric_f64_addition() -> None:
    function = IRFunction(
        "main",
        (),
        IRType.F64,
        registers=(IRRegister(0, IRType.F64), IRRegister(1, IRType.F64), IRRegister(2, IRType.F64)),
        blocks=(IRBasicBlock("entry", (
            IRInstruction(IROpcode.CONST, result=0, immediate=0.5),
            IRInstruction(IROpcode.CONST, result=1, immediate=0.25),
            IRInstruction(IROpcode.ADD, result=2, operands=(0, 1)),
            IRInstruction(IROpcode.RETURN, operands=(2,)),
        )),),
    )
    assert execute_ir(IRModule((function,))) == 0.75
