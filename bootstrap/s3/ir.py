"""Typed, block-based S3 intermediate representation independent from the AST."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .diagnostics import SourceLocation


class IRType(Enum):
    TRIT = "trit"
    TRYTE = "tryte"


class IROpcode(Enum):
    CONST = "const"
    MOVE = "move"
    INVERT = "invert"
    ADD = "add"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    COMPARE = "compare"
    CALL = "call"
    RETURN = "return"
    JUMP = "jump"
    BRANCH3 = "branch3"


TERMINATOR_OPCODES = {
    IROpcode.RETURN,
    IROpcode.JUMP,
    IROpcode.BRANCH3,
}


@dataclass(frozen=True, slots=True)
class IRRegister:
    index: int
    type: IRType
    location: SourceLocation | None = None

    @property
    def name(self) -> str:
        return f"r{self.index}"

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "index": self.index,
            "type": self.type.value,
        }
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRParameter:
    name: str
    register: int
    type: IRType
    location: SourceLocation | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "register": f"r{self.register}",
            "type": self.type.value,
        }
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRInstruction:
    opcode: IROpcode
    result: int | None = None
    operands: tuple[int, ...] = ()
    immediate: int | None = None
    callee: str | None = None
    targets: tuple[str, ...] = ()
    location: SourceLocation | None = None

    @property
    def is_terminator(self) -> bool:
        return isinstance(self.opcode, IROpcode) and self.opcode in TERMINATOR_OPCODES

    def to_dict(self) -> dict[str, object]:
        opcode = (
            self.opcode.value
            if isinstance(self.opcode, IROpcode)
            else str(self.opcode)
        )
        result: dict[str, object] = {"opcode": opcode}
        if self.result is not None:
            result["result"] = f"r{self.result}"
        if self.operands:
            result["operands"] = [f"r{operand}" for operand in self.operands]
        if self.immediate is not None:
            result["immediate"] = self.immediate
        if self.callee is not None:
            result["callee"] = self.callee
        if self.targets:
            result["targets"] = list(self.targets)
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRBasicBlock:
    name: str
    instructions: tuple[IRInstruction, ...]
    location: SourceLocation | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "instructions": [
                instruction.to_dict() for instruction in self.instructions
            ],
        }
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRFunction:
    name: str
    parameters: tuple[IRParameter, ...]
    return_type: IRType
    registers: tuple[IRRegister, ...]
    blocks: tuple[IRBasicBlock, ...]
    location: SourceLocation | None = None

    @property
    def instructions(self) -> tuple[IRInstruction, ...]:
        """Flattened compatibility/debug view; blocks remain authoritative."""

        return tuple(
            instruction
            for block in self.blocks
            for instruction in block.instructions
        )

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "parameters": [
                parameter.to_dict() for parameter in self.parameters
            ],
            "return_type": self.return_type.value,
            "registers": [register.to_dict() for register in self.registers],
            "blocks": [block.to_dict() for block in self.blocks],
        }
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRModule:
    functions: tuple[IRFunction, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "module": {
                "functions": [
                    function.to_dict() for function in self.functions
                ]
            }
        }


# Backward-compatible public name used by the 0.1 pipeline.
IRProgram = IRModule

