"""Explicit-frame emulator for typed, labelled S3 Assembly."""

from __future__ import annotations

from dataclasses import dataclass, field

from .diagnostics import DiagnosticCategory, DiagnosticCode
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
    parse_assembly,
)
from .ternary import (
    TernaryRangeError,
    TernaryWidth,
    TRYTE_MAX,
    add,
    compare,
    invert,
    tritwise_max,
    tritwise_min,
    validate,
)
from .assembly_verifier import AssemblyVerifier, AssemblyVerifierError, WIDTH_MAP
from .metrics import EmulationMetrics
from .numeric import NumericError, validate_f64, validate_i64


EmulatorError = AssemblyVerifierError


AssemblyValue = int | float | str

DEFAULT_MAX_MEMORY_TRITS = 6561
DEFAULT_MAX_FRAMES = 1024
DEFAULT_MAX_INSTRUCTIONS = 100_000


@dataclass(slots=True)
class Frame:
    function: AssemblyFunction
    registers: dict[int, AssemblyValue] = field(default_factory=dict)
    memory: dict[int, list[AssemblyValue | None]] = field(default_factory=dict)
    block_label: str = "entry"
    instruction_index: int = 0
    return_destinations: tuple[int, ...] = ()
    return_block: str | None = None
    return_instruction_index: int | None = None
    call_instruction: AssemblyInstruction | None = None


