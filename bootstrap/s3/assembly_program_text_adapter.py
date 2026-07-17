"""First-slice adapter from ``AssemblyProgram`` to ``AssemblyTextRenderer``."""

from __future__ import annotations

from bootstrap.s3.assembly import (
    ASSEMBLY_FORMAT_VERSION,
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


class AssemblyProgramTextAdapterError(ValueError):
    """Raised when an ``AssemblyProgram`` is outside the supported adapter slice."""


class AssemblyProgramTextAdapter:
    """Render the first fixture subset through ``AssemblyTextRenderer``.

    This adapter is deliberately first-only. It reads the real ``AssemblyProgram``
    model but does not replace ``AssemblyProgram.render`` and does not implement
    a general Assembly renderer.
    """

    def render_first_program(self, program: AssemblyProgram) -> StaticTextDocument:
        _validate_first_program_shape(program)

        function = program.functions[0]
        block = function.blocks[0]
        renderer = AssemblyTextRenderer()
        renderer.emit_header(program.version)
        renderer.emit_function(function.name, function.return_type.value)
        for register, type_name in function.register_types:
            renderer.emit_register(register, type_name.value)
        renderer.emit_label(block.label)
        for instruction in block.instructions:
            _emit_first_instruction(renderer, instruction)
        renderer.emit_end()
        return renderer.build()


def render_first_program(program: AssemblyProgram) -> StaticTextDocument:
    return AssemblyProgramTextAdapter().render_first_program(program)


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


def _emit_first_instruction(
    renderer: AssemblyTextRenderer,
    instruction: AssemblyInstruction,
) -> None:
    source = _source(instruction)
    opcode = instruction.opcode

    if opcode is AssemblyOpcode.TCONST:
        register = _single_register(instruction, "TCONST")
        if instruction.immediate is None:
            raise AssemblyProgramTextAdapterError(
                "first adapter expects TCONST immediate"
            )
        _require_no_extra_operands(instruction, "TCONST")
        renderer.emit_instruction(
            opcode.value,
            _register(register),
            instruction.immediate,
            source=source,
        )
        return

    if opcode in {AssemblyOpcode.TMOV, AssemblyOpcode.TINV}:
        left, right = _register_pair(instruction, opcode.value)
        _require_no_extra_operands(instruction, opcode.value)
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TADD:
        left, middle, right = _register_triple(instruction, "TADD")
        _require_no_extra_operands(instruction, "TADD")
        renderer.emit_instruction(
            opcode.value,
            _register(left),
            _register(middle),
            _register(right),
            source=source,
        )
        return

    if opcode is AssemblyOpcode.TRET:
        register = _single_register(instruction, "TRET")
        _require_no_extra_operands(instruction, "TRET")
        renderer.emit_instruction(opcode.value, _register(register), source=source)
        return

    raise AssemblyProgramTextAdapterError(
        f"first adapter does not support opcode {opcode.value}"
    )


def _source(instruction: AssemblyInstruction) -> AssemblyTextSource:
    if instruction.source is None:
        raise AssemblyProgramTextAdapterError(
            f"first adapter expects source metadata for {instruction.opcode.value}"
        )
    source = instruction.source
    return AssemblyTextSource(source.line, source.column, source.offset)


def _single_register(instruction: AssemblyInstruction, opcode: str) -> int:
    if len(instruction.registers) != 1:
        raise AssemblyProgramTextAdapterError(
            f"first adapter expects {opcode} to have one register"
        )
    return instruction.registers[0]


def _register_pair(instruction: AssemblyInstruction, opcode: str) -> tuple[int, int]:
    if len(instruction.registers) != 2:
        raise AssemblyProgramTextAdapterError(
            f"first adapter expects {opcode} to have two registers"
        )
    return instruction.registers


def _register_triple(
    instruction: AssemblyInstruction,
    opcode: str,
) -> tuple[int, int, int]:
    if len(instruction.registers) != 3:
        raise AssemblyProgramTextAdapterError(
            f"first adapter expects {opcode} to have three registers"
        )
    return instruction.registers


def _require_no_extra_operands(
    instruction: AssemblyInstruction,
    opcode: str,
) -> None:
    if (
        instruction.callee is not None
        or instruction.labels
        or instruction.memory is not None
    ):
        raise AssemblyProgramTextAdapterError(
            f"first adapter found unsupported {opcode} operands"
        )


def _register(register: int) -> str:
    return f"r{register}"
