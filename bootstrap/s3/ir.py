"""Typed, block-based S3 intermediate representation independent from the AST."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from .diagnostics import SourceLocation


class IRType(Enum):
    TRIT = "trit"
    TRYTE = "tryte"
    I64 = "i64"
    F64 = "f64"
    STRING = "string"
    REFERENCE = "reference"


class IROpcode(Enum):
    CONST = "const"
    CONST_STR = "const_str"
    MOVE = "move"
    INVERT = "invert"
    ADD = "add"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    RELATE = "relate"
    CONVERT = "convert"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    COMPARE = "compare"
    CALL = "call"
    LOAD = "load"
    STORE = "store"
    ADDRESS_OF = "address_of"
    REFERENCE_LOAD = "reference_load"
    REFERENCE_STORE = "reference_store"
    RETURN = "return"
    JUMP = "jump"
    BRANCH3 = "branch3"


TERMINATOR_OPCODES = {
    IROpcode.RETURN,
    IROpcode.JUMP,
    IROpcode.BRANCH3,
}


@dataclass(frozen=True, slots=True)
class IRStaticString:
    id: str
    value: str

    @property
    def utf8_bytes(self) -> tuple[int, ...]:
        return tuple(self.value.encode("utf-8"))

    @property
    def byte_count(self) -> int:
        return len(self.utf8_bytes)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.value.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "value": self.value,
            "utf8_bytes": list(self.utf8_bytes),
            "byte_count": self.byte_count,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class IRRegister:
    index: int
    type: IRType
    location: SourceLocation | None = None
    reference_target: IRType | None = None
    reference_mutable: bool = False

    @property
    def name(self) -> str:
        return f"r{self.index}"

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "index": self.index,
            "type": self.type.value,
        }
        if self.reference_target is not None:
            result["reference_target"] = self.reference_target.value
            result["reference_mutable"] = self.reference_mutable
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRParameter:
    name: str
    register: int
    type: IRType
    location: SourceLocation | None = None
    reference_target: IRType | None = None
    reference_mutable: bool = False

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "register": f"r{self.register}",
            "type": self.type.value,
        }
        if self.reference_target is not None:
            result["reference_target"] = self.reference_target.value
            result["reference_mutable"] = self.reference_mutable
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRMemoryObject:
    index: int
    element_type: IRType
    length: int
    mutable: bool
    location: SourceLocation | None = None

    @property
    def name(self) -> str:
        return f"m{self.index}"

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "index": self.index,
            "element_type": self.element_type.value,
            "length": self.length,
            "mutable": self.mutable,
        }
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRInstruction:
    opcode: IROpcode
    result: int | None = None
    operands: tuple[int, ...] = ()
    immediate: int | float | None = None
    static_string: str | None = None
    callee: str | None = None
    targets: tuple[str, ...] = ()
    memory: int | None = None
    initialization: bool = False
    location: SourceLocation | None = None
    results: tuple[int, ...] = ()
    reference_target: IRType | None = None
    reference_mutable: bool = False

    def __post_init__(self) -> None:
        if self.results and self.result is not None and self.results != (self.result,):
            raise ValueError("IRInstruction cannot set both result and results")
        if not self.results and self.result is not None:
            object.__setattr__(self, "results", (self.result,))

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
        if self.results:
            result["results"] = [f"r{register}" for register in self.results]
        if self.operands:
            result["operands"] = [f"r{operand}" for operand in self.operands]
        if self.immediate is not None:
            result["immediate"] = self.immediate
        if self.static_string is not None:
            result["static_string"] = self.static_string
        if self.callee is not None:
            result["callee"] = self.callee
        if self.targets:
            result["targets"] = list(self.targets)
        if self.memory is not None:
            result["memory"] = f"m{self.memory}"
        if self.initialization:
            result["initialization"] = True
        if self.location is not None:
            result["source"] = self.location.to_dict()
        if self.reference_target is not None:
            result["reference_target"] = self.reference_target.value
            result["reference_mutable"] = self.reference_mutable
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
    memory_objects: tuple[IRMemoryObject, ...] = ()
    result_types: tuple[IRType, ...] = ()

    def __post_init__(self) -> None:
        if not self.result_types:
            object.__setattr__(self, "result_types", (self.return_type,))

    @property
    def result_width(self) -> int:
        return len(self.result_types)

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
            "result_types": [type_name.value for type_name in self.result_types],
            "registers": [register.to_dict() for register in self.registers],
            "memory_objects": [
                memory.to_dict() for memory in self.memory_objects
            ],
            "blocks": [block.to_dict() for block in self.blocks],
        }
        if self.location is not None:
            result["source"] = self.location.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class IRModule:
    functions: tuple[IRFunction, ...]
    static_strings: tuple[IRStaticString, ...] = ()

    def to_dict(self) -> dict[str, object]:
        module: dict[str, object] = {
            "functions": [
                function.to_dict() for function in self.functions
            ]
        }
        if self.static_strings:
            module["static_strings"] = [
                entry.to_dict() for entry in self.static_strings
            ]
        return {"module": module}


# Backward-compatible public name used by the 0.1 pipeline.
IRProgram = IRModule