class Emulator(AssemblyVerifier):
    def __init__(
        self,
        *,
        max_frames: int = DEFAULT_MAX_FRAMES,
        max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
        max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
        enable_metrics: bool = False,
    ):
        if max_frames < 1:
            raise ValueError("max_frames must be at least 1")
        if max_instructions < 1:
            raise ValueError("max_instructions must be at least 1")
        if max_memory_trits < 1:
            raise ValueError("max_memory_trits must be at least 1")
        self.max_frames = max_frames
        self.max_instructions = max_instructions
        self.max_memory_trits = max_memory_trits
        super().__init__(max_memory_trits=max_memory_trits)
        self.metrics = EmulationMetrics() if enable_metrics else None

    def validate(
        self,
        program: AssemblyProgram,
        *,
        entry: str | None = None,
    ) -> None:
        """Validate assembly without executing it.

        Native backends use this public boundary so they only consume the same
        typed, structurally valid assembly accepted by the emulator.
        """

        super().validate(program, entry=entry)

    def execute(
        self,
        program: AssemblyProgram,
        entry: str = "main",
        *,
        capture_memory: list[dict[int, list[AssemblyValue | None]]] | None = None,
    ) -> AssemblyValue:
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
        stack = [self._create_frame(entry_function)]
        executed = 0
        if self.metrics:
            # Phase 8: clear metrics for each run
            self.metrics.executed_s3_opcodes = 0
            self.metrics.maximum_frame_depth_observed = 1
            self.metrics.function_call_count = 0

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
                    f"function '{frame.function.name}'",
                    diagnostic_category=(
                        DiagnosticCategory.INSTRUCTION_LIMIT
                    ),
                    diagnostic_code=(
                        DiagnosticCode.RUNTIME_INSTRUCTION_LIMIT
                    ),
                    diagnostic_context={
                        "function": frame.function.name,
                        "block": frame.block_label,
                        "limit": self.max_instructions,
                    },
                )
            instruction = block.instructions[frame.instruction_index]
            executed += 1
            if self.metrics:
                self.metrics.executed_s3_opcodes = executed
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
                elif opcode is AssemblyOpcode.TCONST_STR:
                    assert instruction.static_string is not None
                    self._write(
                        frame,
                        instruction.registers[0],
                        instruction.static_string,
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
                            self._read_int(frame, source, instruction),
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
                    left = self._read(frame, left_register, instruction)
                    right = self._read(frame, right_register, instruction)
                    if type_name is AssemblyType.I64 and opcode is AssemblyOpcode.TADD:
                        result = validate_i64(left + right)
                    elif type_name is AssemblyType.F64 and opcode is AssemblyOpcode.TADD:
                        result = validate_f64(left + right)
                    else:
                        result = operation(left, right, WIDTH_MAP[type_name])
                    self._write(frame, destination, result, instruction)
                    frame.instruction_index += 1
                elif opcode is AssemblyOpcode.TCMP:
                    destination, left_register, right_register = instruction.registers
                    source_type = self._register_type(
                        frame,
                        left_register,
                        instruction,
                    )
                    left = self._read(frame, left_register, instruction)
                    right = self._read(frame, right_register, instruction)
                    if source_type in {AssemblyType.I64, AssemblyType.F64}:
                        result = -1 if left < right else 1 if left > right else 0
                    else:
                        result = compare(left, right, WIDTH_MAP[source_type])
                    self._write(frame, destination, result, instruction)
                    frame.instruction_index += 1
                elif opcode is AssemblyOpcode.TSTORE:
                    index_register, source_register = instruction.registers
                    index = self._read_int(frame, index_register, instruction)
                    value = self._read(frame, source_register, instruction)
                    self._store_memory(
                        frame,
                        instruction,
                        index,
                        value,
                        source_register,
                    )
                    frame.instruction_index += 1
                elif opcode is AssemblyOpcode.TLOAD:
                    destination, index_register = instruction.registers
                    index = self._read_int(frame, index_register, instruction)
                    value = self._load_memory(frame, instruction, index)
                    self._write(frame, destination, value, instruction)
                    frame.instruction_index += 1
                elif opcode is AssemblyOpcode.TJMP:
                    frame.block_label = instruction.labels[0]
                    frame.instruction_index = 0
                elif opcode is AssemblyOpcode.TBR3:
                    condition = self._read_int(
                        frame,
                        instruction.registers[0],
                        instruction,
                    )
                    target_index = {-1: 0, 0: 1, 1: 2}[condition]
                    frame.block_label = instruction.labels[target_index]
                    frame.instruction_index = 0
                elif opcode is AssemblyOpcode.TCALL:
                    if len(stack) >= self.max_frames:
                        raise self._runtime_error(
                            frame,
                            instruction,
                            f"frame limit {self.max_frames} exceeded",
                            DiagnosticCategory.FRAME_LIMIT,
                            DiagnosticCode.RUNTIME_FRAME_LIMIT,
                            limit=self.max_frames,
                        )
                    assert instruction.callee is not None
                    callee = functions[instruction.callee]
                    argument_values = [
                        self._read(frame, register, instruction)
                        for register in instruction.argument_registers
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
                        self._create_frame(
                            callee,
                            registers=callee_registers,
                            return_destinations=instruction.result_registers,
                            return_block=return_block,
                            return_instruction_index=return_index,
                            call_instruction=instruction,
                        )
                    )
                    if self.metrics:
                        self.metrics.function_call_count += 1
                        if len(stack) > self.metrics.maximum_frame_depth_observed:
                            self.metrics.maximum_frame_depth_observed = len(stack)
                elif opcode is AssemblyOpcode.TRET:
                    result = tuple(
                        self._read(frame, register, instruction)
                        for register in instruction.registers
                    )
                    completed = stack.pop()
                    if not stack:
                        if capture_memory is not None:
                            capture_memory.append(completed.memory)
                        return result[0]
                    caller = stack[-1]
                    assert completed.call_instruction is not None
                    if (
                        caller.block_label != completed.return_block
                        or caller.instruction_index
                        != completed.return_instruction_index
                    ):
                        raise self._runtime_error(
                            caller,
                            completed.call_instruction,
                            f"corrupt return position after calling "
                            f"'{completed.function.name}'",
                            DiagnosticCategory.INTERNAL,
                            DiagnosticCode.RUNTIME_INVALID_STATE,
                        )
                    if completed.return_destinations and (
                        len(completed.return_destinations) != len(result)
                    ):
                        raise self._runtime_error(
                            caller,
                            completed.call_instruction,
                            "call result width mismatch",
                            DiagnosticCategory.INTERNAL,
                            DiagnosticCode.RUNTIME_INVALID_STATE,
                        )
                    if completed.return_destinations:
                        for destination, value in zip(
                            completed.return_destinations,
                            result,
                            strict=True,
                        ):
                            self._write(
                                caller,
                                destination,
                                value,
                                completed.call_instruction,
                            )
                else:
                    raise self._runtime_error(
                        frame,
                        instruction,
                        f"unsupported opcode {opcode.value}",
                        DiagnosticCategory.INTERNAL,
                        DiagnosticCode.RUNTIME_INVALID_STATE,
                    )
            except TernaryRangeError as error:
                raise self._runtime_error(
                    frame,
                    instruction,
                    str(error),
                    DiagnosticCategory.OVERFLOW,
                    DiagnosticCode.RUNTIME_OVERFLOW,
                    value=error.value,
                    lower_bound=error.lower_bound,
                    upper_bound=error.upper_bound,
                ) from error

        raise EmulatorError(
            "execution stopped without returning a value",
            diagnostic_category=DiagnosticCategory.INTERNAL,
            diagnostic_code=DiagnosticCode.RUNTIME_INVALID_STATE,
        )

    def _create_frame(
        self,
        function: AssemblyFunction,
        *,
        registers: dict[int, int] | None = None,
        return_destinations: tuple[int, ...] = (),
        return_block: str | None = None,
        return_instruction_index: int | None = None,
        call_instruction: AssemblyInstruction | None = None,
    ) -> Frame:
        self._validate_memory_budget(function)
        return Frame(
            function,
            registers={} if registers is None else dict(registers),
            memory={
                memory.index: [None] * memory.length
                for memory in function.memory_objects
            },
            return_destinations=return_destinations,
            return_block=return_block,
            return_instruction_index=return_instruction_index,
            call_instruction=call_instruction,
        )

    def _validate_memory_budget(self, function: AssemblyFunction) -> None:
        memory_cost = sum(
            memory.length
            * (1 if memory.element_type is AssemblyType.TRIT else 6)
            for memory in function.memory_objects
        )
        if memory_cost > self.max_memory_trits:
            raise EmulatorError(
                f"function '{function.name}' requires {memory_cost} logical "
                f"trits of frame memory; limit is {self.max_memory_trits}"
            )

    @staticmethod
    def _memory_definition(
        frame: Frame,
        memory_index: int | None,
        instruction: AssemblyInstruction,
    ) -> AssemblyMemoryObject:
        for memory in frame.function.memory_objects:
            if memory.index == memory_index:
                return memory
        raise EmulatorError(
            Emulator._context(
                frame,
                instruction,
                f"unknown memory object m{memory_index}",
            )
        )

    @classmethod
    def _checked_memory_index(
        cls,
        frame: Frame,
        instruction: AssemblyInstruction,
        memory: AssemblyMemoryObject,
        index: int,
    ) -> int:
        if index < 0 or index >= memory.length:
            raise cls._runtime_error(
                frame,
                instruction,
                f"[bounds] memory m{memory.index} index {index} is outside "
                f"[0, {memory.length})",
                DiagnosticCategory.BOUNDS,
                DiagnosticCode.RUNTIME_BOUNDS,
                memory=f"m{memory.index}",
                index=index,
                lower_bound=0,
                upper_bound=memory.length,
            )
        return index

    def _store_memory(
        self,
        frame: Frame,
        instruction: AssemblyInstruction,
        index: int,
        value: AssemblyValue,
        source_register: int,
    ) -> None:
        memory = self._memory_definition(frame, instruction.memory, instruction)
        index = self._checked_memory_index(frame, instruction, memory, index)
        source_type = self._register_type(frame, source_register, instruction)
        if source_type is not memory.element_type:
            raise EmulatorError(
                self._context(
                    frame,
                    instruction,
                    f"memory m{memory.index} expects {memory.element_type.value}, "
                    f"got {source_type.value}",
                )
            )
        if memory.element_type is AssemblyType.STRING:
            if not isinstance(value, str):
                raise self._runtime_error(
                    frame,
                    instruction,
                    f"memory m{memory.index} expects a string handle",
                    DiagnosticCategory.INTERNAL,
                    DiagnosticCode.RUNTIME_INVALID_STATE,
                    memory=f"m{memory.index}",
                    index=index,
                )
        else:
            if not isinstance(value, int):
                raise self._runtime_error(
                    frame,
                    instruction,
                    f"memory m{memory.index} expects a numeric value",
                    DiagnosticCategory.INTERNAL,
                    DiagnosticCode.RUNTIME_INVALID_STATE,
                    memory=f"m{memory.index}",
                    index=index,
                )
            try:
                validate(value, WIDTH_MAP[memory.element_type])
            except TernaryRangeError as error:
                raise self._runtime_error(
                    frame,
                    instruction,
                    f"memory m{memory.index} index {index}: {error}",
                    DiagnosticCategory.OVERFLOW,
                    DiagnosticCode.RUNTIME_OVERFLOW,
                    memory=f"m{memory.index}",
                    index=index,
                    value=error.value,
                    lower_bound=error.lower_bound,
                    upper_bound=error.upper_bound,
                ) from error
        cells = frame.memory[memory.index]
        if not memory.mutable and cells[index] is not None:
            raise self._runtime_error(
                frame,
                instruction,
                f"memory m{memory.index} index {index} is immutable and "
                "already initialized",
                DiagnosticCategory.IMMUTABLE_WRITE,
                DiagnosticCode.RUNTIME_IMMUTABLE_WRITE,
                memory=f"m{memory.index}",
                index=index,
            )
        cells[index] = value

    def _load_memory(
        self,
        frame: Frame,
        instruction: AssemblyInstruction,
        index: int,
    ) -> AssemblyValue:
        memory = self._memory_definition(frame, instruction.memory, instruction)
        index = self._checked_memory_index(frame, instruction, memory, index)
        value = frame.memory[memory.index][index]
        if value is None:
            raise self._runtime_error(
                frame,
                instruction,
                f"uninitialized memory m{memory.index} at index {index} "
                f"(length {memory.length})",
                DiagnosticCategory.UNINITIALIZED,
                DiagnosticCode.RUNTIME_UNINITIALIZED_MEMORY,
                memory=f"m{memory.index}",
                index=index,
                limit=memory.length,
            )
        return value

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
    ) -> AssemblyValue:
        self._register_type(frame, register, instruction)
        try:
            return frame.registers[register]
        except KeyError as error:
            raise self._runtime_error(
                frame,
                instruction,
                f"uninitialized register r{register}",
                DiagnosticCategory.UNINITIALIZED,
                DiagnosticCode.RUNTIME_UNINITIALIZED_REGISTER,
                notes=(f"register r{register}",),
            ) from error

    def _read_int(
        self,
        frame: Frame,
        register: int,
        instruction: AssemblyInstruction,
    ) -> int:
        value = self._read(frame, register, instruction)
        if not isinstance(value, int):
            raise self._runtime_error(
                frame,
                instruction,
                f"register r{register} does not contain a numeric value",
                DiagnosticCategory.INTERNAL,
                DiagnosticCode.RUNTIME_INVALID_STATE,
                notes=(f"register r{register}",),
            )
        return value

    def _write(
        self,
        frame: Frame,
        register: int,
        value: AssemblyValue,
        instruction: AssemblyInstruction,
    ) -> None:
        type_name = self._register_type(frame, register, instruction)
        if type_name is AssemblyType.STRING:
            if not isinstance(value, str):
                raise self._runtime_error(
                    frame,
                    instruction,
                    f"register r{register} expects a string handle",
                    DiagnosticCategory.INTERNAL,
                    DiagnosticCode.RUNTIME_INVALID_STATE,
                    notes=(f"register r{register}",),
                )
        elif type_name is AssemblyType.I64:
            try:
                validate_i64(value)
            except (NumericError, TypeError, ValueError) as error:
                raise self._runtime_error(
                    frame, instruction, str(error), DiagnosticCategory.OVERFLOW,
                    DiagnosticCode.RUNTIME_OVERFLOW,
                ) from error
        elif type_name is AssemblyType.F64:
            try:
                validate_f64(value)
            except (NumericError, TypeError, ValueError) as error:
                raise self._runtime_error(
                    frame, instruction, str(error), DiagnosticCategory.OVERFLOW,
                    DiagnosticCode.RUNTIME_OVERFLOW,
                ) from error
        else:
            if not isinstance(value, int):
                raise self._runtime_error(
                    frame,
                    instruction,
                    f"register r{register} expects a numeric value",
                    DiagnosticCategory.INTERNAL,
                    DiagnosticCode.RUNTIME_INVALID_STATE,
                    notes=(f"register r{register}",),
                )
            try:
                validate(value, WIDTH_MAP[type_name])
            except TernaryRangeError as error:
                raise self._runtime_error(
                    frame,
                    instruction,
                    str(error),
                    DiagnosticCategory.OVERFLOW,
                    DiagnosticCode.RUNTIME_OVERFLOW,
                    value=error.value,
                    lower_bound=error.lower_bound,
                    upper_bound=error.upper_bound,
                ) from error
        frame.registers[register] = value

    @classmethod
    def _runtime_error(
        cls,
        frame: Frame,
        instruction: AssemblyInstruction,
        message: str,
        category: DiagnosticCategory,
        code: DiagnosticCode,
        **context: object,
    ) -> EmulatorError:
        notes: tuple[str, ...] = ()
        if instruction.line is not None:
            notes = (f"assembly line {instruction.line}",)
        supplied_notes = context.pop("notes", ())
        if isinstance(supplied_notes, str):
            supplied_notes = (supplied_notes,)
        return EmulatorError(
            cls._context(frame, instruction, message),
            diagnostic_message=message,
            diagnostic_category=category,
            diagnostic_code=code,
            diagnostic_context={
                "function": frame.function.name,
                "block": frame.block_label,
                "opcode": instruction.opcode.value,
                "notes": (*notes, *supplied_notes),
                **context,
            },
            location=instruction.source,
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
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
) -> AssemblyValue:
    program = parse_assembly(assembly) if isinstance(assembly, str) else assembly
    from .backends._hosted_execution import _execute_hosted_assembly

    return _execute_hosted_assembly(
        program,
        entry,
        max_frames=max_frames,
        max_instructions=max_instructions,
        max_memory_trits=max_memory_trits,
    )
