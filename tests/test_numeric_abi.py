from __future__ import annotations

import pytest

from bootstrap.s3.numeric import NumericType
from bootstrap.s3.numeric_abi import (
    NumericABIValue,
    SYSV_FLOAT_ARGUMENT_REGISTERS,
    SYSV_FLOAT_RETURN_REGISTER,
    SYSV_INTEGER_RETURN_REGISTER,
    return_register,
)
from bootstrap.s3.numeric_native import lower_add, lower_return


def test_sysv_numeric_return_registers_are_distinct() -> None:
    assert return_register(NumericType.I64) == SYSV_INTEGER_RETURN_REGISTER == "rax"
    assert return_register(NumericType.F64) == SYSV_FLOAT_RETURN_REGISTER == "xmm0"
    assert SYSV_FLOAT_ARGUMENT_REGISTERS[0] == "xmm0"


def test_numeric_abi_value_rejects_wrong_return_class() -> None:
    assert NumericABIValue(NumericType.F64, "xmm0").register == "xmm0"
    with pytest.raises(ValueError):
        NumericABIValue(NumericType.F64, "rax")


def test_native_lowering_uses_integer_and_sse2_additions() -> None:
    assert lower_add(NumericType.I64, "%r8", "%r9").render() == "addq %r9, %r8"
    assert lower_add(NumericType.F64, "%xmm1", "%xmm0").render() == "addsd %xmm0, %xmm1"


def test_native_returns_use_sysv_register_classes() -> None:
    assert lower_return(NumericType.I64, "%r8").render() == "movq %r8, %rax"
    assert lower_return(NumericType.F64, "%xmm1").render() == "movsd %xmm1, %xmm0"
