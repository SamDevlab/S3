"""Standalone structural and type verifier for block-based S3 IR."""

from __future__ import annotations

from .diagnostics import S3Error, SourceLocation
from .ir import (
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRType,
    TERMINATOR_OPCODES,
)
from .ternary import TernaryRangeError, TernaryWidth, validate


class IRVerificationError(S3Error):
    category = "IR verification error"


WIDTH_MAP = {
    IRType.TRIT: TernaryWidth.TRIT,
    IRType.TRYTE: TernaryWidth.TRYTE,
}


class IRVerifier:
    def verify(self, module: IRModule) -> None:
        functions: dict[str, IRFunction] = {}
        for function in module.functions:
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
        block_names: set[str] = set()
        for block in function.blocks:
            if block.name in block_names:
                self._error(
                    f"function '{function.name}' has duplicate block "
                    f"'{block.name}'",
                    block.location,
                )
            block_names.add(block.name)
        if "entry" not in block_names:
            self._error(
                f"function '{function.name}' has no entry block",
                function.location,
            )

        register_types: dict[int, IRType] = {}
        for register in function.registers:
            if register.index in register_types:
                self._error(
                    f"duplicate value r{register.index}",
                    register.location,
                )
            register_types[register.index] = register.type

        definitions: set[int] = set()
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
            definitions.add(parameter.register)

        for block in function.blocks:
            self._verify_block_shape(function, block.name, block.instructions)
            for instruction in block.instructions:
                if instruction.result is not None:
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
                    definitions.add(instruction.result)

        for block in function.blocks:
            for instruction in block.instructions:
                self._verify_instruction(
                    instruction,
                    function,
                    functions,
                    block_names,
                    register_types,
                )

        undefined = sorted(set(register_types) - definitions)
        if undefined:
            rendered = ", ".join(f"r{register}" for register in undefined)
            self._error(
                f"function '{function.name}' has values without definitions: "
                f"{rendered}",
                function.location,
            )

    def _verify_block_shape(
        self,
        function: IRFunction,
        block_name: str,
        instructions: tuple[IRInstruction, ...],
    ) -> None:
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
    ) -> None:
        if not isinstance(instruction.opcode, IROpcode):
            name = str(instruction.opcode).lower()
            if "sub" in name:
                self._error(
                    "subtraction opcode is forbidden after lowering",
                    instruction.location,
                )
            self._error(f"unknown IR opcode '{instruction.opcode}'", instruction.location)
        opcode = instruction.opcode

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
                self._error(
                    "compare result must have type trit",
                    instruction.location,
                )
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

        if opcode is IROpcode.RETURN:
            if instruction.result is not None:
                self._error("return cannot define a result", instruction.location)
            operand_types = require_operands(1)
            if operand_types[0] is not function.return_type:
                self._error(
                    f"return has type {operand_types[0].value}; function "
                    f"returns {function.return_type.value}",
                    instruction.location,
                )
            return

        if opcode is IROpcode.JUMP:
            require_operands(0)
            self._verify_targets(instruction, 1, block_names)
            return

        if opcode is IROpcode.BRANCH3:
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

    def _require_same_types(
        self,
        types: tuple[IRType, ...],
        subject: str,
        location: SourceLocation | None,
    ) -> None:
        if types and any(type_name is not types[0] for type_name in types[1:]):
            rendered = ", ".join(type_name.value for type_name in types)
            self._error(f"{subject} type mismatch ({rendered})", location)

    @staticmethod
    def _error(message: str, location: SourceLocation | None) -> None:
        raise IRVerificationError(message, location)


def verify_ir(module: IRModule) -> None:
    IRVerifier().verify(module)

