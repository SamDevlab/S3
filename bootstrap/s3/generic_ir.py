"""Arena-backed generic IR model and transactional builder.

The model is intentionally separate from ``bootstrap.s3.ir``.  The latter is
the reference compiler's convenient immutable object graph; this module is the
flat identity/range model intended for later self-host representation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable

from .compiler_substrate import InvalidIdError, StableArena
from .ir import (
    DYNAMIC_BUILTIN_SIGNATURES,
    IRType,
    IROpcode,
    composite_vector_runtime_signature,
)


@dataclass(frozen=True, slots=True)
class IRRange:
    first: int
    count: int


@dataclass(frozen=True, slots=True)
class IRValue:
    id: int
    function_id: int
    type: IRType
    reference_target: IRType | None = None
    reference_mutable: bool = False
    reference_is_slice: bool = False
    slice_length_value_id: int | None = None


@dataclass(frozen=True, slots=True)
class IRParameter:
    id: int
    function_id: int
    name_symbol_id: int
    value_id: int


@dataclass(frozen=True, slots=True)
class IRMemoryObject:
    id: int
    function_id: int
    element_type: IRType
    length: int
    mutable: bool


@dataclass(frozen=True, slots=True)
class IRStaticString:
    id: int
    value: str


@dataclass(frozen=True, slots=True)
class IRInstruction:
    id: int
    function_id: int
    block_id: int
    opcode: IROpcode
    result_range: IRRange
    operand_range: IRRange
    target_range: IRRange
    immediate: int | float | None = None
    static_string_id: int | None = None
    callee_function_id: int | None = None
    callee_builtin: str | None = None
    memory_id: int | None = None
    initialization: bool = False
    reference_target: IRType | None = None
    reference_mutable: bool = False
    reference_is_slice: bool = False


@dataclass(slots=True)
class IRBlock:
    id: int
    function_id: int
    label_symbol_id: int
    instruction_range: IRRange
    terminator_id: int | None = None


@dataclass(slots=True)
class IRFunction:
    id: int
    name_symbol_id: int
    name: str
    parameter_range: IRRange
    result_type_range: IRRange
    value_range: IRRange
    memory_range: IRRange
    block_range: IRRange
    entry_block_id: int | None
    external: bool = False
    exported: bool = False


@dataclass(frozen=True, slots=True)
class IRCheckpoint:
    cursors: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class IRBuilderCheckpoint:
    program: IRCheckpoint
    function_id: int | None
    block_id: int | None
    function_snapshot: IRFunction | None
    block_snapshot: IRBlock | None


@dataclass(frozen=True, slots=True)
class BuiltinSignature:
    name: str
    parameters: tuple[IRType, ...]
    results: tuple[IRType, ...]


class CapabilityTable:
    """Deterministic ordinary data view of reference builtin signatures."""

    def __init__(self, entries: Iterable[BuiltinSignature] = ()) -> None:
        self._entries = tuple(sorted(entries, key=lambda entry: entry.name))

    @classmethod
    def reference(cls) -> "CapabilityTable":
        return cls(
            BuiltinSignature(name, parameters, results)
            for name, (parameters, results) in sorted(DYNAMIC_BUILTIN_SIGNATURES.items())
        )

    def signature(self, name: str) -> BuiltinSignature | None:
        for entry in self._entries:
            if entry.name == name:
                return entry
        decoded = composite_vector_runtime_signature(name)
        if decoded is None:
            return None
        parameters, results = decoded
        return BuiltinSignature(name, parameters, results)

    @property
    def entries(self) -> tuple[BuiltinSignature, ...]:
        return self._entries


class IRProgram:
    """One authoritative arena for each generic IR entity and sequence."""

    def __init__(self) -> None:
        self.functions: StableArena[IRFunction] = StableArena()
        self.blocks: StableArena[IRBlock] = StableArena()
        self.instructions: StableArena[IRInstruction] = StableArena()
        self.values: StableArena[IRValue] = StableArena()
        self.parameters: StableArena[IRParameter] = StableArena()
        self.memory_objects: StableArena[IRMemoryObject] = StableArena()
        self.static_strings: StableArena[IRStaticString] = StableArena()
        self.result_types: StableArena[IRType] = StableArena()
        self.operands: StableArena[int] = StableArena()
        self.results: StableArena[int] = StableArena()
        self.targets: StableArena[int] = StableArena()

    @property
    def arenas(self) -> tuple[tuple[str, StableArena[object]], ...]:
        return (
            ("functions", self.functions),
            ("blocks", self.blocks),
            ("instructions", self.instructions),
            ("values", self.values),
            ("parameters", self.parameters),
            ("memory_objects", self.memory_objects),
            ("static_strings", self.static_strings),
            ("result_types", self.result_types),
            ("operands", self.operands),
            ("results", self.results),
            ("targets", self.targets),
        )

    def checkpoint(self) -> IRCheckpoint:
        return IRCheckpoint(tuple((name, arena.checkpoint()) for name, arena in self.arenas))

    def rollback(self, checkpoint: IRCheckpoint) -> None:
        by_name = dict(self.arenas)
        for name, cursor in checkpoint.cursors:
            by_name[name].rollback(cursor)

    def range_values(self, arena: StableArena[object], value_range: IRRange) -> tuple[object, ...]:
        if value_range.first < 0 or value_range.count < 0:
            raise ValueError("invalid IR range")
        return tuple(arena.get(value_range.first + offset) for offset in range(value_range.count))

    def range_ids(self, arena: StableArena[int], value_range: IRRange) -> tuple[int, ...]:
        return tuple(int(value) for value in self.range_values(arena, value_range))

    def to_dict(self) -> dict[str, object]:
        def encode(value: object) -> object:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            if is_dataclass(value):
                return {key: encode(item) for key, item in asdict(value).items()}
            return value

        return {
            name: [
                {"id": item_id, "value": encode(value)}
                for item_id, value in arena.items()
            ]
            for name, arena in self.arenas
        }

    def structural_digest(self) -> str:
        data = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return sha256(data).hexdigest()


class IRBuilder:
    """Direct-ID IR construction with O(number of arena cursors) checkpoints."""

    def __init__(self, program: IRProgram | None = None) -> None:
        self.program = program or IRProgram()
        self.current_function_id: int | None = None
        self.current_block_id: int | None = None

    def checkpoint(self) -> IRBuilderCheckpoint:
        function_snapshot = None
        block_snapshot = None
        if self.current_function_id is not None:
            function_snapshot = replace(self.program.functions.get(self.current_function_id))
        if self.current_block_id is not None:
            block_snapshot = replace(self.program.blocks.get(self.current_block_id))
        return IRBuilderCheckpoint(
            self.program.checkpoint(),
            self.current_function_id,
            self.current_block_id,
            function_snapshot,
            block_snapshot,
        )

    def rollback(self, checkpoint: IRBuilderCheckpoint) -> None:
        self.program.rollback(checkpoint.program)
        self.current_function_id = checkpoint.function_id
        self.current_block_id = checkpoint.block_id
        if checkpoint.function_id is not None and checkpoint.function_snapshot is not None:
            function = self.program.functions.get(checkpoint.function_id)
            function.parameter_range = checkpoint.function_snapshot.parameter_range
            function.result_type_range = checkpoint.function_snapshot.result_type_range
            function.value_range = checkpoint.function_snapshot.value_range
            function.memory_range = checkpoint.function_snapshot.memory_range
            function.block_range = checkpoint.function_snapshot.block_range
            function.entry_block_id = checkpoint.function_snapshot.entry_block_id
        if checkpoint.block_id is not None and checkpoint.block_snapshot is not None:
            block = self.program.blocks.get(checkpoint.block_id)
            block.instruction_range = checkpoint.block_snapshot.instruction_range
            block.terminator_id = checkpoint.block_snapshot.terminator_id

    def begin_function(
        self,
        name_symbol_id: int,
        name: str,
        result_types: tuple[IRType, ...],
        *,
        external: bool = False,
        exported: bool = False,
    ) -> int:
        if self.current_function_id is not None:
            raise ValueError("a function is already open")
        if not result_types:
            raise ValueError("a function requires at least one result type")
        result_first = self.program.result_types.checkpoint()
        for result_type in result_types:
            self.program.result_types.append(result_type)
        function_id = self.program.functions.checkpoint()
        self.program.functions.append(
            IRFunction(
                function_id,
                name_symbol_id,
                name,
                IRRange(self.program.parameters.checkpoint(), 0),
                IRRange(result_first, len(result_types)),
                IRRange(self.program.values.checkpoint(), 0),
                IRRange(self.program.memory_objects.checkpoint(), 0),
                IRRange(self.program.blocks.checkpoint(), 0),
                None,
                external,
                exported,
            )
        )
        self.current_function_id = function_id
        return function_id

    def _function(self) -> IRFunction:
        if self.current_function_id is None:
            raise ValueError("no function is open")
        return self.program.functions.get(self.current_function_id)

    def add_parameter(self, name_symbol_id: int, type: IRType, **metadata: object) -> int:
        function = self._function()
        value_id = self.allocate_value(type, **metadata)
        parameter_id = self.program.parameters.checkpoint()
        self.program.parameters.append(
            IRParameter(parameter_id, function.id, name_symbol_id, value_id)
        )
        function.parameter_range = IRRange(
            parameter_id if function.parameter_range.count == 0 else function.parameter_range.first,
            function.parameter_range.count + 1,
        )
        return parameter_id

    def allocate_value(self, type: IRType, **metadata: object) -> int:
        function = self._function()
        value_id = self.program.values.checkpoint()
        self.program.values.append(IRValue(value_id, function.id, type, **metadata))
        function.value_range = IRRange(
            value_id if function.value_range.count == 0 else function.value_range.first,
            function.value_range.count + 1,
        )
        return value_id

    def allocate_memory(self, element_type: IRType, length: int, mutable: bool) -> int:
        function = self._function()
        memory_id = self.program.memory_objects.checkpoint()
        self.program.memory_objects.append(
            IRMemoryObject(memory_id, function.id, element_type, length, mutable)
        )
        function.memory_range = IRRange(
            memory_id if function.memory_range.count == 0 else function.memory_range.first,
            function.memory_range.count + 1,
        )
        return memory_id

    def add_static_string(self, value: str) -> int:
        static_id = self.program.static_strings.checkpoint()
        self.program.static_strings.append(IRStaticString(static_id, value))
        return static_id

    def begin_block(self, label_symbol_id: int) -> int:
        function = self._function()
        if self.current_block_id is not None:
            raise ValueError("a block is already open")
        block_id = self.program.blocks.checkpoint()
        self.program.blocks.append(
            IRBlock(
                block_id,
                function.id,
                label_symbol_id,
                IRRange(self.program.instructions.checkpoint(), 0),
            )
        )
        if function.entry_block_id is None:
            function.entry_block_id = block_id
        function.block_range = IRRange(
            block_id if function.block_range.count == 0 else function.block_range.first,
            function.block_range.count + 1,
        )
        self.current_block_id = block_id
        return block_id

    def reserve_block(self, label_symbol_id: int) -> int:
        """Allocate a block ID without opening it for instruction emission."""

        function = self._function()
        block_id = self.program.blocks.checkpoint()
        self.program.blocks.append(
            IRBlock(
                block_id,
                function.id,
                label_symbol_id,
                IRRange(self.program.instructions.checkpoint(), 0),
            )
        )
        if function.entry_block_id is None:
            function.entry_block_id = block_id
        function.block_range = IRRange(
            block_id if function.block_range.count == 0 else function.block_range.first,
            function.block_range.count + 1,
        )
        return block_id

    def open_block(self, block_id: int) -> None:
        function = self._function()
        if self.current_block_id is not None:
            raise ValueError("a block is already open")
        block = self.program.blocks.get(block_id)
        if block.function_id != function.id:
            raise ValueError("block belongs to another function")
        if block.instruction_range.count == 0:
            block.instruction_range = IRRange(self.program.instructions.checkpoint(), 0)
        self.current_block_id = block_id

    def append_instruction(
        self,
        opcode: IROpcode,
        *,
        result_ids: tuple[int, ...] = (),
        operand_ids: tuple[int, ...] = (),
        target_block_ids: tuple[int, ...] = (),
        immediate: int | float | None = None,
        static_string_id: int | None = None,
        callee_function_id: int | None = None,
        callee_builtin: str | None = None,
        memory_id: int | None = None,
        initialization: bool = False,
        reference_target: IRType | None = None,
        reference_mutable: bool = False,
        reference_is_slice: bool = False,
    ) -> int:
        function = self._function()
        if self.current_block_id is None:
            raise ValueError("no block is open")
        instruction_id = self.program.instructions.checkpoint()
        result_first = self.program.results.checkpoint()
        operand_first = self.program.operands.checkpoint()
        target_first = self.program.targets.checkpoint()
        for value_id in result_ids:
            self.program.results.append(value_id)
        for value_id in operand_ids:
            self.program.operands.append(value_id)
        for block_id in target_block_ids:
            self.program.targets.append(block_id)
        self.program.instructions.append(
            IRInstruction(
                instruction_id,
                function.id,
                self.current_block_id,
                opcode,
                IRRange(result_first, len(result_ids)),
                IRRange(operand_first, len(operand_ids)),
                IRRange(target_first, len(target_block_ids)),
                immediate,
                static_string_id,
                callee_function_id,
                callee_builtin,
                memory_id,
                initialization,
                reference_target,
                reference_mutable,
                reference_is_slice,
            )
        )
        block = self.program.blocks.get(self.current_block_id)
        block.instruction_range = IRRange(
            instruction_id if block.instruction_range.count == 0 else block.instruction_range.first,
            block.instruction_range.count + 1,
        )
        block.terminator_id = instruction_id if opcode in {
            IROpcode.RETURN,
            IROpcode.JUMP,
            IROpcode.BRANCH3,
        } else block.terminator_id
        return instruction_id

    def finish_block(self) -> None:
        if self.current_block_id is None:
            raise ValueError("no block is open")
        self.current_block_id = None

    def finish_function(self) -> int:
        function = self._function()
        if self.current_block_id is not None:
            raise ValueError("finish the current block first")
        function_id = function.id
        self.current_function_id = None
        return function_id


__all__ = [
    "BuiltinSignature",
    "CapabilityTable",
    "IRBlock",
    "IRBuilder",
    "IRBuilderCheckpoint",
    "IRCheckpoint",
    "IRFunction",
    "IRInstruction",
    "IRMemoryObject",
    "IRParameter",
    "IRProgram",
    "IRRange",
    "IRStaticString",
    "IRValue",
    "IROpcode",
    "IRType",
]
