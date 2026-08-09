"""Controlled adapters from ``AssemblyProgram`` to ``AssemblyTextRenderer``."""

from __future__ import annotations

from collections.abc import Callable

from bootstrap.s3.assembly import (
    ASSEMBLY_FORMAT_VERSION,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyMemoryObject,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyStaticString,
    AssemblyType,
)
from bootstrap.s3.assembly_text_renderer import (
    AssemblyTextRenderer,
    AssemblyTextSource,
)
from bootstrap.s3.static_text import StaticTextDocument


FIRST_PROGRAM_REGISTER_TYPES = tuple(
    (register, AssemblyType.TRYTE) for register in range(5)
)
FIRST_PROGRAM_OPCODES = (
    AssemblyOpcode.TCONST,
    AssemblyOpcode.TMOV,
    AssemblyOpcode.TCONST,
    AssemblyOpcode.TMOV,
    AssemblyOpcode.TCONST,
    AssemblyOpcode.TRET,
)
SIMPLE_CALL_ADD_PARAMETER_TYPES = (
    (0, AssemblyType.TRYTE),
    (1, AssemblyType.TRYTE),
)
SIMPLE_CALL_ADD_REGISTER_TYPES = ((2, AssemblyType.TRYTE),)
SIMPLE_CALL_ADD_OPCODES = (
    AssemblyOpcode.TADD,
    AssemblyOpcode.TRET,
)
SIMPLE_CALL_MAIN_REGISTER_TYPES = tuple(
    (register, AssemblyType.TRYTE) for register in range(3)
)
SIMPLE_CALL_MAIN_OPCODES = (
    AssemblyOpcode.TCONST,
    AssemblyOpcode.TCONST,
    AssemblyOpcode.TCALL,
    AssemblyOpcode.TRET,
)
SIGN_FUNCTION_PARAMETER_TYPES = ((0, AssemblyType.TRYTE),)
SIGN_FUNCTION_REGISTER_TYPES = (
    (1, AssemblyType.TRYTE),
    (2, AssemblyType.TRIT),
    (3, AssemblyType.TRIT),
    (4, AssemblyType.TRIT),
    (5, AssemblyType.TRIT),
)
SIGN_FUNCTION_BLOCKS = (
    (
        "entry",
        (
            AssemblyOpcode.TCONST,
            AssemblyOpcode.TCMP,
            AssemblyOpcode.TBR3,
        ),
    ),
    (
        "switch_negative_0",
        (
            AssemblyOpcode.TCONST,
            AssemblyOpcode.TRET,
        ),
    ),
    (
        "switch_neutral_1",
        (
            AssemblyOpcode.TCONST,
            AssemblyOpcode.TRET,
        ),
    ),
    (
        "switch_positive_2",
        (
            AssemblyOpcode.TCONST,
            AssemblyOpcode.TRET,
        ),
    ),
)
SIGN_MAIN_REGISTER_TYPES = (
    (0, AssemblyType.TRYTE),
    (1, AssemblyType.TRIT),
)
SIGN_MAIN_BLOCKS = (
    (
        "entry",
        (
            AssemblyOpcode.TCONST,
            AssemblyOpcode.TCALL,
            AssemblyOpcode.TRET,
        ),
    ),
)
SUPPORTED_PROGRAM_OPCODES = frozenset(
    {
        AssemblyOpcode.TCONST,
        AssemblyOpcode.TCONST_STR,
        AssemblyOpcode.TMOV,
        AssemblyOpcode.TINV,
        AssemblyOpcode.TADD,
        AssemblyOpcode.TMIN,
        AssemblyOpcode.TMAX,
        AssemblyOpcode.TCMP,
        AssemblyOpcode.TCALL,
        AssemblyOpcode.TLOAD,
        AssemblyOpcode.TSTORE,
        AssemblyOpcode.TRET,
        AssemblyOpcode.TJMP,
        AssemblyOpcode.TBR3,
        AssemblyOpcode.TADDR,
        AssemblyOpcode.TREFLOAD,
        AssemblyOpcode.TREFSTORE,
    }
)

InstructionEmitter = Callable[[AssemblyTextRenderer, AssemblyInstruction], None]


class AssemblyProgramTextAdapterError(ValueError):
    """Raised when an ``AssemblyProgram`` is outside the supported adapter slice."""


