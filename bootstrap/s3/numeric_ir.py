"""Small typed numeric IR used by the M1.32 numeric-domain boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .numeric import NumericType, NumericValue


class NumericIROpcode(Enum):
    CONST = "const"
    ADD = "add"
    RETURN = "return"


@dataclass(frozen=True, slots=True)
class NumericIRInstruction:
    opcode: NumericIROpcode
    result: int | None = None
    operands: tuple[int, ...] = ()
    value: NumericValue | None = None


@dataclass(frozen=True, slots=True)
class NumericIRFunction:
    instructions: tuple[NumericIRInstruction, ...]
    return_type: NumericType


def evaluate_numeric_ir(function: NumericIRFunction) -> NumericValue:
    registers: dict[int, NumericValue] = {}
    returned: NumericValue | None = None
    for instruction in function.instructions:
        if instruction.opcode is NumericIROpcode.CONST:
            if instruction.result is None or instruction.value is None:
                raise ValueError("numeric const requires result and value")
            registers[instruction.result] = instruction.value
        elif instruction.opcode is NumericIROpcode.ADD:
            if instruction.result is None or len(instruction.operands) != 2:
                raise ValueError("numeric add requires result and two operands")
            try:
                left = registers[instruction.operands[0]]
                right = registers[instruction.operands[1]]
            except KeyError as error:
                raise ValueError("numeric add reads an undefined register") from error
            registers[instruction.result] = left.add(right)
        elif instruction.opcode is NumericIROpcode.RETURN:
            if len(instruction.operands) != 1:
                raise ValueError("numeric return requires one operand")
            try:
                returned = registers[instruction.operands[0]]
            except KeyError as error:
                raise ValueError("numeric return reads an undefined register") from error
            break
        else:
            raise ValueError(f"unsupported numeric opcode {instruction.opcode!r}")
    if returned is None:
        raise ValueError("numeric function did not return a value")
    if returned.type is not function.return_type:
        raise ValueError("numeric return type does not match function type")
    return returned
