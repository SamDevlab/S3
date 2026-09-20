"""Typed, block-based S3 intermediate representation independent from the AST."""

from __future__ import annotations

import hashlib
import base64
from dataclasses import dataclass
from enum import Enum

from .diagnostics import SourceLocation
from .vector_types import COMPOSITE_VECTOR_BUILTIN_PREFIX


class IRType(Enum):
    TRIT = "trit"
    TRYTE = "tryte"
    I64 = "i64"
    F64 = "f64"
    STRING = "string"
    BYTES = "bytes"
    TEXT = "text"
    VECTOR = "vector"
    REFERENCE = "reference"


def composite_vector_runtime_signature(
    name: str,
) -> tuple[tuple[IRType, ...], tuple[IRType, ...]] | None:
    """Decode the verifier-visible signature of a monomorphized vector call."""

    decoded = _decode_composite_vector_runtime_name(name)
    if decoded is None:
        return None
    cells, operation = decoded
    reference = (IRType.REFERENCE,)
    if operation == "new":
        return (IRType.I64,), (IRType.VECTOR,)
    if operation in {"len", "capacity"}:
        return reference, (IRType.I64,)
    if operation == "reserve":
        return (IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)
    if operation == "push":
        return (IRType.REFERENCE, *cells), (IRType.TRYTE,)
    if operation == "pop":
        return reference, cells
    if operation == "get":
        return (IRType.REFERENCE, IRType.I64), cells
    if operation == "set":
        return (IRType.REFERENCE, IRType.I64, *cells), (IRType.TRYTE,)
    if operation == "clone":
        return reference, (IRType.VECTOR,)
    if operation == "slice":
        return (IRType.REFERENCE, IRType.I64, IRType.I64), (IRType.VECTOR,)
    return None


def composite_vector_runtime_cell_types(name: str) -> tuple[IRType, ...] | None:
    """Return the statically encoded cells for a composite vector builtin."""

    decoded = _decode_composite_vector_runtime_name(name)
    return None if decoded is None else decoded[0]


def _decode_composite_vector_runtime_name(
    name: str,
) -> tuple[tuple[IRType, ...], str] | None:
    prefix = COMPOSITE_VECTOR_BUILTIN_PREFIX
    if not name.startswith(prefix):
        return None
    parts = name[len(prefix) :].split("__")
    if len(parts) != 3:
        return None
    encoded_type, encoded_cells, operation = parts
    if not encoded_type or encoded_cells == "empty":
        return None
    try:
        padding = "=" * (-len(encoded_type) % 4)
        type_key = base64.urlsafe_b64decode(encoded_type + padding).decode("utf-8")
        cells = tuple(IRType(code) for code in encoded_cells.split("-"))
    except (UnicodeDecodeError, ValueError, base64.binascii.Error):
        return None
    if not type_key or not cells:
        return None
    return cells, operation


DYNAMIC_BUILTIN_SIGNATURES: dict[str, tuple[tuple[IRType, ...], tuple[IRType, ...]]] = {
    "bytes_new": ((IRType.I64,), (IRType.BYTES,)),
    "bytes_len": ((IRType.REFERENCE,), (IRType.I64,)),
    "bytes_capacity": ((IRType.REFERENCE,), (IRType.I64,)),
    "bytes_get": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
    "bytes_set": ((IRType.REFERENCE, IRType.I64, IRType.TRYTE), (IRType.TRYTE,)),
    "bytes_push": ((IRType.REFERENCE, IRType.TRYTE), (IRType.TRYTE,)),
    "bytes_reserve": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
    "bytes_clone": ((IRType.REFERENCE,), (IRType.BYTES,)),
    "bytes_concat": ((IRType.REFERENCE, IRType.REFERENCE), (IRType.BYTES,)),
    "bytes_slice": ((IRType.REFERENCE, IRType.I64, IRType.I64), (IRType.BYTES,)),
    "bytes_from_text": ((IRType.REFERENCE,), (IRType.BYTES,)),
    "text_new": ((IRType.I64,), (IRType.TEXT,)),
    "text_from_static": ((IRType.STRING,), (IRType.TEXT,)),
    "text_len": ((IRType.REFERENCE,), (IRType.I64,)),
    "text_capacity": ((IRType.REFERENCE,), (IRType.I64,)),
    "text_reserve": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
    "text_append": ((IRType.REFERENCE, IRType.REFERENCE), (IRType.TRYTE,)),
    "text_append_static": ((IRType.REFERENCE, IRType.STRING), (IRType.TRYTE,)),
    "text_clone": ((IRType.REFERENCE,), (IRType.TEXT,)),
    "text_concat": ((IRType.REFERENCE, IRType.REFERENCE), (IRType.TEXT,)),
    "text_slice": ((IRType.REFERENCE, IRType.I64, IRType.I64), (IRType.TEXT,)),
    "text_find": ((IRType.REFERENCE, IRType.REFERENCE), (IRType.I64,)),
    "text_from_bytes": ((IRType.REFERENCE,), (IRType.TEXT,)),
}


