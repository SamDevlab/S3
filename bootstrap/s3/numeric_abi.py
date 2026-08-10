"""Internal System V AMD64 ABI facts for M1.32 numeric values."""

from __future__ import annotations

from dataclasses import dataclass

from .numeric import NumericType


SYSV_INTEGER_RETURN_REGISTER = "rax"
SYSV_FLOAT_RETURN_REGISTER = "xmm0"
SYSV_FLOAT_ARGUMENT_REGISTERS = (
    "xmm0",
    "xmm1",
    "xmm2",
    "xmm3",
    "xmm4",
    "xmm5",
    "xmm6",
    "xmm7",
)


@dataclass(frozen=True, slots=True)
class NumericABIValue:
    type: NumericType
    register: str

    def __post_init__(self) -> None:
        expected = (
            SYSV_FLOAT_RETURN_REGISTER
            if self.type is NumericType.F64
            else SYSV_INTEGER_RETURN_REGISTER
        )
        if self.register != expected:
            raise ValueError(
                f"{self.type.value} return value must use {expected}, "
                f"got {self.register}"
            )


def return_register(type_name: NumericType) -> str:
    return (
        SYSV_FLOAT_RETURN_REGISTER
        if type_name is NumericType.F64
        else SYSV_INTEGER_RETURN_REGISTER
    )
