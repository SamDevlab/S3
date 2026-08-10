"""Native x86-64 lowering contract for the M1.32 numeric IR subset."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .numeric import NumericType
from .numeric_abi import return_register


class NativeNumericOpcode(Enum):
    ADD_I64 = "addq"
    ADD_F64 = "addsd"
    RETURN_I64 = "movq"
    RETURN_F64 = "movsd"


@dataclass(frozen=True, slots=True)
class NativeNumericInstruction:
    opcode: NativeNumericOpcode
    source: str
    destination: str

    def render(self) -> str:
        return f"{self.opcode.value} {self.source}, {self.destination}"


def lower_add(type_name: NumericType, left: str, right: str) -> NativeNumericInstruction:
    if type_name is NumericType.I64:
        opcode = NativeNumericOpcode.ADD_I64
    elif type_name is NumericType.F64:
        opcode = NativeNumericOpcode.ADD_F64
    else:
        raise ValueError(f"unsupported native numeric type {type_name!r}")
    return NativeNumericInstruction(opcode, right, left)


def lower_return(type_name: NumericType, source: str) -> NativeNumericInstruction:
    if type_name is NumericType.I64:
        opcode = NativeNumericOpcode.RETURN_I64
    elif type_name is NumericType.F64:
        opcode = NativeNumericOpcode.RETURN_F64
    else:
        raise ValueError(f"unsupported native numeric type {type_name!r}")
    return NativeNumericInstruction(opcode, source, f"%{return_register(type_name)}")