def _vector_ir_signatures(
    prefix: str,
    element_type: IRType,
) -> dict[str, tuple[tuple[IRType, ...], tuple[IRType, ...]]]:
    reference = (IRType.REFERENCE,)
    mutable = (IRType.REFERENCE,)
    return {
        f"{prefix}_vector_new": ((IRType.I64,), (IRType.VECTOR,)),
        f"{prefix}_vector_len": (reference, (IRType.I64,)),
        f"{prefix}_vector_capacity": (reference, (IRType.I64,)),
        f"{prefix}_vector_reserve": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        f"{prefix}_vector_push": ((IRType.REFERENCE, element_type), (IRType.TRYTE,)),
        f"{prefix}_vector_pop": (mutable, (element_type,)),
        f"{prefix}_vector_get": ((IRType.REFERENCE, IRType.I64), (element_type,)),
        f"{prefix}_vector_set": ((IRType.REFERENCE, IRType.I64, element_type), (IRType.TRYTE,)),
        f"{prefix}_vector_clone": (reference, (IRType.VECTOR,)),
        f"{prefix}_vector_slice": ((IRType.REFERENCE, IRType.I64, IRType.I64), (IRType.VECTOR,)),
    }


DYNAMIC_BUILTIN_SIGNATURES.update(_vector_ir_signatures("tryte", IRType.TRYTE))
DYNAMIC_BUILTIN_SIGNATURES.update(_vector_ir_signatures("i64", IRType.I64))
DYNAMIC_BUILTIN_SIGNATURES.update(_vector_ir_signatures("f64", IRType.F64))

