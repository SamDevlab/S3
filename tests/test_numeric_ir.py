from __future__ import annotations

import pytest

from bootstrap.s3.numeric import NumericError, NumericType, NumericValue
from bootstrap.s3.numeric_ir import (
    NumericIRFunction,
    NumericIRInstruction,
    NumericIROpcode,
    evaluate_numeric_ir,
)


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