class AssemblyProgramTextAdapter:
    """Render controlled AssemblyProgram shapes through ``AssemblyTextRenderer``.

    This adapter reads real ``AssemblyProgram`` values and preserves the
    current Python Assembly text format. It does not implement the future S3
    Assembly renderer.
    """

    def render_first_program(self, program: AssemblyProgram) -> StaticTextDocument:
        _validate_first_program_shape(program)
        return self.render_supported_program(program)

    def render_simple_call_program(
        self,
        program: AssemblyProgram,
    ) -> StaticTextDocument:
        _validate_simple_call_program_shape(program)
        return self.render_supported_program(program)

    def render_sign_program(self, program: AssemblyProgram) -> StaticTextDocument:
        _validate_sign_program_shape(program)
        return self.render_supported_program(program)

    def render_supported_program(self, program: AssemblyProgram) -> StaticTextDocument:
        _validate_supported_program_shape(program)
        renderer = AssemblyTextRenderer()
        renderer.emit_header(program.version)
        if program.static_strings:
            _emit_static_strings(renderer, program.static_strings)
            renderer.emit_blank_line()
        functions = tuple(program.functions)
        if not functions:
            renderer.emit_blank_line()
        for index, function in enumerate(functions):
            if index > 0:
                renderer.emit_blank_line()
            _emit_function(renderer, function, _emit_supported_instruction)
        return renderer.build()


def render_first_program(program: AssemblyProgram) -> StaticTextDocument:
    return AssemblyProgramTextAdapter().render_first_program(program)


def render_simple_call_program(program: AssemblyProgram) -> StaticTextDocument:
    return AssemblyProgramTextAdapter().render_simple_call_program(program)


def render_sign_program(program: AssemblyProgram) -> StaticTextDocument:
    return AssemblyProgramTextAdapter().render_sign_program(program)


def render_supported_program(program: AssemblyProgram) -> StaticTextDocument:
    return AssemblyProgramTextAdapter().render_supported_program(program)


def _validate_first_program_shape(program: AssemblyProgram) -> None:
    if not isinstance(program, AssemblyProgram):
        raise TypeError("first adapter expects an AssemblyProgram")
    if program.version != ASSEMBLY_FORMAT_VERSION:
        raise AssemblyProgramTextAdapterError(
            "first adapter expects Assembly format version "
            f"{ASSEMBLY_FORMAT_VERSION}"
        )
    if len(program.functions) != 1:
        raise AssemblyProgramTextAdapterError(
            "first adapter expects exactly one function"
        )

    function = program.functions[0]
    if function.name != "main":
        raise AssemblyProgramTextAdapterError(
            "first adapter expects function 'main'"
        )
    if function.return_type is not AssemblyType.TRYTE:
        raise AssemblyProgramTextAdapterError(
            "first adapter expects main to return tryte"
        )
    if function.parameters:
        raise AssemblyProgramTextAdapterError(
            "first adapter does not support parameters"
        )
    if function.memory_objects:
        raise AssemblyProgramTextAdapterError(
            "first adapter does not support memory objects"
        )
        if function.register_types != FIRST_PROGRAM_REGISTER_TYPES:
            raise AssemblyProgramTextAdapterError(
                "first adapter expects registers r0..r4 as tryte"
            )
    if len(function.blocks) != 1:
        raise AssemblyProgramTextAdapterError(
            "first adapter expects exactly one block"
        )

    block = function.blocks[0]
    if block.label != "entry":
        raise AssemblyProgramTextAdapterError(
            "first adapter expects entry block label"
        )
    opcodes = tuple(instruction.opcode for instruction in block.instructions)
    if opcodes != FIRST_PROGRAM_OPCODES:
        raise AssemblyProgramTextAdapterError(
            "first adapter supports only the first fixture opcode sequence"
        )
    _validate_source_metadata(function, "first adapter")


def _validate_simple_call_program_shape(program: AssemblyProgram) -> None:
    if not isinstance(program, AssemblyProgram):
        raise TypeError("simple_call adapter expects an AssemblyProgram")
    if program.version != ASSEMBLY_FORMAT_VERSION:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects Assembly format version "
            f"{ASSEMBLY_FORMAT_VERSION}"
        )
    if len(program.functions) != 2:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects exactly two functions"
        )
    if tuple(function.name for function in program.functions) != ("add", "main"):
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects functions 'add' and 'main'"
        )

    _validate_simple_call_add_function(program.functions[0])
    _validate_simple_call_main_function(program.functions[1])