DYNAMIC_BUILTIN_SIGNATURES.update(
    {
        "i64_map_new": ((IRType.I64,), (IRType.VECTOR,)),
        "i64_map_len": ((IRType.REFERENCE,), (IRType.I64,)),
        "i64_map_capacity": ((IRType.REFERENCE,), (IRType.I64,)),
        "i64_map_reserve": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        "i64_map_put": ((IRType.REFERENCE, IRType.I64, IRType.I64), (IRType.TRYTE,)),
        "i64_map_contains": ((IRType.REFERENCE, IRType.I64), (IRType.TRIT,)),
        "i64_map_get": ((IRType.REFERENCE, IRType.I64), (IRType.I64,)),
        "i64_map_remove": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        "i64_map_key_at": ((IRType.REFERENCE, IRType.I64), (IRType.I64,)),
        "i64_map_value_at": ((IRType.REFERENCE, IRType.I64), (IRType.I64,)),
        "i64_map_clone": ((IRType.REFERENCE,), (IRType.VECTOR,)),
        "text_i64_map_new": ((IRType.I64,), (IRType.VECTOR,)),
        "text_i64_map_len": ((IRType.REFERENCE,), (IRType.I64,)),
        "text_i64_map_capacity": ((IRType.REFERENCE,), (IRType.I64,)),
        "text_i64_map_reserve": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        "text_i64_map_put": ((IRType.REFERENCE, IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        "text_i64_map_contains": ((IRType.REFERENCE, IRType.REFERENCE), (IRType.TRIT,)),
        "text_i64_map_get": ((IRType.REFERENCE, IRType.REFERENCE), (IRType.I64,)),
        "text_i64_map_remove": ((IRType.REFERENCE, IRType.REFERENCE), (IRType.TRYTE,)),
        "text_i64_map_key_at": ((IRType.REFERENCE, IRType.I64), (IRType.TEXT,)),
        "text_i64_map_value_at": ((IRType.REFERENCE, IRType.I64), (IRType.I64,)),
        "text_i64_map_clone": ((IRType.REFERENCE,), (IRType.VECTOR,)),
        "i64_set_new": ((IRType.I64,), (IRType.VECTOR,)),
        "i64_set_len": ((IRType.REFERENCE,), (IRType.I64,)),
        "i64_set_capacity": ((IRType.REFERENCE,), (IRType.I64,)),
        "i64_set_reserve": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        "i64_set_add": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        "i64_set_contains": ((IRType.REFERENCE, IRType.I64), (IRType.TRIT,)),
        "i64_set_remove": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        "i64_set_at": ((IRType.REFERENCE, IRType.I64), (IRType.I64,)),
        "i64_set_clone": ((IRType.REFERENCE,), (IRType.VECTOR,)),
    }
)

DYNAMIC_BUILTIN_SIGNATURES.update(
    {
        "host_capability_grant": ((IRType.I64,), (IRType.I64,)),
        "resource_open": ((IRType.I64,), (IRType.I64,)),
        "resource_is_open": ((IRType.REFERENCE,), (IRType.TRIT,)),
        "resource_kind": ((IRType.REFERENCE,), (IRType.I64,)),
        "resource_invoke": ((IRType.REFERENCE, IRType.I64), (IRType.TRYTE,)),
        "resource_close": ((IRType.REFERENCE,), (IRType.TRYTE,)),
    }
)


class IROpcode(Enum):
    CONST = "const"
    CONST_STR = "const_str"
    MOVE = "move"
    INVERT = "invert"
    ADD = "add"
    NUMERIC_DIFFERENCE = "numeric_difference"
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
    AGGREGATE_ADDRESS_OF = "aggregate_address_of"
    AGGREGATE_FIELD_LOAD = "aggregate_field_load"
    AGGREGATE_FIELD_ADDRESS = "aggregate_field_address"
    REFERENCE_LOAD = "reference_load"
    REFERENCE_STORE = "reference_store"
    SLICE_LENGTH = "slice_length"
    SLICE_LOAD = "slice_load"
    SLICE_STORE = "slice_store"
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
    reference_is_slice: bool = False
    slice_length_register: int | None = None
    reference_aggregate: str | None = None

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
            result["reference_is_slice"] = self.reference_is_slice
        if self.reference_aggregate is not None:
            result["reference_aggregate"] = self.reference_aggregate
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
    reference_is_slice: bool = False
    slice_length_register: int | None = None
    reference_aggregate: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "register": f"r{self.register}",
            "type": self.type.value,
        }
        if self.reference_target is not None:
            result["reference_target"] = self.reference_target.value
            result["reference_mutable"] = self.reference_mutable
            result["reference_is_slice"] = self.reference_is_slice
        if self.reference_aggregate is not None:
            result["reference_aggregate"] = self.reference_aggregate
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
    reference_is_slice: bool = False
    slice_length_result: int | None = None
    reference_aggregate: str | None = None
    aggregate_field_paths: tuple[tuple[str, ...], ...] = ()
    aggregate_field_path: tuple[str, ...] = ()

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
            result["reference_is_slice"] = self.reference_is_slice
        if self.reference_aggregate is not None:
            result["reference_aggregate"] = self.reference_aggregate
        if self.aggregate_field_paths:
            result["aggregate_field_paths"] = [list(path) for path in self.aggregate_field_paths]
        if self.aggregate_field_path:
            result["aggregate_field_path"] = list(self.aggregate_field_path)
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
    external: bool = False
    exported: bool = False

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
