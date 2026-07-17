"""Controlled adapters from ``AssemblyProgram`` to ``AssemblyTextRenderer``."""

from __future__ import annotations

from collections.abc import Callable

from bootstrap.s3.assembly import (
    ASSEMBLY_FORMAT_VERSION,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.assembly_text_renderer import (
    AssemblyTextRenderer,
    AssemblyTextSource,
)
from bootstrap.s3.static_text import StaticTextDocument


FIRST_PROGRAM_REGISTER_TYPES = tuple(
    (register, AssemblyType.TRYTE) for register in range(6)
)
FIRST_PROGRAM_OPCODES = (
    AssemblyOpcode.TCONST,
    AssemblyOpcode.TMOV,
    AssemblyOpcode.TCONST,
    AssemblyOpcode.TMOV,
    AssemblyOpcode.TINV,
    AssemblyOpcode.TADD,
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
    (6, AssemblyType.TRIT),
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
            AssemblyOpcode.TINV,
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
    (1, AssemblyType.TRYTE),
    (2, AssemblyType.TRIT),
)
SIGN_MAIN_BLOCKS = (
    (
        "entry",
        (
            AssemblyOpcode.TCONST,
            AssemblyOpcode.TINV,
            AssemblyOpcode.TCALL,
            AssemblyOpcode.TRET,
        ),
    ),
)

InstructionEmitter = Callable[[AssemblyTextRenderer, AssemblyInstruction], None]


class AssemblyProgramTextAdapterError(ValueError):
    """Raised when an ``AssemblyProgram`` is outside the supported adapter slice."""


class AssemblyProgramTextAdapter:
    """Render controlled fixture subsets through ``AssemblyTextRenderer``.

    This adapter reads real ``AssemblyProgram`` values for narrow fixture
    shapes. It does not replace ``AssemblyProgram.render`` and does not
    implement a general Assembly renderer.
    """

    def render_first_program(self, program: AssemblyProgram) -> StaticTextDocument:
        _validate_first_program_shape(program)

        function = program.functions[0]
        renderer = AssemblyTextRenderer()
        renderer.emit_header(program.version)
        _emit_function(renderer, function, _emit_first_instruction)
        return renderer.build()

    def render_simple_call_program(
        self,
        program: AssemblyProgram,
    ) -> StaticTextDocument:
        _validate_simple_call_program_shape(program)

        renderer = AssemblyTextRenderer()
        renderer.emit_header(program.version)
        _emit_function(
            renderer,
            program.functions[0],
            _emit_simple_call_instruction,
        )
        renderer.emit_blank_line()
        _emit_function(
            renderer,
            program.functions[1],
            _emit_simple_call_instruction,
        )
        return renderer.build()

    def render_sign_program(self, program: AssemblyProgram) -> StaticTextDocument:
        _validate_sign_program_shape(program)

        renderer = AssemblyTextRenderer()
        renderer.emit_header(program.version)
        _emit_function(renderer, program.functions[0], _emit_sign_instruction)
        renderer.emit_blank_line()
        _emit_function(renderer, program.functions[1], _emit_sign_instruction)
        return renderer.build()


def render_first_program(program: AssemblyProgram) -> StaticTextDocument:
    return AssemblyProgramTextAdapter().render_first_program(program)


def render_simple_call_program(program: AssemblyProgram) -> StaticTextDocument:
    return AssemblyProgramTextAdapter().render_simple_call_program(program)


def render_sign_program(program: AssemblyProgram) -> StaticTextDocument:
    return AssemblyProgramTextAdapter().render_sign_program(program)


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
            "first adapter expects registers r0..r5 as tryte"
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
            "sign adapter expects sign registers r1..r6 with fixture types"
        )
    _validate_blocks(function, SIGN_FUNCTION_BLOCKS, "sign adapter", "sign")


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


def _emit_function(
    renderer: AssemblyTextRenderer,
    function: AssemblyFunction,
    emit_instruction: InstructionEmitter,
) -> None:
    renderer.emit_function(function.name, function.return_type.value)
    for parameter in function.parameters:
        renderer.emit_param(parameter.register, parameter.type.value)
    for register, type_name in function.register_types:
        renderer.emit_register(register, type_name.value)
    for block in function.blocks:
        renderer.emit_label(block.label)
        for instruction in block.instructions:
            emit_instruction(renderer, instruction)
    renderer.emit_end()


def _emit_first_instruction(
    renderer: AssemblyTextRenderer,
    instruction: AssemblyInstruction,
) -> None:
    source = _source(instruction, "first adapter")
    opcode = instruction.opcode

    if opcode is AssemblyOpcode.TCONST:
        register = _single_register(instruction, "TCONST", "first adapter")
        if instruction.immediate is None:
            raise AssemblyProgramTextAdapterError(
                "first adapter expects TCONST immediate"
            )
        _require_no_extra_operands(
            instruction,
            "TCONST",
            "first adapter",
            allow_immediate=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(register),
            instruction.immediate,
            source=source,
        )
        return

    if opcode in {AssemblyOpcode.TMOV, AssemblyOpcode.TINV}:
        left, right = _register_pair(instruction, opcode.value, "first adapter")
        _require_no_extra_operands(instruction, opcode.value, "first adapter")
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TADD:
        left, middle, right = _register_triple(instruction, "TADD", "first adapter")
        _require_no_extra_operands(instruction, "TADD", "first adapter")
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(middle),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TRET:
        register = _single_register(instruction, "TRET", "first adapter")
        _require_no_extra_operands(instruction, "TRET", "first adapter")
        renderer.emit_instruction(opcode.value, _register(register), source=source)
        return

    raise AssemblyProgramTextAdapterError(
        f"first adapter does not support opcode {opcode.value}"
    )