def _validate_simple_call_add_function(function: AssemblyFunction) -> None:
    if function.return_type is not AssemblyType.TRYTE:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects add to return tryte"
        )
    if _parameter_types(function) != SIMPLE_CALL_ADD_PARAMETER_TYPES:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects add parameters r0 and r1 as tryte"
        )
    if function.memory_objects:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter does not support memory objects"
        )
    if function.register_types != SIMPLE_CALL_ADD_REGISTER_TYPES:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects add register r2 as tryte"
        )
    if len(function.blocks) != 1:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects add to have exactly one block"
        )

    block = function.blocks[0]
    if block.label != "entry":
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects add entry block label"
        )
    opcodes = tuple(instruction.opcode for instruction in block.instructions)
    if opcodes != SIMPLE_CALL_ADD_OPCODES:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter supports only the add opcode sequence"
        )
    _validate_source_metadata(function, "simple_call adapter")


def _validate_simple_call_main_function(function: AssemblyFunction) -> None:
    if function.return_type is not AssemblyType.TRYTE:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects main to return tryte"
        )
    if function.parameters:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter does not support main parameters"
        )
    if function.memory_objects:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter does not support memory objects"
        )
    if function.register_types != SIMPLE_CALL_MAIN_REGISTER_TYPES:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects main registers r0..r2 as tryte"
        )
    if len(function.blocks) != 1:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects main to have exactly one block"
        )

    block = function.blocks[0]
    if block.label != "entry":
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter expects main entry block label"
        )
    opcodes = tuple(instruction.opcode for instruction in block.instructions)
    if opcodes != SIMPLE_CALL_MAIN_OPCODES:
        raise AssemblyProgramTextAdapterError(
            "simple_call adapter supports only the main opcode sequence"
        )
    _validate_source_metadata(function, "simple_call adapter")


def _validate_sign_program_shape(program: AssemblyProgram) -> None:
    if not isinstance(program, AssemblyProgram):
        raise TypeError("sign adapter expects an AssemblyProgram")
    if program.version != ASSEMBLY_FORMAT_VERSION:
        raise AssemblyProgramTextAdapterError(
            "sign adapter expects Assembly format version "
            f"{ASSEMBLY_FORMAT_VERSION}"
        )
    if len(program.functions) != 2:
        raise AssemblyProgramTextAdapterError(
            "sign adapter expects exactly two functions"
        )
    if tuple(function.name for function in program.functions) != ("sign", "main"):
        raise AssemblyProgramTextAdapterError(
            "sign adapter expects functions 'sign' and 'main'"
        )

    _validate_sign_function(program.functions[0])
    _validate_sign_main_function(program.functions[1])


def _validate_sign_function(function: AssemblyFunction) -> None:
    if function.return_type is not AssemblyType.TRIT:
        raise AssemblyProgramTextAdapterError(
            "sign adapter expects sign to return trit"
        )
    if _parameter_types(function) != SIGN_FUNCTION_PARAMETER_TYPES:
        raise AssemblyProgramTextAdapterError(
            "sign adapter expects sign parameter r0 as tryte"
        )
    if function.memory_objects:
        raise AssemblyProgramTextAdapterError(
            "sign adapter does not support memory objects"
        )
    if function.register_types != SIGN_FUNCTION_REGISTER_TYPES:
        raise AssemblyProgramTextAdapterError(
            "sign adapter expects sign registers r1..r5 with fixture types"
        )
    _validate_blocks(function, SIGN_FUNCTION_BLOCKS, "sign adapter", "sign")
    _validate_source_metadata(function, "sign adapter")


def _validate_sign_main_function(function: AssemblyFunction) -> None:
    if function.return_type is not AssemblyType.TRIT:
        raise AssemblyProgramTextAdapterError(
            "sign adapter expects main to return trit"
        )
    if function.parameters:
        raise AssemblyProgramTextAdapterError(
            "sign adapter does not support main parameters"
        )
    if function.memory_objects:
        raise AssemblyProgramTextAdapterError(
            "sign adapter does not support memory objects"
        )
    if function.register_types != SIGN_MAIN_REGISTER_TYPES:
        raise AssemblyProgramTextAdapterError(
            "sign adapter expects main registers r0..r2 with fixture types"
        )
    _validate_blocks(function, SIGN_MAIN_BLOCKS, "sign adapter", "main")
    _validate_source_metadata(function, "sign adapter")


