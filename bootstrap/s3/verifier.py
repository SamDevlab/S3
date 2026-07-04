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

    def verify(self, module: IRModule) -> None:
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
                if instruction.result is None:
                    continue
                if instruction.result not in register_types:
                    self._error(
                        f"instruction defines nonexistent value "
                        f"r{instruction.result}",
                        instruction.location,
                    )
                if instruction.result in definitions:
                    self._error(
                        f"redefinition of r{instruction.result}",
                        instruction.location,
                    )
                definitions[instruction.result] = (block.name, position)
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
            if instruction.result is not None:
                self._error(
                    f"{opcode.value} cannot define a result",
                    instruction.location,
                )

        def require_result() -> tuple[int, IRType]:
            if instruction.result is None:
                self._error(f"{opcode.value} requires a result", instruction.location)
            assert instruction.result is not None
            return instruction.result, register_types[instruction.result]

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

        if opcode is IROpcode.CONST:
            _, result_type = require_result()
            require_operands(0)
            if instruction.immediate is None:
                self._error("const requires an immediate", instruction.location)
            try:
                assert instruction.immediate is not None
                validate(instruction.immediate, WIDTH_MAP[result_type])
            except TernaryRangeError as error:
                self._error(str(error), instruction.location)
            return

        if opcode in {IROpcode.MOVE, IROpcode.INVERT}:
            _, result_type = require_result()
            operand_types = require_operands(1)
            self._require_same_types(
                (result_type, *operand_types),
                opcode.value,
                instruction.location,
            )
            return

        if opcode in {IROpcode.ADD, IROpcode.MINIMUM, IROpcode.MAXIMUM}:
            _, result_type = require_result()
            operand_types = require_operands(2)
            self._require_same_types(
                (result_type, *operand_types),
                opcode.value,
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
            return

        if opcode is IROpcode.CALL:
            _, result_type = require_result()
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
            if result_type is not callee.return_type:
                self._error(
                    f"call result has type {result_type.value}; "
                    f"'{callee.name}' returns {callee.return_type.value}",
                    instruction.location,
                )
            return

        if opcode is IROpcode.LOAD:
            _, result_type = require_result()
            operand_types = require_operands(1)
            memory = self._require_memory(instruction, memory_objects)
            if operand_types[0] is not IRType.TRYTE:
                self._error("load index must have type tryte", instruction.location)
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
            if operand_types[0] is not IRType.TRYTE:
                self._error("store index must have type tryte", instruction.location)
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
            operand_types = require_operands(1)
            if operand_types[0] is not function.return_type:
                self._error(
                    f"return has type {operand_types[0].value}; function "
                    f"returns {function.return_type.value}",
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
