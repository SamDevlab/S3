"""Independent structural verifier for :mod:`generic_ir`.

The kernel receives only an ``IRProgram`` and a capability table.  It has no
AST, syntax arena, semantic environment, source fixture, or lowering state.
All temporary registries are created per call and are discarded with the
returned result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .generic_ir import (
    CapabilityTable,
    IRBlock,
    IRFunction,
    IRInstruction,
    IRProgram,
    IRRange,
    IRValue,
    IROpcode,
    IRType,
)
from .compiler_substrate import InvalidIdError
from .ternary import TRYTE_MAX


@dataclass(frozen=True, slots=True)
class VerifierConfig:
    capabilities: CapabilityTable
    max_memory_length: int = TRYTE_MAX + 1

    @classmethod
    def reference(cls) -> "VerifierConfig":
        return cls(CapabilityTable.reference())


@dataclass(frozen=True, slots=True)
class VerificationResult:
    success: bool
    diagnostic_code: str | None = None
    message: str = ""
    function_id: int | None = None
    block_id: int | None = None
    instruction_id: int | None = None
    reachable_blocks: tuple[int, ...] = ()
    cfg_successors: tuple[tuple[int, tuple[int, ...]], ...] = ()
    dominators: tuple[tuple[int, tuple[int, ...]], ...] = ()


class _Failure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        function_id: int | None = None,
        block_id: int | None = None,
        instruction_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.function_id = function_id
        self.block_id = block_id
        self.instruction_id = instruction_id


class IRVerifierKernel:
    """Deterministic multi-pass verifier over the generic indexed IR."""

    def __init__(self, config: VerifierConfig | None = None) -> None:
        self.config = config or VerifierConfig.reference()

    def verify(self, program: IRProgram) -> VerificationResult:
        before = program.structural_digest()
        state = _VerificationState(program)
        try:
            state.collect_static_strings()
            state.collect_functions()
            for function_id, function in program.functions.items():
                if function.external:
                    if function.block_range.count or function.entry_block_id is not None:
                        state.fail(
                            "external_function_blocks",
                            "external function must not own blocks",
                            function_id=function_id,
                        )
                    continue
                state.verify_function(function_id, function, self.config)
            after = program.structural_digest()
            if before != after:
                raise _Failure("verifier_mutated_ir", "verifier changed IR state")
            return VerificationResult(
                True,
                reachable_blocks=tuple(sorted(state.reachable)),
                cfg_successors=tuple(
                    (block_id, tuple(state.successors[block_id]))
                    for block_id in sorted(state.successors)
                ),
                dominators=tuple(
                    (block_id, tuple(sorted(state.dominators[block_id])))
                    for block_id in sorted(state.dominators)
                ),
            )
        except _Failure as failure:
            after = program.structural_digest()
            code = failure.code
            message = failure.message
            if before != after:
                code = "verifier_mutated_ir"
                message = "verifier changed IR state"
            return VerificationResult(
                False,
                code,
                message,
                failure.function_id,
                failure.block_id,
                failure.instruction_id,
            )


class _VerificationState:
    def __init__(self, program: IRProgram) -> None:
        self.program = program
        self.functions_by_id: dict[int, IRFunction] = {}
        self.functions_by_symbol: dict[int, int] = {}
        self.blocks_by_id: dict[int, IRBlock] = {}
        self.values_by_id: dict[int, IRValue] = {}
        self.definitions: dict[int, tuple[int, int | None]] = {}
        self.successors: dict[int, list[int]] = {}
        self.predecessors: dict[int, list[int]] = {}
        self.reachable: set[int] = set()
        self.dominators: dict[int, set[int]] = {}

    def fail(
        self,
        code: str,
        message: str,
        *,
        function_id: int | None = None,
        block_id: int | None = None,
        instruction_id: int | None = None,
    ) -> None:
        raise _Failure(
            code,
            message,
            function_id=function_id,
            block_id=block_id,
            instruction_id=instruction_id,
        )

    def collect_static_strings(self) -> None:
        previous_id = -1
        for arena_id, entry in self.program.static_strings.items():
            if entry.id != arena_id:
                self.fail("static_string_identity", "static string ID does not match arena ID")
            if entry.id <= previous_id:
                self.fail("static_string_order", "static string IDs are not deterministic")
            if not isinstance(entry.value, str):
                self.fail("static_string_value", "static string value is not text")
            previous_id = entry.id

    def collect_functions(self) -> None:
        for function_id, function in self.program.functions.items():
            if function.id != function_id:
                self.fail("function_identity", "function ID does not match arena ID")
            if not isinstance(function.name, str) or not function.name:
                self.fail("function_metadata", "function name is empty", function_id=function_id)
            if function.name_symbol_id in self.functions_by_symbol:
                self.fail(
                    "duplicate_function_identity",
                    f"duplicate function symbol {function.name_symbol_id}",
                    function_id=function_id,
                )
            self.functions_by_id[function_id] = function
            self.functions_by_symbol[function.name_symbol_id] = function_id

    def _range(
        self,
        arena: object,
        value_range: IRRange,
        *,
        function_id: int,
        field: str,
    ) -> tuple[object, ...]:
        if value_range.first < 0 or value_range.count < 0:
            self.fail("invalid_range", f"{field} has a negative range", function_id=function_id)
        try:
            return tuple(
                getattr(arena, "get")(value_range.first + offset)
                for offset in range(value_range.count)
            )
        except (InvalidIdError, KeyError, IndexError, ValueError) as error:
            self.fail("invalid_range", f"{field} points outside its arena", function_id=function_id)
            raise AssertionError from error

    def _function_types(self, function: IRFunction) -> tuple[IRType, ...]:
        values = self._range(
            self.program.result_types,
            function.result_type_range,
            function_id=function.id,
            field="result types",
        )
        if not values or any(not isinstance(value, IRType) for value in values):
            self.fail("invalid_result_types", "function has no valid result types", function_id=function.id)
        return tuple(values)  # type: ignore[arg-type]

    def verify_function(
        self,
        function_id: int,
        function: IRFunction,
        config: VerifierConfig,
    ) -> None:
        result_types = self._function_types(function)
        parameters = self._range(
            self.program.parameters,
            function.parameter_range,
            function_id=function_id,
            field="parameters",
        )
        values = self._range(
            self.program.values,
            function.value_range,
            function_id=function_id,
            field="values",
        )
        memories = self._range(
            self.program.memory_objects,
            function.memory_range,
            function_id=function_id,
            field="memory objects",
        )
        blocks = self._range(
            self.program.blocks,
            function.block_range,
            function_id=function_id,
            field="blocks",
        )
        if function.entry_block_id is None or function.entry_block_id not in {
            block.id for block in blocks
        }:
            self.fail("missing_entry_block", "function has no valid entry block", function_id=function_id)
        value_types: dict[int, IRType] = {}
        for value in values:
            if value.id in self.values_by_id:
                self.fail("duplicate_value_id", f"duplicate value r{value.id}", function_id=function_id)
            if value.function_id != function_id or not isinstance(value.type, IRType):
                self.fail("invalid_value_metadata", "value metadata is invalid", function_id=function_id)
            value_types[value.id] = value.type
            self.values_by_id[value.id] = value
        memory_ids: dict[int, object] = {}
        for memory in memories:
            if memory.id in memory_ids:
                self.fail("duplicate_memory_id", f"duplicate memory m{memory.id}", function_id=function_id)
            if (
                memory.function_id != function_id
                or not isinstance(memory.element_type, IRType)
                or memory.element_type is IRType.REFERENCE
                or memory.length <= 0
                or memory.length > config.max_memory_length
            ):
                self.fail("invalid_memory", f"invalid memory m{memory.id}", function_id=function_id)
            memory_ids[memory.id] = memory
        parameter_value_ids: set[int] = set()
        parameter_symbols: set[int] = set()
        for parameter in parameters:
            if parameter.function_id != function_id:
                self.fail("invalid_parameter", "parameter belongs to another function", function_id=function_id)
            if parameter.name_symbol_id in parameter_symbols:
                self.fail("duplicate_parameter", "duplicate parameter symbol", function_id=function_id)
            parameter_symbols.add(parameter.name_symbol_id)
            if parameter.value_id not in value_types or parameter.value_id in parameter_value_ids:
                self.fail("invalid_parameter_value", "parameter value is invalid", function_id=function_id)
            parameter_value_ids.add(parameter.value_id)
            self.definitions[parameter.value_id] = (function_id, None)
        block_ids = {block.id for block in blocks}
        if len(block_ids) != len(blocks):
            self.fail("duplicate_block_id", "duplicate block ID", function_id=function_id)
        for block in blocks:
            if block.function_id != function_id:
                self.fail("invalid_block_owner", "block belongs to another function", function_id=function_id, block_id=block.id)
            self.blocks_by_id[block.id] = block
        for block in blocks:
            self._verify_block(function, block, block_ids, value_types, memory_ids, result_types, config)
        self._verify_cfg(function, blocks)
        self._verify_dominance(function, blocks)

    def _range_for_block(self, block: IRBlock) -> tuple[IRInstruction, ...]:
        try:
            return tuple(
                self.program.instructions.get(block.instruction_range.first + offset)
                for offset in range(block.instruction_range.count)
            )
        except (InvalidIdError, KeyError, IndexError, ValueError) as error:
            self.fail("invalid_instruction_range", "block instruction range is invalid", function_id=block.function_id, block_id=block.id)
            raise AssertionError from error

    def _value_ids(self, value_range: IRRange, arena: object) -> tuple[int, ...]:
        try:
            return tuple(
                int(getattr(arena, "get")(value_range.first + offset))
                for offset in range(value_range.count)
            )
        except (InvalidIdError, KeyError, IndexError, ValueError) as error:
            self.fail("invalid_sequence_range", "instruction sequence range is invalid")
            raise AssertionError from error

    def _verify_block(
        self,
        function: IRFunction,
        block: IRBlock,
        block_ids: set[int],
        value_types: dict[int, IRType],
        memory_ids: dict[int, object],
        result_types: tuple[IRType, ...],
        config: VerifierConfig,
    ) -> None:
        instructions = self._range_for_block(block)
        if not instructions:
            self.fail("missing_terminator", "block is empty", function_id=function.id, block_id=block.id)
        terminators = [index for index, instruction in enumerate(instructions) if instruction.opcode in {
            IROpcode.RETURN, IROpcode.JUMP, IROpcode.BRANCH3
        }]
        if len(terminators) != 1:
            self.fail("terminator_count", "block must contain exactly one terminator", function_id=function.id, block_id=block.id)
        if terminators[0] != len(instructions) - 1:
            self.fail("terminator_position", "terminator must be the final instruction", function_id=function.id, block_id=block.id, instruction_id=instructions[terminators[0]].id)
        if block.terminator_id != instructions[-1].id:
            self.fail("terminator_metadata", "block terminator metadata is stale", function_id=function.id, block_id=block.id)
        for position, instruction in enumerate(instructions):
            if instruction.id != block.instruction_range.first + position:
                self.fail("instruction_identity", "instruction ID does not match its arena position", function_id=function.id, block_id=block.id, instruction_id=instruction.id)
            if instruction.function_id != function.id or instruction.block_id != block.id:
                self.fail("instruction_owner", "instruction has invalid owner", function_id=function.id, block_id=block.id, instruction_id=instruction.id)
            result_ids = self._value_ids(instruction.result_range, self.program.results)
            operand_ids = self._value_ids(instruction.operand_range, self.program.operands)
            target_ids = self._value_ids(instruction.target_range, self.program.targets)
            for result_id in result_ids:
                if result_id not in value_types:
                    self.fail("unknown_result", f"unknown result r{result_id}", function_id=function.id, block_id=block.id, instruction_id=instruction.id)
                if result_id in self.definitions:
                    self.fail("redefined_value", f"redefinition of r{result_id}", function_id=function.id, block_id=block.id, instruction_id=instruction.id)
                self.definitions[result_id] = (block.id, position)
            for operand_id in operand_ids:
                if operand_id not in value_types:
                    self.fail("unknown_operand", f"unknown operand r{operand_id}", function_id=function.id, block_id=block.id, instruction_id=instruction.id)
            for target_id in target_ids:
                if target_id not in block_ids:
                    self.fail("unknown_target", f"unknown block target b{target_id}", function_id=function.id, block_id=block.id, instruction_id=instruction.id)
            self._verify_instruction(
                instruction,
                result_ids,
                operand_ids,
                target_ids,
                value_types,
                memory_ids,
                result_types,
                function.id,
                config,
            )

    def _verify_instruction(
        self,
        instruction: IRInstruction,
        result_ids: tuple[int, ...],
        operand_ids: tuple[int, ...],
        target_ids: tuple[int, ...],
        value_types: dict[int, IRType],
        memory_ids: dict[int, object],
        function_result_types: tuple[IRType, ...],
        function_id: int,
        config: VerifierConfig,
    ) -> None:
        opcode = instruction.opcode
        if not isinstance(opcode, IROpcode):
            self.fail("unknown_opcode", f"unknown opcode {opcode!r}", function_id=function_id, instruction_id=instruction.id)
        result_types = tuple(value_types[value_id] for value_id in result_ids)
        operand_types = tuple(value_types[value_id] for value_id in operand_ids)

        def count(results: int | None = None, operands: int | None = None) -> None:
            if results is not None and len(result_ids) != results:
                self.fail("result_arity", f"{opcode.value} expects {results} result(s)", function_id=function_id, instruction_id=instruction.id)
            if operands is not None and len(operand_ids) != operands:
                self.fail("operand_arity", f"{opcode.value} expects {operands} operand(s)", function_id=function_id, instruction_id=instruction.id)

        def same(types: tuple[IRType, ...], label: str) -> None:
            if types and any(item is not types[0] for item in types[1:]):
                self.fail("type_mismatch", f"{label} types do not match", function_id=function_id, instruction_id=instruction.id)

        if opcode is IROpcode.CONST:
            count(1, 0)
            if result_types[0] in {IRType.STRING, IRType.BYTES, IRType.TEXT, IRType.VECTOR, IRType.REFERENCE} or instruction.immediate is None:
                self.fail("invalid_const", "const requires a scalar immediate", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.CONST_STR:
            count(1, 0)
            if result_types[0] is not IRType.STRING or instruction.static_string_id is None:
                self.fail("invalid_const_string", "const_str requires a string result and static ID", function_id=function_id, instruction_id=instruction.id)
            try:
                self.program.static_strings.get(instruction.static_string_id)
            except InvalidIdError:
                self.fail("unknown_static_string", "const_str references an unknown static string", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.MOVE:
            count(1, 1); same(result_types + operand_types, "move"); return
        if opcode is IROpcode.INVERT:
            count(1, 1); same(result_types + operand_types, "invert")
            if result_types[0] in {IRType.STRING, IRType.BYTES, IRType.TEXT, IRType.VECTOR, IRType.REFERENCE}:
                self.fail("invalid_invert", "invert requires a scalar value", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode in {IROpcode.ADD, IROpcode.NUMERIC_DIFFERENCE, IROpcode.MULTIPLY, IROpcode.DIVIDE, IROpcode.MINIMUM, IROpcode.MAXIMUM}:
            count(1, 2); same(result_types + operand_types, opcode.value)
            if result_types[0] in {IRType.STRING, IRType.REFERENCE, IRType.BYTES, IRType.TEXT, IRType.VECTOR}:
                self.fail("invalid_arithmetic_type", "arithmetic requires a scalar value", function_id=function_id, instruction_id=instruction.id)
            if opcode in {IROpcode.NUMERIC_DIFFERENCE, IROpcode.MULTIPLY, IROpcode.DIVIDE} and result_types[0] not in {IRType.I64, IRType.F64}:
                self.fail("invalid_numeric_type", f"{opcode.value} requires i64 or f64", function_id=function_id, instruction_id=instruction.id)
            if opcode in {IROpcode.MINIMUM, IROpcode.MAXIMUM} and result_types[0] in {IRType.I64, IRType.F64}:
                self.fail("invalid_ternary_type", f"{opcode.value} requires a ternary type", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.RELATE:
            count(1, 2); same(operand_types, "relate operands")
            if result_types[0] is not IRType.TRIT or operand_types[0] not in {IRType.TRIT, IRType.TRYTE, IRType.I64, IRType.F64} or not isinstance(instruction.immediate, int) or instruction.immediate not in range(6):
                self.fail("invalid_relate", "relate has invalid relation contract", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.CONVERT:
            count(1, 1)
            if (operand_types[0], result_types[0]) not in {
                (IRType.TRIT, IRType.I64), (IRType.TRYTE, IRType.I64), (IRType.TRIT, IRType.F64),
                (IRType.TRYTE, IRType.F64), (IRType.I64, IRType.F64), (IRType.I64, IRType.TRYTE),
            }:
                self.fail("invalid_conversion", "unsupported conversion", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.COMPARE:
            count(1, 2); same(operand_types, "compare operands")
            if result_types[0] is not IRType.TRIT or operand_types[0] in {IRType.STRING, IRType.BYTES, IRType.TEXT, IRType.VECTOR, IRType.REFERENCE}:
                self.fail("invalid_compare", "compare has invalid types", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.CALL:
            signature = None
            if instruction.callee_function_id is not None:
                callee = self.functions_by_id.get(instruction.callee_function_id)
                if callee is None:
                    self.fail("unknown_callee", "call references unknown function", function_id=function_id, instruction_id=instruction.id)
                signature = (self._function_types(callee), tuple(
                    value.type for value in self._range(self.program.values, callee.value_range, function_id=callee.id, field="callee values")
                ))
                parameters = self._range(self.program.parameters, callee.parameter_range, function_id=callee.id, field="callee parameters")
                parameter_types = tuple(self.program.values.get(parameter.value_id).type for parameter in parameters)  # type: ignore[union-attr]
                expected_params = parameter_types
                expected_results = signature[0]
            elif instruction.callee_builtin is not None:
                builtin = config.capabilities.signature(instruction.callee_builtin)
                if builtin is None:
                    self.fail("unknown_builtin", "call references unknown builtin", function_id=function_id, instruction_id=instruction.id)
                expected_params = builtin.parameters
                expected_results = builtin.results
            else:
                self.fail("missing_callee", "call requires a function or builtin callee", function_id=function_id, instruction_id=instruction.id)
            if operand_types != expected_params or result_types != expected_results:
                self.fail("call_signature", "call signature does not match its authority", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.LOAD:
            count(1, 1)
            memory = self._memory(instruction, memory_ids, function_id)
            if operand_types[0] not in {IRType.TRYTE, IRType.I64} or result_types[0] is not memory.element_type:
                self.fail("invalid_load", "load index or result type is invalid", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.STORE:
            count(0, 2)
            memory = self._memory(instruction, memory_ids, function_id)
            if operand_types[0] not in {IRType.TRYTE, IRType.I64} or operand_types[1] is not memory.element_type or (not memory.mutable and not instruction.initialization):
                self.fail("invalid_store", "store contract is invalid", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.ADDRESS_OF:
            count(1)
            if result_types[0] is not IRType.REFERENCE or len(operand_ids) not in {0, 1} or (instruction.memory_id is None and not operand_ids) or instruction.reference_target is None:
                self.fail("invalid_address_of", "address_of metadata is invalid", function_id=function_id, instruction_id=instruction.id)
            if instruction.memory_id is not None:
                self._memory(instruction, memory_ids, function_id)
            return
        if opcode is IROpcode.REFERENCE_LOAD:
            count(1, 1)
            if operand_types[0] is not IRType.REFERENCE or instruction.reference_target is not result_types[0]:
                self.fail("invalid_reference_load", "reference_load metadata is invalid", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.REFERENCE_STORE:
            count(0, 2)
            if operand_types[0] is not IRType.REFERENCE or instruction.reference_target is not operand_types[1] or not instruction.reference_mutable:
                self.fail("invalid_reference_store", "reference_store metadata is invalid", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.SLICE_LENGTH:
            count(1, 2)
            if result_types[0] is not IRType.I64 or operand_types != (IRType.REFERENCE, IRType.I64) or not instruction.reference_is_slice:
                self.fail("invalid_slice_length", "slice_length metadata is invalid", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.SLICE_LOAD:
            count(1, 3)
            if operand_types[0] is not IRType.REFERENCE or operand_types[1] is not IRType.I64 or operand_types[2] not in {IRType.TRYTE, IRType.I64} or instruction.reference_target is not result_types[0] or not instruction.reference_is_slice:
                self.fail("invalid_slice_load", "slice_load metadata is invalid", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.SLICE_STORE:
            count(0, 4)
            if operand_types[0] is not IRType.REFERENCE or operand_types[1] is not IRType.I64 or operand_types[2] not in {IRType.TRYTE, IRType.I64} or instruction.reference_target is not operand_types[3] or not instruction.reference_is_slice or not instruction.reference_mutable:
                self.fail("invalid_slice_store", "slice_store metadata is invalid", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.RETURN:
            count(0)
            if operand_types != function_result_types:
                self.fail("return_signature", "return operands do not match function results", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.JUMP:
            count(0, 0)
            if len(target_ids) != 1:
                self.fail("jump_targets", "jump requires one target", function_id=function_id, instruction_id=instruction.id)
            return
        if opcode is IROpcode.BRANCH3:
            count(0, 1)
            if operand_types != (IRType.TRIT,) or len(target_ids) != 3:
                self.fail("branch3_contract", "branch3 requires trit selector and three targets", function_id=function_id, instruction_id=instruction.id)
            return
        self.fail("unknown_opcode", f"unsupported opcode {opcode!r}", function_id=function_id, instruction_id=instruction.id)

    def _memory(self, instruction: IRInstruction, memories: dict[int, object], function_id: int) -> object:
        if instruction.memory_id is None or instruction.memory_id not in memories:
            self.fail("unknown_memory", "instruction references unknown memory", function_id=function_id, instruction_id=instruction.id)
        return memories[instruction.memory_id]

    def _verify_cfg(self, function: IRFunction, blocks: Iterable[IRBlock]) -> None:
        for block in blocks:
            instructions = self._range_for_block(block)
            terminator = instructions[-1]
            targets = self._value_ids(terminator.target_range, self.program.targets)
            if terminator.opcode is IROpcode.RETURN:
                successors: list[int] = []
            else:
                successors = list(targets)
            self.successors[block.id] = successors
            for target in successors:
                self.predecessors.setdefault(target, []).append(block.id)
        entry = function.entry_block_id
        assert entry is not None
        stack = [entry]
        while stack:
            current = stack.pop()
            if current in self.reachable:
                continue
            self.reachable.add(current)
            stack.extend(reversed(self.successors.get(current, ())))

    def _verify_dominance(self, function: IRFunction, blocks: Iterable[IRBlock]) -> None:
        function_blocks = {block.id for block in blocks}
        entry = function.entry_block_id
        assert entry is not None
        reachable = self.reachable & function_blocks
        for block_id in sorted(reachable):
            self.dominators[block_id] = {entry} if block_id != entry else {entry}
        changed = True
        while changed:
            changed = False
            for block_id in sorted(reachable - {entry}):
                predecessors = [
                    predecessor
                    for predecessor in self.predecessors.get(block_id, ())
                    if predecessor in reachable
                ]
                if predecessors:
                    candidate = {block_id} | set.intersection(
                        *(self.dominators[predecessor] for predecessor in predecessors)
                    )
                else:
                    candidate = {block_id}
                if candidate != self.dominators[block_id]:
                    self.dominators[block_id] = candidate
                    changed = True
        for block in blocks:
            if block.id not in reachable:
                continue
            for position, instruction in enumerate(self._range_for_block(block)):
                for value_id in self._value_ids(instruction.operand_range, self.program.operands):
                    definition = self.definitions.get(value_id)
                    if definition is None:
                        self.fail("undefined_value", f"value r{value_id} has no definition", function_id=function.id, block_id=block.id, instruction_id=instruction.id)
                    definition_block, definition_position = definition
                    if definition_block == block.id:
                        if definition_position is not None and definition_position >= position:
                            self.fail("use_before_definition", f"value r{value_id} is used before its definition", function_id=function.id, block_id=block.id, instruction_id=instruction.id)
                    elif definition_block not in self.dominators.get(block.id, set()):
                        self.fail("use_not_dominated", f"value r{value_id} is not dominated by its definition", function_id=function.id, block_id=block.id, instruction_id=instruction.id)


def verify_ir_program(program: IRProgram, config: VerifierConfig | None = None) -> VerificationResult:
    return IRVerifierKernel(config).verify(program)


__all__ = [
    "IRVerifierKernel",
    "VerifierConfig",
    "VerificationResult",
    "verify_ir_program",
]