def _validate_blocks(
    function: AssemblyFunction,
    expected_blocks: tuple[tuple[str, tuple[AssemblyOpcode, ...]], ...],
    adapter_name: str,
    function_name: str,
) -> None:
    if len(function.blocks) != len(expected_blocks):
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects {function_name} block shape"
        )

    actual = tuple(
        (
            block.label,
            tuple(instruction.opcode for instruction in block.instructions),
        )
        for block in function.blocks
    )
    if actual != expected_blocks:
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} supports only the {function_name} block shape"
        )


def _parameter_types(
    function: AssemblyFunction,
) -> tuple[tuple[int, AssemblyType], ...]:
    return tuple(
        (parameter.register, parameter.type) for parameter in function.parameters
    )


def _validate_supported_program_shape(program: AssemblyProgram) -> None:
    if not isinstance(program, AssemblyProgram):
        raise TypeError("supported adapter expects an AssemblyProgram")
    _validate_supported_static_strings(program.static_strings)
    for function in program.functions:
        _validate_supported_function_shape(function)


def _validate_supported_static_strings(
    static_strings: tuple[AssemblyStaticString, ...],
) -> None:
    seen: set[str] = set()
    for index, entry in enumerate(static_strings):
        if not isinstance(entry, AssemblyStaticString):
            raise AssemblyProgramTextAdapterError(
                "supported adapter expects static strings to be AssemblyStaticString"
            )
        expected = f"s{index}"
        if entry.id != expected:
            raise AssemblyProgramTextAdapterError(
                f"supported adapter expects static string {expected}"
            )
        if entry.id in seen:
            raise AssemblyProgramTextAdapterError(
                f"supported adapter found duplicate static string {entry.id}"
            )
        seen.add(entry.id)
        if not isinstance(entry.value, str):
            raise AssemblyProgramTextAdapterError(
                "supported adapter expects static string value to be text"
            )


def _validate_supported_function_shape(function: AssemblyFunction) -> None:
    for memory in function.memory_objects:
        _validate_supported_memory_shape(memory)
    for block in function.blocks:
        for instruction in block.instructions:
            _validate_supported_instruction_shape(instruction)


def _validate_supported_memory_shape(memory: AssemblyMemoryObject) -> None:
    if not isinstance(memory.index, int) or isinstance(memory.index, bool):
        raise AssemblyProgramTextAdapterError(
            "supported adapter expects memory index to be an integer"
        )
    if memory.index < 0:
        raise AssemblyProgramTextAdapterError(
            "supported adapter expects memory index to be non-negative"
        )
    if not isinstance(memory.length, int) or isinstance(memory.length, bool):
        raise AssemblyProgramTextAdapterError(
            "supported adapter expects memory length to be an integer"
        )
    if memory.length < 1:
        raise AssemblyProgramTextAdapterError(
            "supported adapter expects memory length to be positive"
        )
    if not isinstance(memory.element_type, AssemblyType):
        raise AssemblyProgramTextAdapterError(
            "supported adapter expects memory element type to be an AssemblyType"
        )
    if not isinstance(memory.mutable, bool):
        raise AssemblyProgramTextAdapterError(
            "supported adapter expects memory mutability to be a boolean"
        )


def _validate_supported_instruction_shape(
    instruction: AssemblyInstruction,
) -> None:
    if instruction.opcode not in SUPPORTED_PROGRAM_OPCODES:
        opcode = (
            instruction.opcode.value
            if isinstance(instruction.opcode, AssemblyOpcode)
            else str(instruction.opcode)
        )
        raise AssemblyProgramTextAdapterError(
            f"supported adapter does not support opcode {opcode}"
        )


def _validate_source_metadata(function: AssemblyFunction, adapter_name: str) -> None:
    for block in function.blocks:
        for instruction in block.instructions:
            if instruction.source is None:
                raise AssemblyProgramTextAdapterError(
                    f"{adapter_name} expects source metadata for "
                    f"{instruction.opcode.value}"
                )


