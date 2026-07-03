"""Typed, labelled textual S3 Assembly representation, parser, and renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .diagnostics import SourceLocation


class AssemblyError(Exception):
    """Base error for malformed assembly or invalid assembly execution."""


class AssemblyParseError(AssemblyError):
    def __init__(self, message: str, line: int):
        self.message = message
        self.line = line
        super().__init__(f"assembly line {line}: {message}")


class AssemblyType(Enum):
    TRIT = "trit"
    TRYTE = "tryte"


class AssemblyOpcode(Enum):
    TCONST = "TCONST"
    TMOV = "TMOV"
    TINV = "TINV"
    TADD = "TADD"
    TMIN = "TMIN"
    TMAX = "TMAX"
    TCMP = "TCMP"
    TCALL = "TCALL"
    TRET = "TRET"
    TJMP = "TJMP"
    TBR3 = "TBR3"


TERMINATOR_OPCODES = {
    AssemblyOpcode.TRET,
    AssemblyOpcode.TJMP,
    AssemblyOpcode.TBR3,
}


@dataclass(frozen=True, slots=True)
class AssemblyParameter:
    register: int
    type: AssemblyType

    def render(self) -> str:
        return f"    .param r{self.register}, {self.type.value}"


@dataclass(frozen=True, slots=True)
class AssemblyInstruction:
    opcode: AssemblyOpcode
    registers: tuple[int, ...] = ()
    immediate: int | None = None
    callee: str | None = None
    labels: tuple[str, ...] = ()
    source: SourceLocation | None = None
    line: int | None = field(default=None, compare=False)

    @property
    def is_terminator(self) -> bool:
        return self.opcode in TERMINATOR_OPCODES

    def render(self) -> str:
        if self.opcode is AssemblyOpcode.TCONST:
            assert self.immediate is not None
            operands = f"r{self.registers[0]}, {self.immediate}"
        elif self.opcode is AssemblyOpcode.TCALL:
            assert self.callee is not None
            parts = [f"r{self.registers[0]}", self.callee]
            parts.extend(f"r{register}" for register in self.registers[1:])
            operands = ", ".join(parts)
        elif self.opcode is AssemblyOpcode.TJMP:
            operands = self.labels[0]
        elif self.opcode is AssemblyOpcode.TBR3:
            operands = ", ".join(
                (f"r{self.registers[0]}", *self.labels)
            )
        else:
            operands = ", ".join(f"r{register}" for register in self.registers)
        rendered = f"    {self.opcode.value:<6} {operands}"
        if self.source is not None:
            rendered += (
                f" ; source={self.source.line}:{self.source.column}:"
                f"{self.source.offset}"
            )
        return rendered


@dataclass(frozen=True, slots=True)
class AssemblyBlock:
    label: str
    instructions: tuple[AssemblyInstruction, ...]

    def render(self) -> str:
        lines = [f".label {self.label}"]
        lines.extend(instruction.render() for instruction in self.instructions)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AssemblyFunction:
    name: str
    return_type: AssemblyType
    parameters: tuple[AssemblyParameter, ...]
    register_types: tuple[tuple[int, AssemblyType], ...]
    blocks: tuple[AssemblyBlock, ...]

    @property
    def instructions(self) -> tuple[AssemblyInstruction, ...]:
        """Flattened compatibility/debug view; labels remain authoritative."""

        return tuple(
            instruction
            for block in self.blocks
            for instruction in block.instructions
        )

    @property
    def all_register_types(self) -> dict[int, AssemblyType]:
        result = dict(self.register_types)
        result.update(
            (parameter.register, parameter.type)
            for parameter in self.parameters
        )
        return result

    def type_of(self, register: int) -> AssemblyType | None:
        return self.all_register_types.get(register)

    def render(self) -> str:
        lines = [f".function {self.name} -> {self.return_type.value}"]
        lines.extend(parameter.render() for parameter in self.parameters)
        lines.extend(
            f"    .register r{register}, {type_name.value}"
            for register, type_name in self.register_types
        )
        lines.extend(block.render() for block in self.blocks)
        lines.append(".end")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AssemblyProgram:
    functions: tuple[AssemblyFunction, ...]

    def render(self) -> str:
        return "\n\n".join(function.render() for function in self.functions) + "\n"


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_FUNCTION_PATTERN = re.compile(
    rf"^\.function\s+({_IDENTIFIER})\s*->\s*(trit|tryte)$"
)
_DECLARATION_PATTERN = re.compile(
    r"^\.(param|register)\s+(r[0-9]+)\s*,\s*(trit|tryte)$"
)
_LABEL_PATTERN = re.compile(rf"^\.label\s+({_IDENTIFIER})$")
_INSTRUCTION_PATTERN = re.compile(r"^([A-Za-z0-9_]+)(?:\s+(.*))?$")
_REGISTER_PATTERN = re.compile(r"^r([0-9]+)$")
_IDENTIFIER_PATTERN = re.compile(rf"^{_IDENTIFIER}$")
_SOURCE_PATTERN = re.compile(r"^source=([0-9]+):([0-9]+):([0-9]+)$")


def _parse_register(text: str, line: int) -> int:
    match = _REGISTER_PATTERN.fullmatch(text.strip())
    if match is None:
        raise AssemblyParseError(f"invalid register '{text.strip()}'", line)
    return int(match.group(1))


def _parse_label(text: str, line: int) -> str:
    label = text.strip()
    if _IDENTIFIER_PATTERN.fullmatch(label) is None:
        raise AssemblyParseError(f"invalid label '{label}'", line)
    return label


def _parse_source_metadata(
    comment: str,
    line: int,
) -> SourceLocation | None:
    comment = comment.strip()
    if not comment:
        return None
    match = _SOURCE_PATTERN.fullmatch(comment)
    if match is None:
        if comment.startswith("source="):
            raise AssemblyParseError("invalid source metadata", line)
        return None
    source_line, column, offset = (int(part) for part in match.groups())
    if source_line < 1 or column < 1:
        raise AssemblyParseError("source line and column must be positive", line)
    return SourceLocation(offset, source_line, column)


def _parse_instruction(
    text: str,
    line: int,
    source: SourceLocation | None,
) -> AssemblyInstruction:
    match = _INSTRUCTION_PATTERN.fullmatch(text)
    if match is None:
        raise AssemblyParseError("invalid instruction syntax", line)
    opcode_text, operands_text = match.groups()
    try:
        opcode = AssemblyOpcode(opcode_text.upper())
    except ValueError as error:
        raise AssemblyParseError(f"unknown opcode '{opcode_text}'", line) from error
    operands = (
        []
        if operands_text is None
        else [operand.strip() for operand in operands_text.split(",")]
    )
    if any(not operand for operand in operands):
        raise AssemblyParseError(f"{opcode.value} has an empty operand", line)

    fixed_counts = {
        AssemblyOpcode.TCONST: 2,
        AssemblyOpcode.TMOV: 2,
        AssemblyOpcode.TINV: 2,
        AssemblyOpcode.TADD: 3,
        AssemblyOpcode.TMIN: 3,
        AssemblyOpcode.TMAX: 3,
        AssemblyOpcode.TCMP: 3,
        AssemblyOpcode.TRET: 1,
        AssemblyOpcode.TJMP: 1,
        AssemblyOpcode.TBR3: 4,
    }
    if opcode is not AssemblyOpcode.TCALL:
        expected = fixed_counts[opcode]
        if len(operands) != expected:
            raise AssemblyParseError(
                f"{opcode.value} expects {expected} operand(s), got "
                f"{len(operands)}",
                line,
            )
    elif len(operands) < 2:
        raise AssemblyParseError(
            f"TCALL expects at least 2 operands, got {len(operands)}",
            line,
        )

    if opcode is AssemblyOpcode.TCONST:
        destination = _parse_register(operands[0], line)
        try:
            immediate = int(operands[1], 10)
        except ValueError as error:
            raise AssemblyParseError(
                f"invalid decimal constant '{operands[1]}'",
                line,
            ) from error
        return AssemblyInstruction(
            opcode,
            (destination,),
            immediate=immediate,
            source=source,
            line=line,
        )
    if opcode is AssemblyOpcode.TCALL:
        destination = _parse_register(operands[0], line)
        callee = _parse_label(operands[1], line)
        arguments = tuple(
            _parse_register(operand, line) for operand in operands[2:]
        )
        return AssemblyInstruction(
            opcode,
            (destination, *arguments),
            callee=callee,
            source=source,
            line=line,
        )
    if opcode is AssemblyOpcode.TJMP:
        return AssemblyInstruction(
            opcode,
            labels=(_parse_label(operands[0], line),),
            source=source,
            line=line,
        )
    if opcode is AssemblyOpcode.TBR3:
        condition = _parse_register(operands[0], line)
        labels = tuple(_parse_label(operand, line) for operand in operands[1:])
        return AssemblyInstruction(
            opcode,
            (condition,),
            labels=labels,
            source=source,
            line=line,
        )
    registers = tuple(_parse_register(operand, line) for operand in operands)
    return AssemblyInstruction(
        opcode,
        registers,
        source=source,
        line=line,
    )


def parse_assembly(source: str) -> AssemblyProgram:
    functions: list[AssemblyFunction] = []
    function_names: set[str] = set()
    current_name: str | None = None
    current_return_type: AssemblyType | None = None
    parameters: list[AssemblyParameter] = []
    registers: dict[int, AssemblyType] = {}
    blocks: list[AssemblyBlock] = []
    block_labels: set[str] = set()
    current_label: str | None = None
    instructions: list[AssemblyInstruction] = []
    code_started = False

    def flush_block() -> None:
        nonlocal current_label, instructions
        if current_label is not None:
            blocks.append(AssemblyBlock(current_label, tuple(instructions)))
        current_label = None
        instructions = []

    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        code, separator, comment = raw_line.partition(";")
        text = code.strip()
        source_location = (
            _parse_source_metadata(comment, line_number)
            if separator and text
            else None
        )
        if not text:
            continue
        if current_name is None:
            match = _FUNCTION_PATTERN.fullmatch(text)
            if match is None:
                raise AssemblyParseError("expected '.function name -> type'", line_number)
            current_name, type_text = match.groups()
            if current_name in function_names:
                raise AssemblyParseError(
                    f"duplicate function '{current_name}'",
                    line_number,
                )
            function_names.add(current_name)
            current_return_type = AssemblyType(type_text)
            parameters = []
            registers = {}
            blocks = []
            block_labels = set()
            current_label = None
            instructions = []
            code_started = False
            continue

        if text == ".end":
            flush_block()
            assert current_return_type is not None
            functions.append(
                AssemblyFunction(
                    current_name,
                    current_return_type,
                    tuple(parameters),
                    tuple(sorted(registers.items())),
                    tuple(blocks),
                )
            )
            current_name = None
            current_return_type = None
            continue

        declaration = _DECLARATION_PATTERN.fullmatch(text)
        if declaration is not None:
            if code_started:
                raise AssemblyParseError(
                    "parameter and register declarations must precede labels "
                    "and instructions",
                    line_number,
                )
            kind, register_text, type_text = declaration.groups()
            register = _parse_register(register_text, line_number)
            declared = {
                **registers,
                **{parameter.register: parameter.type for parameter in parameters},
            }
            if register in declared:
                raise AssemblyParseError(
                    f"duplicate declaration of r{register}",
                    line_number,
                )
            type_name = AssemblyType(type_text)
            if kind == "param":
                parameters.append(AssemblyParameter(register, type_name))
            else:
                registers[register] = type_name
            continue

        label_match = _LABEL_PATTERN.fullmatch(text)
        if label_match is not None:
            code_started = True
            flush_block()
            label = label_match.group(1)
            if label in block_labels:
                raise AssemblyParseError(f"duplicate label '{label}'", line_number)
            block_labels.add(label)
            current_label = label
            continue

        if text.startswith("."):
            raise AssemblyParseError(f"unknown directive '{text}'", line_number)

        code_started = True
        if current_label is None:
            # Backward compatibility for 0.1 assembly without explicit labels.
            current_label = "entry"
            if current_label in block_labels:
                raise AssemblyParseError("duplicate implicit entry label", line_number)
            block_labels.add(current_label)
        instructions.append(
            _parse_instruction(text, line_number, source_location)
        )

    if current_name is not None:
        raise AssemblyParseError(
            f"function '{current_name}' is missing '.end'",
            len(source.splitlines()) + 1,
        )
    if not functions:
        raise AssemblyParseError("assembly contains no functions", 1)
    return AssemblyProgram(tuple(functions))

