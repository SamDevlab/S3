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


def test_sysv_numeric_return_registers_are_distinct() -> None:
    assert return_register(NumericType.I64) == SYSV_INTEGER_RETURN_REGISTER == "rax"
    assert return_register(NumericType.F64) == SYSV_FLOAT_RETURN_REGISTER == "xmm0"
    assert SYSV_FLOAT_ARGUMENT_REGISTERS[0] == "xmm0"


def test_numeric_abi_value_rejects_wrong_return_class() -> None:
    assert NumericABIValue(NumericType.F64, "xmm0").register == "xmm0"
    with pytest.raises(ValueError):
        NumericABIValue(NumericType.F64, "rax")