def _emit_function(
    renderer: AssemblyTextRenderer,
    function: AssemblyFunction,
    emit_instruction: InstructionEmitter,
) -> None:
    renderer.emit_function(function.name, _type_group(function.result_types))
    for parameter in function.parameters:
        renderer.emit_param(parameter.register, parameter.type.value)
    for register, type_name in function.register_types:
        renderer.emit_register(register, type_name.value)
    for memory in function.memory_objects:
        renderer.emit_memory(
            memory.index,
            memory.element_type.value,
            memory.length,
            memory.mutable,
        )
    for block in function.blocks:
        renderer.emit_label(block.label)
        for instruction in block.instructions:
            emit_instruction(renderer, instruction)
    renderer.emit_end()


def _emit_static_strings(
    renderer: AssemblyTextRenderer,
    static_strings: tuple[AssemblyStaticString, ...],
) -> None:
    renderer.emit_line(".data")
    for entry in static_strings:
        renderer.emit_line(entry.render())


def _emit_supported_instruction(
    renderer: AssemblyTextRenderer,
    instruction: AssemblyInstruction,
) -> None:
    source = _source(instruction, "supported adapter")
    opcode = instruction.opcode

    if opcode is AssemblyOpcode.TCONST:
        register = _single_register(instruction, "TCONST", "supported adapter")
        if instruction.immediate is None:
            raise AssemblyProgramTextAdapterError(
                "supported adapter expects TCONST immediate"
            )
        _require_no_extra_operands(
            instruction,
            "TCONST",
            "supported adapter",
            allow_immediate=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(register),
            instruction.immediate,
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TCONST_STR:
        register = _single_register(instruction, "TCONST_STR", "supported adapter")
        if instruction.static_string is None:
            raise AssemblyProgramTextAdapterError(
                "supported adapter expects TCONST_STR static string id"
            )
        _require_no_extra_operands(
            instruction,
            "TCONST_STR",
            "supported adapter",
            allow_static_string=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(register),
            instruction.static_string,
            source=source,
        )
        return

    if opcode in {AssemblyOpcode.TMOV, AssemblyOpcode.TINV}:
        left, right = _register_pair(
            instruction,
            opcode.value,
            "supported adapter",
        )
        _require_no_extra_operands(instruction, opcode.value, "supported adapter")
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(right),
            source=source,
        )
        return

    if opcode in {
        AssemblyOpcode.TADD,
        AssemblyOpcode.TMIN,
        AssemblyOpcode.TMAX,
        AssemblyOpcode.TCMP,
    }:
        left, middle, right = _register_triple(
            instruction,
            opcode.value,
            "supported adapter",
        )
        _require_no_extra_operands(instruction, opcode.value, "supported adapter")
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(middle),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TJMP:
        label = _single_label(instruction, "TJMP", "supported adapter")
        _require_no_extra_operands(
            instruction,
            "TJMP",
            "supported adapter",
            allow_labels=True,
        )
        renderer.emit_instruction(opcode.value, label, source=source)
        return

    if opcode is AssemblyOpcode.TBR3:
        condition = _single_register(instruction, "TBR3", "supported adapter")
        labels = _label_triple(instruction, "TBR3", "supported adapter")
        _require_no_extra_operands(
            instruction,
            "TBR3",
            "supported adapter",
            allow_labels=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(condition),
            *labels,
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TCALL:
        _validate_tcall_width(instruction, "supported adapter")
        targets = instruction.result_registers
        arguments = instruction.argument_registers
        if instruction.callee is None:
            raise AssemblyProgramTextAdapterError(
                "supported adapter expects TCALL callee"
            )
        _require_no_extra_operands(
            instruction,
            "TCALL",
            "supported adapter",
            allow_callee=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register_group(targets),
            instruction.callee,
            *(_register(argument) for argument in arguments),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TLOAD:
        target, index = _register_pair(
            instruction,
            "TLOAD",
            "supported adapter",
        )
        memory = _instruction_memory(instruction, "TLOAD", "supported adapter")
        _require_no_extra_operands(
            instruction,
            "TLOAD",
            "supported adapter",
            allow_memory=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(target),
            _memory(memory),
            _register(index),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TSTORE:
        index, source_register = _register_pair(
            instruction,
            "TSTORE",
            "supported adapter",
        )
        memory = _instruction_memory(instruction, "TSTORE", "supported adapter")
        _require_no_extra_operands(
            instruction,
            "TSTORE",
            "supported adapter",
            allow_memory=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _memory(memory),
            _register(index),
            _register(source_register),
            source=source,
        )
        return

    if opcode in {AssemblyOpcode.TADDR, AssemblyOpcode.TREFLOAD, AssemblyOpcode.TREFSTORE}:
        _require_no_extra_operands(
            instruction,
            opcode.value,
            "supported adapter",
            allow_memory=opcode is AssemblyOpcode.TADDR,
        )
        if opcode is AssemblyOpcode.TADDR and instruction.memory is not None:
            operands = (
                _register(instruction.registers[0]),
                _memory(instruction.memory),
                *(_register(register) for register in instruction.registers[1:]),
            )
        else:
            operands = tuple(_register(register) for register in instruction.registers)
        renderer.emit_instruction(
            opcode.value,
            *operands,
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TRET:
        _require_no_extra_operands(instruction, "TRET", "supported adapter")
        renderer.emit_instruction(
            opcode.value,
            _register_group(instruction.registers),
            source=source,
        )
        return

    raise AssemblyProgramTextAdapterError(
        f"supported adapter does not support opcode {opcode.value}"
    )


def _source(
    instruction: AssemblyInstruction,
    adapter_name: str,
) -> AssemblyTextSource | None:
    if instruction.source is None:
        return None
    source = instruction.source
    return AssemblyTextSource(source.line, source.column, source.offset)


def _single_register(
    instruction: AssemblyInstruction,
    opcode: str,
    adapter_name: str,
) -> int:
    if len(instruction.registers) != 1:
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects {opcode} to have one register"
        )
    return instruction.registers[0]


def _register_pair(
    instruction: AssemblyInstruction,
    opcode: str,
    adapter_name: str,
) -> tuple[int, int]:
    if len(instruction.registers) != 2:
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects {opcode} to have two registers"
        )
    return instruction.registers


def _register_triple(
    instruction: AssemblyInstruction,
    opcode: str,
    adapter_name: str,
) -> tuple[int, int, int]:
    if len(instruction.registers) != 3:
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects {opcode} to have three registers"
        )
    return instruction.registers


def _label_triple(
    instruction: AssemblyInstruction,
    opcode: str,
    adapter_name: str,
) -> tuple[str, str, str]:
    if len(instruction.labels) != 3:
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects {opcode} to have three labels"
        )
    return instruction.labels


