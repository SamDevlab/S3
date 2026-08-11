"""Structural, type, memory, CFG, and dominance verifier for S3 IR."""

from __future__ import annotations

from .diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    S3Error,
    SourceLocation,
)
from .ir import (
    IRFunction,
    IRInstruction,
    IRMemoryObject,
    IRModule,
    IROpcode,
    IRType,
    TERMINATOR_OPCODES,
)
from .ternary import TRYTE_MAX, TernaryRangeError, TernaryWidth, validate
from .numeric import NumericError, validate_f64, validate_i64


class IRVerificationError(S3Error):
    category = "IR verification error"
    diagnostic_category = DiagnosticCategory.VERIFICATION
    diagnostic_code = DiagnosticCode.VERIFY_INVALID_IR
    diagnostic_phase = DiagnosticPhase.VERIFICATION


WIDTH_MAP = {
    IRType.TRIT: TernaryWidth.TRIT,
    IRType.TRYTE: TernaryWidth.TRYTE,
}

Definition = tuple[str, int] | None  # None denotes a parameter.


class IRVerifier:
    def __init__(self) -> None:
        self.current_function: str | None = None
        self.current_block: str | None = None
        self.current_opcode: str | None = None
        self.static_string_ids: set[str] = set()

    def verify(self, module: IRModule) -> None:
        self.static_string_ids = self._collect_static_strings(module)
        functions: dict[str, IRFunction] = {}
        for function in module.functions:
            self.current_function = function.name
            self.current_block = None
            self.current_opcode = None
            if function.name in functions:
                self._error(
                    f"duplicate function '{function.name}'",
                    function.location,
                )
            functions[function.name] = function
        for function in module.functions:
            self._verify_function(function, functions)

    def _collect_static_strings(self, module: IRModule) -> set[str]:
        result: set[str] = set()
        for index, entry in enumerate(module.static_strings):
            if entry.id in result:
                self._error(f"duplicate static string '{entry.id}'", None)
            expected = f"s{index}"
            if entry.id != expected:
                self._error(
                    f"static string '{entry.id}' must be ordered as '{expected}'",
                    None,
                )
            if not isinstance(entry.value, str):
                self._error(f"static string '{entry.id}' has invalid value", None)
            result.add(entry.id)
        return result

    def _verify_function(
        self,
        function: IRFunction,
        functions: dict[str, IRFunction],
    ) -> None:
        self.current_function = function.name
        self.current_block = None
        self.current_opcode = None
        blocks = self._collect_blocks(function)
        self.current_block = None
        register_types = self._collect_registers(function)
        self._verify_result_types(function)
        memory_objects = self._collect_memory(function)
        definitions = self._collect_definitions(function, register_types)

        self.current_block = None
        self.current_opcode = None
        for block in function.blocks:
            self.current_block = block.name
            for instruction in block.instructions:
                self.current_opcode = (
                    instruction.opcode.value
                    if isinstance(instruction.opcode, IROpcode)
                    else str(instruction.opcode)
                )
                self._verify_instruction(
                    instruction,
                    function,
                    functions,
                    set(blocks),
                    register_types,
                    memory_objects,
                )

        self.current_block = None
        self.current_opcode = None
        undefined = sorted(set(register_types) - definitions.keys())
        if undefined:
            rendered = ", ".join(f"r{register}" for register in undefined)
            self._error(
                f"function '{function.name}' has values without definitions: "
                f"{rendered}",
                function.location,
            )

        reachable, dominators = self._compute_dominators(function, blocks)
        self._verify_uses_dominate(
            function,
            definitions,
            reachable,
            dominators,
        )
        self.current_block = None
        self.current_opcode = None

    def _collect_blocks(self, function: IRFunction) -> dict[str, object]:
        blocks: dict[str, object] = {}
        for block in function.blocks:
            if block.name in blocks:
                self._error(
                    f"function '{function.name}' has duplicate block "
                    f"'{block.name}'",
                    block.location,
                )
            blocks[block.name] = block
        if "entry" not in blocks:
            self._error(
                f"function '{function.name}' has no entry block",
                function.location,
            )
        for block in function.blocks:
            self._verify_block_shape(function, block.name, block.instructions)
        return blocks

    def _collect_registers(self, function: IRFunction) -> dict[int, IRType]:
        register_types: dict[int, IRType] = {}
        for register in function.registers:
            if register.index in register_types:
                self._error(
                    f"duplicate value r{register.index}",
                    register.location,
                )
            if not isinstance(register.type, IRType):
                self._error(
                    f"invalid type for r{register.index}",
                    register.location,
                )
            register_types[register.index] = register.type
        return register_types

    def _verify_result_types(self, function: IRFunction) -> None:
        if not function.result_types:
            self._error(
                f"function '{function.name}' has no result types",
                function.location,
            )
        for index, result_type in enumerate(function.result_types):
            if not isinstance(result_type, IRType):
                self._error(
                    f"function '{function.name}' result cell {index} has invalid type",
                    function.location,
                )
            if result_type is IRType.REFERENCE:
                self._error(
                    "reference return values are not supported",
                    function.location,
                )

    def _collect_memory(
        self,
        function: IRFunction,
    ) -> dict[int, IRMemoryObject]:
        result: dict[int, IRMemoryObject] = {}
        for memory in function.memory_objects:
            if memory.index in result:
                self._error(
                    f"duplicate memory object m{memory.index}",
                    memory.location,
                )
            if not isinstance(memory.element_type, IRType):
                self._error(
                    f"memory object m{memory.index} has invalid element type",
                    memory.location,
                )
            if memory.element_type is IRType.REFERENCE:
                self._error(
                    "memory objects cannot contain references",
                    memory.location,
                )
            if memory.length <= 0:
                self._error(
                    f"memory object m{memory.index} has invalid length "
                    f"{memory.length}",
                    memory.location,
                )
            if memory.length > TRYTE_MAX + 1:
                self._error(
                    f"memory object m{memory.index} length {memory.length} "
                    f"exceeds indexable maximum {TRYTE_MAX + 1}",
                    memory.location,
                )
            result[memory.index] = memory
        return result

    def _collect_definitions(
        self,
        function: IRFunction,
        register_types: dict[int, IRType],
    ) -> dict[int, Definition]:
        definitions: dict[int, Definition] = {}
        parameter_names: set[str] = set()
        for parameter in function.parameters:
            if parameter.name in parameter_names:
                self._error(
                    f"duplicate IR parameter '{parameter.name}'",
                    parameter.location,
                )
            parameter_names.add(parameter.name)
            if register_types.get(parameter.register) is not parameter.type:
                self._error(
                    f"parameter '{parameter.name}' does not match register "
                    f"r{parameter.register}",
                    parameter.location,
                )
            if parameter.register in definitions:
                self._error(
                    f"redefinition of r{parameter.register}",
                    parameter.location,
                )
            definitions[parameter.register] = None

        for block in function.blocks:
            self.current_block = block.name
            for position, instruction in enumerate(block.instructions):
                self.current_opcode = (
                    instruction.opcode.value
                    if isinstance(instruction.opcode, IROpcode)
                    else str(instruction.opcode)
                )
                if not instruction.results:
                    continue
                for result in instruction.results:
                    if result not in register_types:
                        self._error(
                            f"instruction defines nonexistent value r{result}",
                            instruction.location,
                        )
                    if result in definitions:
                        self._error(
                            f"redefinition of r{result}",
                            instruction.location,
                        )
                    definitions[result] = (block.name, position)
        self.current_block = None
        self.current_opcode = None
        return definitions

    def _verify_block_shape(
        self,
        function: IRFunction,
        block_name: str,
        instructions: tuple[IRInstruction, ...],
    ) -> None:
        self.current_block = block_name
        self.current_opcode = None
        terminator_indices = [
            index
            for index, instruction in enumerate(instructions)
            if isinstance(instruction.opcode, IROpcode)
            and instruction.opcode in TERMINATOR_OPCODES
        ]
        if not terminator_indices:
            self._error(
                f"block '{block_name}' in function '{function.name}' "
                "has no terminator",
                function.location,
            )
        first = terminator_indices[0]
        if first != len(instructions) - 1:
            self._error(
                f"block '{block_name}' has an instruction after its terminator",
                instructions[first + 1].location,
            )
        if len(terminator_indices) != 1:
            self._error(
                f"block '{block_name}' has multiple terminators",
                instructions[terminator_indices[1]].location,
            )

    def _verify_instruction(
        self,
        instruction: IRInstruction,
        function: IRFunction,
        functions: dict[str, IRFunction],
        block_names: set[str],
        register_types: dict[int, IRType],
        memory_objects: dict[int, IRMemoryObject],
    ) -> None:
        if not isinstance(instruction.opcode, IROpcode):
            name = str(instruction.opcode).lower()
            if "sub" in name:
                self._error(
                    "subtraction opcode is forbidden after lowering",
                    instruction.location,
                )
            if any(part in name for part in ("ptr", "address", "cast")):
                self._error(
                    "pointer/address opcodes are not supported",
                    instruction.location,
                )
            self._error(f"unknown IR opcode '{instruction.opcode}'", instruction.location)
        opcode = instruction.opcode

        def require_no_result() -> None:
            if instruction.results:
                self._error(
                    f"{opcode.value} cannot define a result",
                    instruction.location,
                )

        def require_result() -> tuple[int, IRType]:
            if len(instruction.results) != 1:
                self._error(f"{opcode.value} requires a result", instruction.location)
            result = instruction.results[0]
            return result, register_types[result]

        def require_operands(count: int) -> tuple[IRType, ...]:
            if len(instruction.operands) != count:
                self._error(
                    f"{opcode.value} expects {count} operand(s), got "
                    f"{len(instruction.operands)}",
                    instruction.location,
                )
            types: list[IRType] = []
            for operand in instruction.operands:
                try:
                    types.append(register_types[operand])
                except KeyError:
                    self._error(
                        f"use of nonexistent value r{operand}",
                        instruction.location,
                    )
            return tuple(types)

        if opcode is IROpcode.ADDRESS_OF:
            result, result_type = require_result()
            if result_type is not IRType.REFERENCE:
                self._error("address_of result must be a reference", instruction.location)
            if instruction.reference_target not in {IRType.TRIT, IRType.TRYTE, IRType.I64, IRType.F64, IRType.STRING}:
                self._error("address_of requires a scalar reference target", instruction.location)
            if len(instruction.operands) not in {0, 1} or instruction.memory is None and not instruction.operands:
                self._error("address_of requires a logical storage operand", instruction.location)
            if instruction.memory is not None:
                self._require_memory(instruction, memory_objects)
                if len(instruction.operands) == 1 and register_types[instruction.operands[0]] not in {IRType.TRYTE, IRType.I64}:
                    self._error("address_of array index must be a tryte or i64", instruction.location)
            if instruction.operands:
                if register_types[instruction.operands[0]] is IRType.REFERENCE:
                    self._error("address_of cannot target a reference", instruction.location)
            return

        if opcode is IROpcode.SLICE_LENGTH:
            result, result_type = require_result()
            operand_types = require_operands(1)
            if result_type is not IRType.I64 or operand_types[0] is not IRType.REFERENCE:
                self._error("slice_length requires a reference and returns i64", instruction.location)
            ref = next(register for register in function.registers if register.index == instruction.operands[0])
            if not ref.reference_is_slice:
                self._error("slice_length requires a slice reference", instruction.location)
            return

        if opcode is IROpcode.SLICE_LOAD:
            _, result_type = require_result()
            operand_types = require_operands(3)
            if operand_types[0] is not IRType.REFERENCE or operand_types[1] is not IRType.I64 or operand_types[2] not in {IRType.TRYTE, IRType.I64}:
                self._error("slice_load requires a slice reference and index", instruction.location)
            if instruction.reference_target is not result_type:
                self._error("slice_load result does not match element type", instruction.location)
            ref = next(register for register in function.registers if register.index == instruction.operands[0])
            if not ref.reference_is_slice:
                self._error("slice_load requires a slice reference", instruction.location)
            return

        if opcode is IROpcode.SLICE_STORE:
            require_no_result()
            operand_types = require_operands(4)
            if operand_types[0] is not IRType.REFERENCE or operand_types[1] is not IRType.I64 or operand_types[2] not in {IRType.TRYTE, IRType.I64}:
                self._error("slice_store requires a slice reference and index", instruction.location)
            ref = next(register for register in function.registers if register.index == instruction.operands[0])
            if not ref.reference_is_slice or not ref.reference_mutable:
                self._error("slice_store requires a mutable slice reference", instruction.location)
            if instruction.reference_target is not operand_types[3]:
                self._error("slice_store value does not match element type", instruction.location)
            return

        if opcode is IROpcode.REFERENCE_LOAD:
            _, result_type = require_result()
            operand_types = require_operands(1)
            if operand_types[0] is not IRType.REFERENCE:
                self._error("reference_load requires a reference operand", instruction.location)
            if instruction.reference_target is not None and result_type is not instruction.reference_target:
                self._error("reference_load result does not match target type", instruction.location)
            return

        if opcode is IROpcode.REFERENCE_STORE:
            require_no_result()
            operand_types = require_operands(2)
            if operand_types[0] is not IRType.REFERENCE:
                self._error("reference_store requires a reference operand", instruction.location)
            reference_register = next(
                register for register in function.registers
                if register.index == instruction.operands[0]
            )
            if not reference_register.reference_mutable or instruction.reference_mutable is False:
                self._error("reference_store requires a mutable reference", instruction.location)
            if instruction.reference_target is not None and reference_register.reference_target is not instruction.reference_target:
                self._error("reference_store target type does not match reference", instruction.location)
            if len(instruction.operands) == 2 and instruction.operands[1] in register_types:
                value_type = register_types[instruction.operands[1]]
                if instruction.reference_target is not None and value_type is not instruction.reference_target:
                    self._error("reference_store value does not match target type", instruction.location)
            return

        if opcode is IROpcode.CONST:
            _, result_type = require_result()
            require_operands(0)
            if result_type is IRType.STRING:
                self._error("const cannot produce string values", instruction.location)
            if result_type is IRType.REFERENCE:
                self._error("const cannot produce reference values", instruction.location)
            if instruction.immediate is None:
                self._error("const requires an immediate", instruction.location)
            if instruction.static_string is not None:
                self._error("const must not have a static string id", instruction.location)
            try:
                assert instruction.immediate is not None
                if result_type is IRType.I64:
                    validate_i64(instruction.immediate)
                elif result_type is IRType.F64:
                    validate_f64(instruction.immediate)
                else:
                    validate(instruction.immediate, WIDTH_MAP[result_type])
            except (TernaryRangeError, NumericError, TypeError, ValueError) as error:
                self._error(str(error), instruction.location)
            return

        if opcode is IROpcode.CONST_STR:
            _, result_type = require_result()
            require_operands(0)
            if result_type is not IRType.STRING:
                self._error("const_str result must have type string", instruction.location)
            if instruction.static_string is None:
                self._error("const_str requires a static string id", instruction.location)
            if instruction.static_string not in self.static_string_ids:
                self._error(
                    f"const_str references unknown static string "
                    f"'{instruction.static_string}'",
                    instruction.location,
                )
            if instruction.immediate is not None:
                self._error("const_str must not have an immediate", instruction.location)
            return

        if opcode is IROpcode.MOVE:
            _, result_type = require_result()
            operand_types = require_operands(1)
            self._require_same_types(
                (result_type, *operand_types),
                opcode.value,
                instruction.location,
            )
            return

        if opcode is IROpcode.INVERT:
            _, result_type = require_result()
            operand_types = require_operands(1)
            self._require_same_types(
                (result_type, *operand_types),
                opcode.value,
                instruction.location,
            )
            if result_type is IRType.STRING:
                self._error("invert does not support string values", instruction.location)
            if result_type is IRType.REFERENCE:
                self._error("invert does not support reference values", instruction.location)
            return

        if opcode in {
            IROpcode.ADD,
            IROpcode.NUMERIC_DIFFERENCE,
            IROpcode.MULTIPLY,
            IROpcode.DIVIDE,
            IROpcode.MINIMUM,
            IROpcode.MAXIMUM,
        }:
            _, result_type = require_result()
            operand_types = require_operands(2)
            self._require_same_types(
                (result_type, *operand_types),
                opcode.value,
                instruction.location,
            )
            if result_type in {IRType.STRING, IRType.REFERENCE}:
                self._error(
                    f"{opcode.value} does not support {result_type.value} values",
                    instruction.location,
                )
            if (
                opcode in {IROpcode.NUMERIC_DIFFERENCE, IROpcode.MULTIPLY, IROpcode.DIVIDE}
                and result_type not in {IRType.I64, IRType.F64}
            ):
                self._error(f"{opcode.value} requires i64 or f64 values", instruction.location)
            if (
                opcode in {IROpcode.MINIMUM, IROpcode.MAXIMUM}
                and result_type in {IRType.I64, IRType.F64}
            ):
                self._error(f"{opcode.value} is balanced-ternary only", instruction.location)
            return

        if opcode is IROpcode.RELATE:
            _, result_type = require_result()
            operand_types = require_operands(2)
            if result_type is not IRType.TRIT:
                self._error("relate result must have type trit", instruction.location)
            self._require_same_types(operand_types, "relate operands", instruction.location)
            if not operand_types or operand_types[0] not in {
                IRType.TRIT, IRType.TRYTE, IRType.I64, IRType.F64
            }:
                self._error("relate requires scalar numeric operands", instruction.location)
            if not isinstance(instruction.immediate, int) or instruction.immediate not in range(6):
                self._error("relate requires relation code 0..5", instruction.location)
            return

        if opcode is IROpcode.CONVERT:
            _, result_type = require_result()
            operand_types = require_operands(1)
            source_type = operand_types[0]
            allowed = {
                (IRType.TRIT, IRType.I64),
                (IRType.TRYTE, IRType.I64),
                (IRType.TRIT, IRType.F64),
                (IRType.TRYTE, IRType.F64),
                (IRType.I64, IRType.F64),
                (IRType.I64, IRType.TRYTE),
            }
            if (source_type, result_type) not in allowed:
                self._error(
                    f"unsupported explicit conversion {source_type.value} -> {result_type.value}",
                    instruction.location,
                )
            return

        if opcode is IROpcode.COMPARE:
            _, result_type = require_result()
            operand_types = require_operands(2)
            if result_type is not IRType.TRIT:
                self._error("compare result must have type trit", instruction.location)
            self._require_same_types(
                operand_types,
                "compare operands",
                instruction.location,
            )
            if operand_types and operand_types[0] is IRType.STRING:
                self._error("compare does not support string values", instruction.location)
            if operand_types and operand_types[0] is IRType.REFERENCE:
                self._error("compare does not support reference values", instruction.location)
            return

        if opcode is IROpcode.CALL:
            operand_types = require_operands(len(instruction.operands))
            if instruction.callee is None:
                self._error("call requires a function name", instruction.location)
            callee = functions.get(instruction.callee or "")
            if callee is None:
                self._error(
                    f"call to nonexistent function '{instruction.callee}'",
                    instruction.location,
                )
            assert callee is not None
            expected_types = tuple(parameter.type for parameter in callee.parameters)
            if len(operand_types) != len(expected_types):
                self._error(
                    f"call to '{callee.name}' expects {len(expected_types)} "
                    f"argument(s), got {len(operand_types)}",
                    instruction.location,
                )
            if operand_types != expected_types:
                self._error(
                    f"call to '{callee.name}' has incompatible argument types",
                    instruction.location,
                )
            if instruction.results:
                if len(instruction.results) != len(callee.result_types):
                    self._error(
                        f"call result count {len(instruction.results)} does not "
                        f"match '{callee.name}' result width "
                        f"{len(callee.result_types)}",
                        instruction.location,
                    )
                result_types = tuple(register_types[result] for result in instruction.results)
                if result_types != callee.result_types:
                    rendered = ", ".join(type_name.value for type_name in result_types)
                    expected = ", ".join(type_name.value for type_name in callee.result_types)
                    self._error(
                        f"call results have types [{rendered}]; "
                        f"'{callee.name}' returns [{expected}]",
                        instruction.location,
                    )
            return

        if opcode is IROpcode.LOAD:
            _, result_type = require_result()
            operand_types = require_operands(1)
            memory = self._require_memory(instruction, memory_objects)
            if operand_types[0] not in {IRType.TRYTE, IRType.I64}:
                self._error("load index must have type tryte or i64", instruction.location)
            if result_type is not memory.element_type:
                self._error(
                    f"load result has type {result_type.value}; memory "
                    f"m{memory.index} contains {memory.element_type.value}",
                    instruction.location,
                )
            return

        if opcode is IROpcode.STORE:
            require_no_result()
            operand_types = require_operands(2)
            memory = self._require_memory(instruction, memory_objects)
            if operand_types[0] not in {IRType.TRYTE, IRType.I64}:
                self._error("store index must have type tryte or i64", instruction.location)
            if operand_types[1] is not memory.element_type:
                self._error(
                    f"store value has type {operand_types[1].value}; memory "
                    f"m{memory.index} contains {memory.element_type.value}",
                    instruction.location,
                )
            if not memory.mutable and not instruction.initialization:
                self._error(
                    f"store to immutable memory m{memory.index} is not initialization",
                    instruction.location,
                )
            return

        if opcode is IROpcode.RETURN:
            require_no_result()
            if function.return_type is not function.result_types[0]:
                self._error(
                    f"function '{function.name}' return_type does not match "
                    "first result type",
                    instruction.location,
                )
            operand_types = require_operands(len(instruction.operands))
            if len(operand_types) != len(function.result_types):
                self._error(
                    f"return result count {len(operand_types)} does not match "
                    f"function result width {len(function.result_types)}",
                    instruction.location,
                )
            for index, (actual, expected) in enumerate(
                zip(operand_types, function.result_types, strict=True)
            ):
                if actual is not expected:
                    self._error(
                        f"return cell {index} has type {actual.value}; "
                        f"function result cell is {expected.value}",
                        instruction.location,
                    )
            return

        if opcode is IROpcode.JUMP:
            require_no_result()
            require_operands(0)
            self._verify_targets(instruction, 1, block_names)
            return

        if opcode is IROpcode.BRANCH3:
            require_no_result()
            operand_types = require_operands(1)
            if operand_types[0] is not IRType.TRIT:
                self._error("branch3 condition must be trit", instruction.location)
            self._verify_targets(instruction, 3, block_names)
            if len(set(instruction.targets)) != 3:
                self._error(
                    "branch3 destinations must be distinct",
                    instruction.location,
                )
            return

        self._error(f"unhandled IR opcode '{opcode.value}'", instruction.location)

    def _require_memory(
        self,
        instruction: IRInstruction,
        memory_objects: dict[int, IRMemoryObject],
    ) -> IRMemoryObject:
        if instruction.memory is None:
            self._error(
                f"{instruction.opcode.value} requires a memory object",
                instruction.location,
            )
        try:
            return memory_objects[instruction.memory]  # type: ignore[index]
        except KeyError:
            self._error(
                f"reference to nonexistent memory object m{instruction.memory}",
                instruction.location,
            )

    def _verify_targets(
        self,
        instruction: IRInstruction,
        count: int,
        block_names: set[str],
    ) -> None:
        if len(instruction.targets) != count:
            self._error(
                f"{instruction.opcode.value} expects {count} target(s), got "
                f"{len(instruction.targets)}",
                instruction.location,
            )
        for target in instruction.targets:
            if target not in block_names:
                self._error(
                    f"jump to nonexistent block '{target}'",
                    instruction.location,
                )

    def _compute_dominators(
        self,
        function: IRFunction,
        blocks: dict[str, object],
    ) -> tuple[set[str], dict[str, set[str]]]:
        successors: dict[str, set[str]] = {}
        predecessors: dict[str, set[str]] = {name: set() for name in blocks}
        for block in function.blocks:
            terminator = block.instructions[-1]
            targets = (
                set(terminator.targets)
                if terminator.opcode in {IROpcode.JUMP, IROpcode.BRANCH3}
                else set()
            )
            successors[block.name] = targets
            for target in targets:
                predecessors[target].add(block.name)

        reachable: set[str] = set()
        pending = ["entry"]
        while pending:
            name = pending.pop()
            if name in reachable:
                continue
            reachable.add(name)
            pending.extend(successors[name] - reachable)

        dominators: dict[str, set[str]] = {
            name: ({"entry"} if name == "entry" else set(reachable))
            for name in reachable
        }
        changed = True
        while changed:
            changed = False
            for name in reachable - {"entry"}:
                incoming = predecessors[name] & reachable
                shared = (
                    set.intersection(*(dominators[pred] for pred in incoming))
                    if incoming
                    else set()
                )
                updated = {name} | shared
                if updated != dominators[name]:
                    dominators[name] = updated
                    changed = True
        return reachable, dominators

    def _verify_uses_dominate(
        self,
        function: IRFunction,
        definitions: dict[int, Definition],
        reachable: set[str],
        dominators: dict[str, set[str]],
    ) -> None:
        for block in function.blocks:
            self.current_block = block.name
            for position, instruction in enumerate(block.instructions):
                self.current_opcode = (
                    instruction.opcode.value
                    if isinstance(instruction.opcode, IROpcode)
                    else str(instruction.opcode)
                )
                for operand in instruction.operands:
                    definition = definitions.get(operand)
                    if definition is None:
                        if operand in definitions:  # Parameter.
                            continue
                        self._error(
                            f"use of nonexistent value r{operand}",
                            instruction.location,
                        )
                    assert definition is not None
                    definition_block, definition_position = definition
                    if definition_block == block.name:
                        if definition_position >= position:
                            self._error(
                                f"definition of r{operand} does not precede its use "
                                f"in block '{block.name}'",
                                instruction.location,
                            )
                        continue
                    if block.name not in reachable:
                        self._error(
                            f"definition of r{operand} does not dominate "
                            f"unreachable block '{block.name}'",
                            instruction.location,
                        )
                    if definition_block not in dominators[block.name]:
                        self._error(
                            f"definition of r{operand} in block "
                            f"'{definition_block}' does not dominate block "
                            f"'{block.name}'",
                            instruction.location,
                        )

    def _require_same_types(
        self,
        types: tuple[IRType, ...],
        subject: str,
        location: SourceLocation | None,
    ) -> None:
        if types and any(type_name is not types[0] for type_name in types[1:]):
            rendered = ", ".join(type_name.value for type_name in types)
            self._error(f"{subject} type mismatch ({rendered})", location)

    def _error(self, message: str, location: SourceLocation | None) -> None:
        raise IRVerificationError(
            message,
            location,
            diagnostic_context={
                "function": self.current_function,
                "block": self.current_block,
                "opcode": self.current_opcode,
            },
        )


def verify_ir(module: IRModule) -> None:
    IRVerifier().verify(module)
