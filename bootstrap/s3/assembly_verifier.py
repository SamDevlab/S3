"""Structural validation for typed, labelled S3 Assembly."""

from __future__ import annotations

from .diagnostics import DiagnosticCategory, DiagnosticCode, DiagnosticPhase, SourceLocation
from .assembly import (
    ASSEMBLY_FORMAT_VERSION,
    AssemblyBlock,
    AssemblyError,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyMemoryObject,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
    TERMINATOR_OPCODES,
)
from .ternary import TernaryRangeError, TernaryWidth, TRYTE_MAX, validate
from .numeric import NumericError, validate_f64, validate_i64


WIDTH_MAP = {
    AssemblyType.TRIT: TernaryWidth.TRIT,
    AssemblyType.TRYTE: TernaryWidth.TRYTE,
}


class AssemblyVerifierError(AssemblyError):
    """Raised when Assembly violates a structural invariant."""

    diagnostic_category = DiagnosticCategory.VERIFICATION
    diagnostic_code = DiagnosticCode.ASSEMBLY_INVALID_PROGRAM
    diagnostic_phase = DiagnosticPhase.EMULATION

    def __init__(
        self,
        message: str,
        *,
        diagnostic_message: str | None = None,
        diagnostic_category: DiagnosticCategory | None = None,
        diagnostic_code: DiagnosticCode | None = None,
        diagnostic_context: dict[str, object] | None = None,
        location: SourceLocation | None = None,
    ) -> None:
        self.message = message
        self.diagnostic_message = diagnostic_message or message
        self.location = location
        if diagnostic_category is not None:
            self.diagnostic_category = diagnostic_category
        if diagnostic_code is not None:
            self.diagnostic_code = diagnostic_code
        self.diagnostic_context = dict(diagnostic_context or {})
        super().__init__(message)


EmulatorError = AssemblyVerifierError