def _single_label(
    instruction: AssemblyInstruction,
    opcode: str,
    adapter_name: str,
) -> str:
    if len(instruction.labels) != 1:
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects {opcode} to have one label"
        )
    return instruction.labels[0]


def _validate_tcall_width(
    instruction: AssemblyInstruction,
    adapter_name: str,
) -> None:
    if instruction.result_width > len(instruction.registers):
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects TCALL result width to fit registers"
        )


def _instruction_memory(
    instruction: AssemblyInstruction,
    opcode: str,
    adapter_name: str,
) -> int:
    if instruction.memory is None:
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects {opcode} memory object"
        )
    return instruction.memory


def _require_no_extra_operands(
    instruction: AssemblyInstruction,
    opcode: str,
    adapter_name: str,
    *,
    allow_immediate: bool = False,
    allow_callee: bool = False,
    allow_labels: bool = False,
    allow_memory: bool = False,
    allow_static_string: bool = False,
) -> None:
    if (
        (instruction.immediate is not None and not allow_immediate)
        or (instruction.callee is not None and not allow_callee)
        or (instruction.labels and not allow_labels)
        or (instruction.memory is not None and not allow_memory)
        or (instruction.static_string is not None and not allow_static_string)
    ):
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} found unsupported {opcode} operands"
        )


def _register(register: int) -> str:
    return f"r{register}"


def _register_group(registers: tuple[int, ...]) -> str:
    if len(registers) == 1:
        return _register(registers[0])
    return "[" + ", ".join(_register(register) for register in registers) + "]"


def _type_group(types: tuple[AssemblyType, ...]) -> str:
    if len(types) == 1:
        return types[0].value
    return "[" + ", ".join(type_name.value for type_name in types) + "]"


def _memory(memory: int) -> str:
    return f"m{memory}"