def _emit_simple_call_instruction(
    renderer: AssemblyTextRenderer,
    instruction: AssemblyInstruction,
) -> None:
    source = _source(instruction, "simple_call adapter")
    opcode = instruction.opcode

    if opcode is AssemblyOpcode.TCONST:
        register = _single_register(instruction, "TCONST", "simple_call adapter")
        if instruction.immediate is None:
            raise AssemblyProgramTextAdapterError(
                "simple_call adapter expects TCONST immediate"
            )
        _require_no_extra_operands(
            instruction,
            "TCONST",
            "simple_call adapter",
            allow_immediate=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(register),
            instruction.immediate,
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TADD:
        left, middle, right = _register_triple(
            instruction,
            "TADD",
            "simple_call adapter",
        )
        _require_no_extra_operands(instruction, "TADD", "simple_call adapter")
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(middle),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TCALL:
        target, left, right = _register_triple(
            instruction,
            "TCALL",
            "simple_call adapter",
        )
        if instruction.callee is None:
            raise AssemblyProgramTextAdapterError(
                "simple_call adapter expects TCALL callee"
            )
        _require_no_extra_operands(
            instruction,
            "TCALL",
            "simple_call adapter",
            allow_callee=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(target),
            instruction.callee,
            _register(left),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TRET:
        register = _single_register(instruction, "TRET", "simple_call adapter")
        _require_no_extra_operands(instruction, "TRET", "simple_call adapter")
        renderer.emit_instruction(opcode.value, _register(register), source=source)
        return

    raise AssemblyProgramTextAdapterError(
        f"simple_call adapter does not support opcode {opcode.value}"
    )


def _emit_sign_instruction(
    renderer: AssemblyTextRenderer,
    instruction: AssemblyInstruction,
) -> None:
    source = _source(instruction, "sign adapter")
    opcode = instruction.opcode

    if opcode is AssemblyOpcode.TCONST:
        register = _single_register(instruction, "TCONST", "sign adapter")
        if instruction.immediate is None:
            raise AssemblyProgramTextAdapterError(
                "sign adapter expects TCONST immediate"
            )
        _require_no_extra_operands(
            instruction,
            "TCONST",
            "sign adapter",
            allow_immediate=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(register),
            instruction.immediate,
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TCMP:
        left, middle, right = _register_triple(
            instruction,
            opcode.value,
            "sign adapter",
        )
        _require_no_extra_operands(instruction, opcode.value, "sign adapter")
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(middle),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TINV:
        left, right = _register_pair(instruction, "TINV", "sign adapter")
        _require_no_extra_operands(instruction, "TINV", "sign adapter")
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TBR3:
        condition = _single_register(instruction, "TBR3", "sign adapter")
        labels = _label_triple(instruction, "TBR3", "sign adapter")
        _require_no_extra_operands(
            instruction,
            "TBR3",
            "sign adapter",
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
        target, argument = _register_pair(instruction, "TCALL", "sign adapter")
        if instruction.callee is None:
            raise AssemblyProgramTextAdapterError(
                "sign adapter expects TCALL callee"
            )
        _require_no_extra_operands(
            instruction,
            "TCALL",
            "sign adapter",
            allow_callee=True,
        )
        renderer.emit_instruction(
            opcode.value,
            _register(target),
            instruction.callee,
            _register(argument),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TRET:
        register = _single_register(instruction, "TRET", "sign adapter")
        _require_no_extra_operands(instruction, "TRET", "sign adapter")
        renderer.emit_instruction(opcode.value, _register(register), source=source)
        return

    raise AssemblyProgramTextAdapterError(
        f"sign adapter does not support opcode {opcode.value}"
    )


def _source(instruction: AssemblyInstruction, adapter_name: str) -> AssemblyTextSource:
    if instruction.source is None:
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} expects source metadata for {instruction.opcode.value}"
        )
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


def _require_no_extra_operands(
    instruction: AssemblyInstruction,
    opcode: str,
    adapter_name: str,
    *,
    allow_immediate: bool = False,
    allow_callee: bool = False,
    allow_labels: bool = False,
) -> None:
    if (
        (instruction.immediate is not None and not allow_immediate)
        or (instruction.callee is not None and not allow_callee)
        or (instruction.labels and not allow_labels)
        or instruction.memory is not None
    ):
        raise AssemblyProgramTextAdapterError(
            f"{adapter_name} found unsupported {opcode} operands"
        )


def _register(register: int) -> str:
    return f"r{register}"