class AssemblyVerifier:
    """Validates Assembly without executing it or requiring emulator state."""

    def __init__(self, *, max_memory_trits: int = 6561) -> None:
        if max_memory_trits < 1:
            raise ValueError("max_memory_trits must be at least 1")
        self.max_memory_trits = max_memory_trits

    def validate(
        self,
        program: AssemblyProgram,
        *,
        entry: str | None = None,
    ) -> None:
        functions = self._validate_program(program)
        for function in program.functions:
            self._validate_memory_budget(function)
        if entry is not None:
            try:
                entry_function = functions[entry]
            except KeyError as error:
                raise AssemblyVerifierError(
                    f"entry function '{entry}' was not found"
                ) from error
            if entry_function.parameters:
                raise AssemblyVerifierError(
                    f"entry function '{entry}' must not declare parameters"
                )

    @staticmethod
    def _static_context(
        function: AssemblyFunction,
        block: AssemblyBlock,
        instruction: AssemblyInstruction,
        message: str,
    ) -> str:
        pieces = [
            f"function '{function.name}'",
            f"block '{block.label}'",
            instruction.opcode.value,
        ]
        if instruction.line is not None:
            pieces.append(f"assembly line {instruction.line}")
        if instruction.source is not None:
            pieces.append(
                f"source {instruction.source.line}:{instruction.source.column}"
            )
        return f"{', '.join(pieces)}: {message}"

    def _validate_program(
        self,
        program: AssemblyProgram,
    ) -> dict[str, AssemblyFunction]:
        if program.version != ASSEMBLY_FORMAT_VERSION:
            raise EmulatorError(
                f"unsupported S3 Assembly version {program.version}; "
                f"expected {ASSEMBLY_FORMAT_VERSION}"
            )
        static_string_ids = self._validate_static_strings(program)
        functions: dict[str, AssemblyFunction] = {}
        for function in program.functions:
            if function.name in functions:
                raise EmulatorError(f"duplicate function '{function.name}'")
            functions[function.name] = function
        for function in program.functions:
            self._validate_function(function, functions, static_string_ids)
        return functions

    def _validate_static_strings(self, program: AssemblyProgram) -> set[str]:
        result: set[str] = set()
        for index, entry in enumerate(program.static_strings):
            if entry.id in result:
                raise EmulatorError(f"duplicate static string '{entry.id}'")
            expected = f"s{index}"
            if entry.id != expected:
                raise EmulatorError(
                    f"static string '{entry.id}' must be ordered as '{expected}'"
                )
            if not isinstance(entry.value, str):
                raise EmulatorError(f"static string '{entry.id}' has invalid value")
            result.add(entry.id)
        return result

    def _validate_function(
        self,
        function: AssemblyFunction,
        functions: dict[str, AssemblyFunction],
        static_string_ids: set[str],
    ) -> None:
        declared_types: dict[int, AssemblyType] = {}
        for parameter in function.parameters:
            if parameter.register in declared_types:
                raise EmulatorError(
                    f"function '{function.name}': duplicate register "
                    f"r{parameter.register}"
                )
            declared_types[parameter.register] = parameter.type
        for register, type_name in function.register_types:
            if register in declared_types:
                raise EmulatorError(
                    f"function '{function.name}': duplicate register r{register}"
                )
            declared_types[register] = type_name

        memory_objects: dict[int, AssemblyMemoryObject] = {}
        for memory in function.memory_objects:
            if memory.index in memory_objects:
                raise EmulatorError(
                    f"function '{function.name}': duplicate memory object "
                    f"m{memory.index}"
                )
            if memory.length <= 0:
                raise EmulatorError(
                    f"function '{function.name}': memory object m{memory.index} "
                    f"has invalid length {memory.length}"
                )
            if memory.length > TRYTE_MAX + 1:
                raise EmulatorError(
                    f"function '{function.name}': memory object m{memory.index} "
                    f"length {memory.length} exceeds indexable maximum "
                    f"{TRYTE_MAX + 1}"
                )
            memory_objects[memory.index] = memory

        blocks: dict[str, AssemblyBlock] = {}
        for block in function.blocks:
            if block.label in blocks:
                raise EmulatorError(
                    f"function '{function.name}': duplicate label "
                    f"'{block.label}'"
                )
            blocks[block.label] = block
        if "entry" not in blocks:
            raise EmulatorError(
                f"function '{function.name}' has no entry label"
            )

        for block in function.blocks:
            terminators = [
                index
                for index, instruction in enumerate(block.instructions)
                if instruction.opcode in TERMINATOR_OPCODES
            ]
            if not terminators:
                raise EmulatorError(
                    f"function '{function.name}', block '{block.label}' "
                    "has no terminator"
                )
            if terminators[0] != len(block.instructions) - 1:
                offending = block.instructions[terminators[0] + 1]
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        offending,
                        "instruction after terminator",
                    )
                )
            if len(terminators) != 1:
                raise EmulatorError(
                    f"function '{function.name}', block '{block.label}' "
                    "has multiple terminators"
                )
            for instruction in block.instructions:
                self._validate_instruction(
                    function,
                    block,
                    instruction,
                    declared_types,
                    memory_objects,
                    blocks,
                    functions,
                    static_string_ids,
                )
        if not any(
            instruction.opcode is AssemblyOpcode.TRET
            for block in function.blocks
            for instruction in block.instructions
        ):
            raise EmulatorError(
                f"function '{function.name}' has no TRET instruction"
            )

    def _validate_instruction(
        self,
        function: AssemblyFunction,
        block: AssemblyBlock,
        instruction: AssemblyInstruction,
        types: dict[int, AssemblyType],
        memory_objects: dict[int, AssemblyMemoryObject],
        blocks: dict[str, AssemblyBlock],
        functions: dict[str, AssemblyFunction],
        static_string_ids: set[str],
    ) -> None:
        def register_type(register: int) -> AssemblyType:
            try:
                return types[register]
            except KeyError as error:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"invalid register r{register}",
                    )
                ) from error

        def same_type(registers: tuple[int, ...]) -> AssemblyType:
            register_types = tuple(register_type(register) for register in registers)
            if any(
                type_name is not register_types[0]
                for type_name in register_types[1:]
            ):
                rendered = ", ".join(
                    f"r{register}:{type_name.value}"
                    for register, type_name in zip(
                        registers,
                        register_types,
                        strict=True,
                    )
                )
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"register type mismatch ({rendered})",
                    )
                )
            return register_types[0]

        opcode = instruction.opcode
        if opcode is AssemblyOpcode.TCONST:
            type_name = register_type(instruction.registers[0])
            if type_name is AssemblyType.STRING:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TCONST destination must not be a string register",
                    )
                )
            assert instruction.immediate is not None
            try:
                if type_name is AssemblyType.I64:
                    validate_i64(instruction.immediate)
                elif type_name is AssemblyType.F64:
                    validate_f64(instruction.immediate)
                else:
                    validate(instruction.immediate, WIDTH_MAP[type_name])
            except (TernaryRangeError, NumericError, TypeError, ValueError) as error:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        str(error),
                    )
                ) from error
        elif opcode is AssemblyOpcode.TCONST_STR:
            type_name = register_type(instruction.registers[0])
            if type_name is not AssemblyType.STRING:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TCONST_STR destination must be a string register",
                    )
                )
            if instruction.static_string is None:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TCONST_STR requires a static string id",
                    )
                )
            if instruction.static_string not in static_string_ids:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"TCONST_STR references unknown static string "
                        f"'{instruction.static_string}'",
                    )
                )
        elif opcode is AssemblyOpcode.TMOV:
            same_type(instruction.registers)
        elif opcode is AssemblyOpcode.TADDR:
            destination = instruction.registers[0]
            if register_type(destination) is not AssemblyType.REFERENCE:
                raise EmulatorError(self._static_context(function, block, instruction, "TADDR destination must be a reference"))
            if instruction.memory is not None:
                if instruction.memory not in memory_objects:
                    raise EmulatorError(self._static_context(function, block, instruction, "TADDR references unknown memory"))
                if len(instruction.registers) not in {1, 2}:
                    raise EmulatorError(self._static_context(function, block, instruction, "TADDR memory form requires a destination and optional index"))
                if len(instruction.registers) == 2 and register_type(instruction.registers[1]) not in {AssemblyType.TRYTE, AssemblyType.I64}:
                    raise EmulatorError(self._static_context(function, block, instruction, "TADDR array index must be a tryte or i64"))
                source_type = memory_objects[instruction.memory].element_type
            else:
                if len(instruction.registers) != 2:
                    raise EmulatorError(self._static_context(function, block, instruction, "TADDR requires a direct register source"))
                source_type = register_type(instruction.registers[1])
                if source_type is AssemblyType.REFERENCE:
                    raise EmulatorError(self._static_context(function, block, instruction, "TADDR source must be a direct value storage"))
            if instruction.reference_target is not source_type:
                raise EmulatorError(self._static_context(function, block, instruction, "TADDR target type mismatch"))
        elif opcode is AssemblyOpcode.TREFLOAD:
            destination, reference = instruction.registers
            if register_type(reference) is not AssemblyType.REFERENCE:
                raise EmulatorError(self._static_context(function, block, instruction, "TREFLOAD source must be a reference"))
            if instruction.reference_target is None or register_type(destination) is not instruction.reference_target:
                raise EmulatorError(self._static_context(function, block, instruction, "TREFLOAD target type mismatch"))
        elif opcode is AssemblyOpcode.TREFSTORE:
            reference, source = instruction.registers
            if register_type(reference) is not AssemblyType.REFERENCE:
                raise EmulatorError(self._static_context(function, block, instruction, "TREFSTORE destination must be a reference"))
            info = function.reference_info(reference)
            if info is None or not info[1] or not instruction.reference_mutable:
                raise EmulatorError(self._static_context(function, block, instruction, "TREFSTORE requires a mutable reference"))
            if instruction.reference_target is None or register_type(source) is not instruction.reference_target:
                raise EmulatorError(self._static_context(function, block, instruction, "TREFSTORE source type mismatch"))
        elif opcode is AssemblyOpcode.TINV:
            type_name = same_type(instruction.registers)
            if type_name is AssemblyType.STRING:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TINV does not support string values",
                    )
                )
            if type_name is AssemblyType.REFERENCE:
                raise EmulatorError(self._static_context(function, block, instruction, "TINV does not support references"))
        elif opcode in {
            AssemblyOpcode.TADD,
            AssemblyOpcode.TNSUB,
            AssemblyOpcode.TMUL,
            AssemblyOpcode.TDIV,
            AssemblyOpcode.TMIN,
            AssemblyOpcode.TMAX,
        }:
            type_name = same_type(instruction.registers)
            if type_name is AssemblyType.STRING:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"{opcode.value} does not support string values",
                    )
                )
            if type_name is AssemblyType.REFERENCE:
                raise EmulatorError(self._static_context(function, block, instruction, f"{opcode.value} does not support references"))
            if (
                opcode in {AssemblyOpcode.TNSUB, AssemblyOpcode.TMUL, AssemblyOpcode.TDIV}
                and type_name not in {AssemblyType.I64, AssemblyType.F64}
            ):
                raise EmulatorError(self._static_context(function, block, instruction, f"{opcode.value} requires i64 or f64 values"))
            if (
                opcode in {AssemblyOpcode.TMIN, AssemblyOpcode.TMAX}
                and type_name in {AssemblyType.I64, AssemblyType.F64}
            ):
                raise EmulatorError(self._static_context(function, block, instruction, f"{opcode.value} is balanced-ternary only"))
        elif opcode is AssemblyOpcode.TREL:
            destination, *sources = instruction.registers
            if register_type(destination) is not AssemblyType.TRIT:
                raise EmulatorError(self._static_context(function, block, instruction, "TREL destination must be trit"))
            source_type = same_type(tuple(sources))
            if source_type not in {AssemblyType.TRIT, AssemblyType.TRYTE, AssemblyType.I64, AssemblyType.F64}:
                raise EmulatorError(self._static_context(function, block, instruction, "TREL requires scalar numeric operands"))
            if not isinstance(instruction.immediate, int) or instruction.immediate not in range(6):
                raise EmulatorError(self._static_context(function, block, instruction, "TREL relation code must be 0..5"))
        elif opcode is AssemblyOpcode.TCVT:
            destination, source = instruction.registers
            pair = (register_type(source), register_type(destination))
            allowed = {
                (AssemblyType.TRIT, AssemblyType.I64),
                (AssemblyType.TRYTE, AssemblyType.I64),
                (AssemblyType.TRIT, AssemblyType.F64),
                (AssemblyType.TRYTE, AssemblyType.F64),
                (AssemblyType.I64, AssemblyType.F64),
                (AssemblyType.I64, AssemblyType.TRYTE),
            }
            if pair not in allowed:
                raise EmulatorError(self._static_context(function, block, instruction, f"unsupported explicit conversion {pair[0].value} -> {pair[1].value}"))
        elif opcode is AssemblyOpcode.TCMP:
            destination, *sources = instruction.registers
            if register_type(destination) is not AssemblyType.TRIT:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TCMP destination must be a trit register",
                    )
                )
            source_type = same_type(tuple(sources))
            if source_type is AssemblyType.STRING:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TCMP does not support string values",
                    )
                )
            if source_type is AssemblyType.REFERENCE:
                raise EmulatorError(self._static_context(function, block, instruction, "TCMP does not support references"))
        elif opcode is AssemblyOpcode.TLOAD:
            destination, index = instruction.registers
            if instruction.memory not in memory_objects:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"unknown memory object m{instruction.memory}",
                    )
                )
            memory = memory_objects[instruction.memory]  # type: ignore[index]
            if register_type(index) not in {AssemblyType.TRYTE, AssemblyType.I64}:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TLOAD index must be a tryte or i64 register",
                    )
                )
            if register_type(destination) is not memory.element_type:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"TLOAD destination type does not match "
                        f"m{memory.index}:{memory.element_type.value}",
                    )
                )
        elif opcode is AssemblyOpcode.TSTORE:
            index, source = instruction.registers
            if instruction.memory not in memory_objects:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"unknown memory object m{instruction.memory}",
                    )
                )
            memory = memory_objects[instruction.memory]  # type: ignore[index]
            if register_type(index) not in {AssemblyType.TRYTE, AssemblyType.I64}:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TSTORE index must be a tryte or i64 register",
                    )
                )
            if register_type(source) is not memory.element_type:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"TSTORE source type does not match "
                        f"m{memory.index}:{memory.element_type.value}",
                    )
                )
        elif opcode is AssemblyOpcode.TCALL:
            destinations = instruction.result_registers
            arguments = instruction.argument_registers
            for destination in destinations:
                register_type(destination)
            for argument in arguments:
                register_type(argument)
            if instruction.callee not in functions:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"call to nonexistent function '{instruction.callee}'",
                    )
                )
            callee = functions[instruction.callee or ""]
            if len(arguments) != len(callee.parameters):
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"TCALL to '{callee.name}' expects "
                        f"{len(callee.parameters)} argument(s), got "
                        f"{len(arguments)}",
                    )
                )
            argument_types = tuple(register_type(argument) for argument in arguments)
            parameter_types = tuple(
                parameter.type for parameter in callee.parameters
            )
            if argument_types != parameter_types:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"TCALL to '{callee.name}' has incompatible argument types",
                    )
                )
            destination_types = tuple(
                register_type(destination) for destination in destinations
            )
            if destinations and destination_types != callee.result_types:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"TCALL destination types do not match return types of "
                        f"'{callee.name}'",
                    )
                )
        elif opcode is AssemblyOpcode.TRET:
            result_types = tuple(register_type(register) for register in instruction.registers)
            if result_types != function.result_types:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TRET types do not match function return types",
                    )
                )
        elif opcode is AssemblyOpcode.TJMP:
            self._require_labels(
                function,
                block,
                instruction,
                blocks,
            )
        elif opcode is AssemblyOpcode.TBR3:
            condition = instruction.registers[0]
            if register_type(condition) is not AssemblyType.TRIT:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TBR3 condition must be a trit register",
                    )
                )
            self._require_labels(function, block, instruction, blocks)
            if len(set(instruction.labels)) != 3:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        "TBR3 labels must be distinct",
                    )
                )

    def _require_labels(
        self,
        function: AssemblyFunction,
        block: AssemblyBlock,
        instruction: AssemblyInstruction,
        blocks: dict[str, AssemblyBlock],
    ) -> None:
        for label in instruction.labels:
            if label not in blocks:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"unknown label '{label}'",
                    )
                )

    def _validate_memory_budget(self, function: AssemblyFunction) -> None:
        memory_cost = sum(
            memory.length
            * (1 if memory.element_type is AssemblyType.TRIT else 6)
            for memory in function.memory_objects
        )
        if memory_cost > self.max_memory_trits:
            raise AssemblyVerifierError(
                f"function '{function.name}' requires {memory_cost} logical "
                f"trits of frame memory; limit is {self.max_memory_trits}"
            )

