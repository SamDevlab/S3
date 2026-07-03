"""Explicit-frame emulator for typed, labelled S3 Assembly."""

from __future__ import annotations

from dataclasses import dataclass, field

from .assembly import (
    AssemblyBlock,
    AssemblyError,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
    TERMINATOR_OPCODES,
    parse_assembly,
)
from .ternary import (
    TernaryRangeError,
    TernaryWidth,
    add,
    compare,
    invert,
    tritwise_max,
    tritwise_min,
    validate,
)


class EmulatorError(AssemblyError):
    """Raised when loaded assembly violates an execution invariant."""


WIDTH_MAP = {
    AssemblyType.TRIT: TernaryWidth.TRIT,
    AssemblyType.TRYTE: TernaryWidth.TRYTE,
}


@dataclass(slots=True)
class Frame:
    function: AssemblyFunction
    registers: dict[int, int] = field(default_factory=dict)
    block_label: str = "entry"
    instruction_index: int = 0
    return_destination: int | None = None
    return_block: str | None = None
    return_instruction_index: int | None = None
    call_instruction: AssemblyInstruction | None = None


class Emulator:
    def __init__(
        self,
        *,
        max_frames: int = 1024,
        max_instructions: int = 100_000,
    ):
        if max_frames < 1:
            raise ValueError("max_frames must be at least 1")
        if max_instructions < 1:
            raise ValueError("max_instructions must be at least 1")
        self.max_frames = max_frames
        self.max_instructions = max_instructions

    def execute(self, program: AssemblyProgram, entry: str = "main") -> int:
        functions = self._validate_program(program)
        try:
            entry_function = functions[entry]
        except KeyError as error:
            raise EmulatorError(f"entry function '{entry}' was not found") from error
        if entry_function.parameters:
            raise EmulatorError(
                f"entry function '{entry}' must not declare parameters"
            )

        blocks = {
            function.name: {
                block.label: block for block in function.blocks
            }
            for function in program.functions
        }
        stack = [Frame(entry_function)]
        executed = 0

        while stack:
            frame = stack[-1]
            block = blocks[frame.function.name][frame.block_label]
            if frame.instruction_index >= len(block.instructions):
                raise EmulatorError(
                    f"function '{frame.function.name}', block "
                    f"'{frame.block_label}' completed without a terminator"
                )
            if executed >= self.max_instructions:
                raise EmulatorError(
                    f"instruction limit {self.max_instructions} exceeded in "
                    f"function '{frame.function.name}'"
                )
            instruction = block.instructions[frame.instruction_index]
            executed += 1
            opcode = instruction.opcode

            try:
                if opcode is AssemblyOpcode.TCONST:
                    assert instruction.immediate is not None
                    self._write(
                        frame,
                        instruction.registers[0],
                        instruction.immediate,
                        instruction,
                    )
                    frame.instruction_index += 1
                elif opcode is AssemblyOpcode.TMOV:
                    self._write(
                        frame,
                        instruction.registers[0],
                        self._read(frame, instruction.registers[1], instruction),
                        instruction,
                    )
                    frame.instruction_index += 1
                elif opcode is AssemblyOpcode.TINV:
                    source = instruction.registers[1]
                    type_name = self._register_type(frame, source, instruction)
                    self._write(
                        frame,
                        instruction.registers[0],
                        invert(
                            self._read(frame, source, instruction),
                            WIDTH_MAP[type_name],
                        ),
                        instruction,
                    )
                    frame.instruction_index += 1
                elif opcode in {
                    AssemblyOpcode.TADD,
                    AssemblyOpcode.TMIN,
                    AssemblyOpcode.TMAX,
                }:
                    destination, left_register, right_register = instruction.registers
                    type_name = self._register_type(
                        frame,
                        destination,
                        instruction,
                    )
                    operation = {
                        AssemblyOpcode.TADD: add,
                        AssemblyOpcode.TMIN: tritwise_min,
                        AssemblyOpcode.TMAX: tritwise_max,
                    }[opcode]
                    self._write(
                        frame,
                        destination,
                        operation(
                            self._read(frame, left_register, instruction),
                            self._read(frame, right_register, instruction),
                            WIDTH_MAP[type_name],
                        ),
                        instruction,
                    )
                    frame.instruction_index += 1
                elif opcode is AssemblyOpcode.TCMP:
                    destination, left_register, right_register = instruction.registers
                    source_type = self._register_type(
                        frame,
                        left_register,
                        instruction,
                    )
                    self._write(
                        frame,
                        destination,
                        compare(
                            self._read(frame, left_register, instruction),
                            self._read(frame, right_register, instruction),
                            WIDTH_MAP[source_type],
                        ),
                        instruction,
                    )
                    frame.instruction_index += 1
                elif opcode is AssemblyOpcode.TJMP:
                    frame.block_label = instruction.labels[0]
                    frame.instruction_index = 0
                elif opcode is AssemblyOpcode.TBR3:
                    condition = self._read(
                        frame,
                        instruction.registers[0],
                        instruction,
                    )
                    target_index = {-1: 0, 0: 1, 1: 2}[condition]
                    frame.block_label = instruction.labels[target_index]
                    frame.instruction_index = 0
                elif opcode is AssemblyOpcode.TCALL:
                    if len(stack) >= self.max_frames:
                        raise EmulatorError(
                            self._context(
                                frame,
                                instruction,
                                f"frame limit {self.max_frames} exceeded",
                            )
                        )
                    assert instruction.callee is not None
                    callee = functions[instruction.callee]
                    argument_values = [
                        self._read(frame, register, instruction)
                        for register in instruction.registers[1:]
                    ]
                    return_block = frame.block_label
                    frame.instruction_index += 1
                    return_index = frame.instruction_index
                    callee_registers = {
                        parameter.register: value
                        for parameter, value in zip(
                            callee.parameters,
                            argument_values,
                            strict=True,
                        )
                    }
                    stack.append(
                        Frame(
                            callee,
                            registers=callee_registers,
                            return_destination=instruction.registers[0],
                            return_block=return_block,
                            return_instruction_index=return_index,
                            call_instruction=instruction,
                        )
                    )
                elif opcode is AssemblyOpcode.TRET:
                    result = self._read(
                        frame,
                        instruction.registers[0],
                        instruction,
                    )
                    completed = stack.pop()
                    if not stack:
                        return result
                    caller = stack[-1]
                    assert completed.return_destination is not None
                    assert completed.call_instruction is not None
                    if (
                        caller.block_label != completed.return_block
                        or caller.instruction_index
                        != completed.return_instruction_index
                    ):
                        raise EmulatorError(
                            f"corrupt return position after calling "
                            f"'{completed.function.name}'"
                        )
                    self._write(
                        caller,
                        completed.return_destination,
                        result,
                        completed.call_instruction,
                    )
                else:
                    raise EmulatorError(
                        self._context(
                            frame,
                            instruction,
                            f"unsupported opcode {opcode.value}",
                        )
                    )
            except TernaryRangeError as error:
                raise EmulatorError(
                    self._context(frame, instruction, str(error))
                ) from error

        raise EmulatorError("execution stopped without returning a value")

    def _validate_program(
        self,
        program: AssemblyProgram,
    ) -> dict[str, AssemblyFunction]:
        functions: dict[str, AssemblyFunction] = {}
        for function in program.functions:
            if function.name in functions:
                raise EmulatorError(f"duplicate function '{function.name}'")
            functions[function.name] = function
        for function in program.functions:
            self._validate_function(function, functions)
        return functions

    def _validate_function(
        self,
        function: AssemblyFunction,
        functions: dict[str, AssemblyFunction],
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
                    blocks,
                    functions,
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
        blocks: dict[str, AssemblyBlock],
        functions: dict[str, AssemblyFunction],
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
            assert instruction.immediate is not None
            try:
                validate(instruction.immediate, WIDTH_MAP[type_name])
            except TernaryRangeError as error:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        str(error),
                    )
                ) from error
        elif opcode in {AssemblyOpcode.TMOV, AssemblyOpcode.TINV}:
            same_type(instruction.registers)
        elif opcode in {
            AssemblyOpcode.TADD,
            AssemblyOpcode.TMIN,
            AssemblyOpcode.TMAX,
        }:
            same_type(instruction.registers)
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
            same_type(tuple(sources))
        elif opcode is AssemblyOpcode.TCALL:
            destination, *arguments = instruction.registers
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
            if register_type(destination) is not callee.return_type:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"TCALL destination type does not match return type of "
                        f"'{callee.name}'",
                    )
                )
        elif opcode is AssemblyOpcode.TRET:
            register = instruction.registers[0]
            if register_type(register) is not function.return_type:
                raise EmulatorError(
                    self._static_context(
                        function,
                        block,
                        instruction,
                        f"TRET type does not match function return type "
                        f"{function.return_type.value}",
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

    def _register_type(
        self,
        frame: Frame,
        register: int,
        instruction: AssemblyInstruction,
    ) -> AssemblyType:
        type_name = frame.function.type_of(register)
        if type_name is None:
            raise EmulatorError(
                self._context(frame, instruction, f"invalid register r{register}")
            )
        return type_name

    def _read(
        self,
        frame: Frame,
        register: int,
        instruction: AssemblyInstruction,
    ) -> int:
        self._register_type(frame, register, instruction)
        try:
            return frame.registers[register]
        except KeyError as error:
            raise EmulatorError(
                self._context(
                    frame,
                    instruction,
                    f"uninitialized register r{register}",
                )
            ) from error

    def _write(
        self,
        frame: Frame,
        register: int,
        value: int,
        instruction: AssemblyInstruction,
    ) -> None:
        type_name = self._register_type(frame, register, instruction)
        try:
            validate(value, WIDTH_MAP[type_name])
        except TernaryRangeError as error:
            raise EmulatorError(
                self._context(frame, instruction, str(error))
            ) from error
        frame.registers[register] = value

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

    @classmethod
    def _context(
        cls,
        frame: Frame,
        instruction: AssemblyInstruction,
        message: str,
    ) -> str:
        block = AssemblyBlock(frame.block_label, ())
        return cls._static_context(
            frame.function,
            block,
            instruction,
            message,
        )


def execute_assembly(
    assembly: str | AssemblyProgram,
    entry: str = "main",
    *,
    max_frames: int = 1024,
    max_instructions: int = 100_000,
) -> int:
    program = parse_assembly(assembly) if isinstance(assembly, str) else assembly
    return Emulator(
        max_frames=max_frames,
        max_instructions=max_instructions,
    ).execute(program, entry)
