"""Typed, labelled textual S3 Assembly representation, parser, and renderer."""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from enum import Enum

from .diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    DiagnosticSource,
    SourceLocation,
)
from .static_text import StaticTextDecodeError, decode_static_text


ASSEMBLY_FORMAT_VERSION = "0.6.0"
ASSEMBLY_LEGACY_FORMAT_VERSION = "0.5.0"


class AssemblyError(Exception):
    """Base error for malformed assembly or invalid assembly execution."""

    diagnostic_category = DiagnosticCategory.VERIFICATION
    diagnostic_code = DiagnosticCode.ASSEMBLY_INVALID_PROGRAM
    diagnostic_phase = DiagnosticPhase.ASSEMBLY


class AssemblyParseError(AssemblyError):
    diagnostic_category = DiagnosticCategory.ARTIFACT
    diagnostic_code = DiagnosticCode.ARTIFACT_INVALID_ASSEMBLY
    diagnostic_phase = DiagnosticPhase.ARTIFACT_READ

    def __init__(
        self,
        message: str,
        line: int,
        *,
        diagnostic_category: DiagnosticCategory | None = None,
        diagnostic_code: DiagnosticCode | None = None,
    ):
        self.message = message
        self.diagnostic_message = message
        self.line = line
        if diagnostic_category is not None:
            self.diagnostic_category = diagnostic_category
        if diagnostic_code is not None:
            self.diagnostic_code = diagnostic_code
        self.diagnostic_context = {
            "source": DiagnosticSource(line=line),
        }
        super().__init__(f"assembly line {line}: {message}")


class AssemblyType(Enum):
    TRIT = "trit"
    TRYTE = "tryte"
    I64 = "i64"
    F64 = "f64"
    STRING = "string"
    REFERENCE = "reference"


class AssemblyOpcode(Enum):
    TCONST = "TCONST"
    TCONST_STR = "TCONST_STR"
    TMOV = "TMOV"
    TINV = "TINV"
    TADD = "TADD"
    TNDIFF = "TNDIFF"
    TMUL = "TMUL"
    TDIV = "TDIV"
    TREL = "TREL"
    TCVT = "TCVT"
    TMIN = "TMIN"
    TMAX = "TMAX"
    TCMP = "TCMP"
    TCALL = "TCALL"
    TLOAD = "TLOAD"
    TSTORE = "TSTORE"
    TRET = "TRET"
    TJMP = "TJMP"
    TBR3 = "TBR3"
    TADDR = "TADDR"
    TREFLOAD = "TREFLOAD"
    TREFSTORE = "TREFSTORE"
    TSLEN = "TSLEN"
    TSLOAD = "TSLOAD"
    TSSTORE = "TSSTORE"


TERMINATOR_OPCODES = {
    AssemblyOpcode.TRET,
    AssemblyOpcode.TJMP,
    AssemblyOpcode.TBR3,
}


@dataclass(frozen=True, slots=True)
class AssemblyStaticString:
    id: str
    value: str

    def render(self) -> str:
        return f'{self.id} "{_escape_static_string(self.value)}"'


@dataclass(frozen=True, slots=True)
class AssemblyParameter:
    register: int
    type: AssemblyType
    reference_target: AssemblyType | None = None
    reference_mutable: bool = False
    reference_is_slice: bool = False

    def render(self) -> str:
        return f"    .param r{self.register}, {self.type.value}"


@dataclass(frozen=True, slots=True)
class AssemblyMemoryObject:
    index: int
    element_type: AssemblyType
    length: int
    mutable: bool

    @property
    def name(self) -> str:
        return f"m{self.index}"

    def render(self) -> str:
        mutability = "mutable" if self.mutable else "immutable"
        return (
            f"    .memory {self.name}, {self.element_type.value}, "
            f"{self.length}, {mutability}"
        )


@dataclass(frozen=True, slots=True)
class AssemblyInstruction:
    opcode: AssemblyOpcode
    registers: tuple[int, ...] = ()
    immediate: int | float | None = None
    static_string: str | None = None
    callee: str | None = None
    labels: tuple[str, ...] = ()
    memory: int | None = None
    source: SourceLocation | None = None
    line: int | None = field(default=None, compare=False)
    result_width: int = 1
    reference_target: AssemblyType | None = None
    reference_mutable: bool = False
    reference_is_slice: bool = False

    def __post_init__(self) -> None:
        if self.result_width < 0:
            raise ValueError("AssemblyInstruction result_width must be non-negative")

    @property
    def result_registers(self) -> tuple[int, ...]:
        if self.opcode is AssemblyOpcode.TCALL:
            return self.registers[: self.result_width]
        return self.registers

    @property
    def argument_registers(self) -> tuple[int, ...]:
        if self.opcode is AssemblyOpcode.TCALL:
            return self.registers[self.result_width :]
        return ()

    @property
    def is_terminator(self) -> bool:
        return self.opcode in TERMINATOR_OPCODES

    def render(self) -> str:
        if self.opcode is AssemblyOpcode.TCONST:
            assert self.immediate is not None
            operands = f"r{self.registers[0]}, {self.immediate}"
        elif self.opcode is AssemblyOpcode.TCONST_STR:
            assert self.static_string is not None
            operands = f"r{self.registers[0]}, {self.static_string}"
        elif self.opcode is AssemblyOpcode.TREL:
            assert self.immediate is not None
            operands = ", ".join(f"r{register}" for register in self.registers)
            operands += f", {self.immediate}"
        elif self.opcode is AssemblyOpcode.TCALL:
            assert self.callee is not None
            parts = [_render_register_group(self.result_registers), self.callee]
            parts.extend(f"r{register}" for register in self.argument_registers)
            operands = ", ".join(parts)
        elif self.opcode is AssemblyOpcode.TJMP:
            operands = self.labels[0]
        elif self.opcode is AssemblyOpcode.TBR3:
            operands = ", ".join(
                (f"r{self.registers[0]}", *self.labels)
            )
        elif self.opcode is AssemblyOpcode.TLOAD:
            assert self.memory is not None
            operands = (
                f"r{self.registers[0]}, m{self.memory}, "
                f"r{self.registers[1]}"
            )
        elif self.opcode is AssemblyOpcode.TSTORE:
            assert self.memory is not None
            operands = (
                f"m{self.memory}, r{self.registers[0]}, "
                f"r{self.registers[1]}"
            )
        elif self.opcode is AssemblyOpcode.TRET:
            operands = _render_register_group(self.registers)
        elif self.opcode is AssemblyOpcode.TADDR:
            if self.memory is not None:
                operands = f"r{self.registers[0]}, m{self.memory}"
                if len(self.registers) > 1:
                    operands += f", r{self.registers[1]}"
            else:
                operands = ", ".join(f"r{register}" for register in self.registers)
        elif self.opcode in {AssemblyOpcode.TREFLOAD, AssemblyOpcode.TREFSTORE}:
            operands = ", ".join(f"r{register}" for register in self.registers)
        elif self.opcode is AssemblyOpcode.TSLEN:
            operands = f"r{self.registers[0]}, r{self.registers[1]}"
        elif self.opcode is AssemblyOpcode.TSLOAD:
            operands = ", ".join(f"r{register}" for register in self.registers)
        elif self.opcode is AssemblyOpcode.TSSTORE:
            operands = ", ".join(f"r{register}" for register in self.registers)
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
    memory_objects: tuple[AssemblyMemoryObject, ...] = ()
    result_types: tuple[AssemblyType, ...] = ()
    reference_targets: tuple[tuple[int, AssemblyType, bool], ...] = ()
    reference_storage_sizes: tuple[tuple[int, int], ...] = ()
    slice_registers: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.result_types:
            object.__setattr__(self, "result_types", (self.return_type,))

    @property
    def result_width(self) -> int:
        return len(self.result_types)

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

    def reference_info(self, register: int) -> tuple[AssemblyType, bool] | None:
        for index, target, mutable in self.reference_targets:
            if index == register:
                return target, mutable
        for parameter in self.parameters:
            if parameter.register == register and parameter.type is AssemblyType.REFERENCE:
                if parameter.reference_target is None:
                    return None
                return parameter.reference_target, parameter.reference_mutable
        return None

    def reference_storage_size(self, register: int) -> int:
        for index, size in self.reference_storage_sizes:
            if index == register:
                return size
        return 8

    def render(self) -> str:
        lines = [f".function {self.name} -> {_render_type_group(self.result_types)}"]
        lines.extend(parameter.render() for parameter in self.parameters)
        lines.extend(
            f"    .register r{register}, {type_name.value}"
            for register, type_name in self.register_types
        )
        lines.extend(memory.render() for memory in self.memory_objects)
        lines.extend(block.render() for block in self.blocks)
        lines.append(".end")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AssemblyProgram:
    functions: tuple[AssemblyFunction, ...]
    version: str = ASSEMBLY_FORMAT_VERSION
    static_strings: tuple[AssemblyStaticString, ...] = ()

    def render(self) -> str:
        from .assembly_program_text_adapter import render_supported_program

        return render_supported_program(self).text


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_TYPE = r"trit|tryte|i64|f64|string|reference"
_STATIC_STRING_ID = r"s[0-9]+"
_FUNCTION_PATTERN = re.compile(rf"^\.function\s+({_IDENTIFIER})\s*->\s*(.+)$")
_DECLARATION_PATTERN = re.compile(
    rf"^\.(param|register)\s+(r[0-9]+)\s*,\s*({_TYPE})$"
)
_MEMORY_DECLARATION_PATTERN = re.compile(
    rf"^\.memory\s+(m[0-9]+)\s*,\s*({_TYPE})\s*,\s*"
    r"(-?[0-9]+)(?:\s*,\s*(mutable|immutable))?$"
)
_LABEL_PATTERN = re.compile(rf"^\.label\s+({_IDENTIFIER})$")
_INSTRUCTION_PATTERN = re.compile(r"^([A-Za-z0-9_]+)(?:\s+(.*))?$")
_REGISTER_PATTERN = re.compile(r"^r([0-9]+)$")
_MEMORY_PATTERN = re.compile(r"^m([0-9]+)$")
_IDENTIFIER_PATTERN = re.compile(rf"^{_IDENTIFIER}$")
_STATIC_STRING_ID_PATTERN = re.compile(rf"^{_STATIC_STRING_ID}$")
_STATIC_STRING_PATTERN = re.compile(rf"^({_STATIC_STRING_ID})\s+\"(.*)\"$")
_SOURCE_PATTERN = re.compile(r"^source=([0-9]+):([0-9]+):([0-9]+)$")
_VERSION_PATTERN = re.compile(r"^\.s3asm\s+([0-9]+\.[0-9]+\.[0-9]+)$")


def _escape_static_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


def _parse_register(text: str, line: int) -> int:
    match = _REGISTER_PATTERN.fullmatch(text.strip())
    if match is None:
        raise AssemblyParseError(f"invalid register '{text.strip()}'", line)
    return int(match.group(1))


def _render_register_group(registers: tuple[int, ...]) -> str:
    if len(registers) == 1:
        return f"r{registers[0]}"
    return "[" + ", ".join(f"r{register}" for register in registers) + "]"


def _render_type_group(types: tuple[AssemblyType, ...]) -> str:
    if len(types) == 1:
        return types[0].value
    return "[" + ", ".join(type_name.value for type_name in types) + "]"


def _split_operands(text: str | None, line: int) -> list[str]:
    if text is None:
        return []
    operands: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth < 0:
                raise AssemblyParseError("malformed operand list", line)
        if char == "," and depth == 0:
            operands.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if depth != 0:
        raise AssemblyParseError("malformed operand list", line)
    operands.append("".join(current).strip())
    return operands


def _parse_register_group(
    text: str,
    line: int,
    *,
    allow_empty: bool = False,
) -> tuple[int, ...]:
    text = text.strip()
    if text.startswith("["):
        if not text.endswith("]"):
            raise AssemblyParseError("malformed register list", line)
        inner = text[1:-1].strip()
        if not inner:
            if allow_empty:
                return ()
            raise AssemblyParseError("register list must not be empty", line)
        return tuple(
            _parse_register(part, line) for part in _split_operands(inner, line)
        )
    return (_parse_register(text, line),)


def _parse_type_group(text: str, line: int) -> tuple[AssemblyType, ...]:
    text = text.strip()
    try:
        if text.startswith("["):
            if not text.endswith("]"):
                raise AssemblyParseError("malformed result type list", line)
            inner = text[1:-1].strip()
            if not inner:
                raise AssemblyParseError("result type list must not be empty", line)
            return tuple(
                AssemblyType(part.strip()) for part in _split_operands(inner, line)
            )
        return (AssemblyType(text),)
    except ValueError as error:
        raise AssemblyParseError("unknown result type in function signature", line) from error


def _parse_memory(text: str, line: int) -> int:
    match = _MEMORY_PATTERN.fullmatch(text.strip())
    if match is None:
        raise AssemblyParseError(f"invalid memory object '{text.strip()}'", line)
    return int(match.group(1))


def _parse_label(text: str, line: int) -> str:
    label = text.strip()
    if _IDENTIFIER_PATTERN.fullmatch(label) is None:
        raise AssemblyParseError(f"invalid label '{label}'", line)
    return label


def _parse_static_string_id(text: str, line: int) -> str:
    static_string = text.strip()
    if _STATIC_STRING_ID_PATTERN.fullmatch(static_string) is None:
        raise AssemblyParseError(
            f"invalid static string id '{static_string}'",
            line,
        )
    return static_string


def _parse_static_string(text: str, line: int) -> AssemblyStaticString:
    match = _STATIC_STRING_PATTERN.fullmatch(text)
    if match is None:
        raise AssemblyParseError("invalid static string entry", line)
    static_id, raw_value = match.groups()
    try:
        value = decode_static_text(raw_value)
    except StaticTextDecodeError as error:
        raise AssemblyParseError(str(error), line) from error
    return AssemblyStaticString(static_id, value)


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
    *,
    version: str,
) -> AssemblyInstruction:
    match = _INSTRUCTION_PATTERN.fullmatch(text)
    if match is None:
        raise AssemblyParseError("invalid instruction syntax", line)
    opcode_text, operands_text = match.groups()
    try:
        opcode = AssemblyOpcode(opcode_text.upper())
    except ValueError as error:
        raise AssemblyParseError(f"unknown opcode '{opcode_text}'", line) from error
    operands = _split_operands(operands_text, line)
    if any(not operand for operand in operands):
        raise AssemblyParseError(f"{opcode.value} has an empty operand", line)

    fixed_counts = {
        AssemblyOpcode.TCONST: 2,
        AssemblyOpcode.TCONST_STR: 2,
        AssemblyOpcode.TMOV: 2,
        AssemblyOpcode.TINV: 2,
        AssemblyOpcode.TADD: 3,
        AssemblyOpcode.TNDIFF: 3,
        AssemblyOpcode.TMUL: 3,
        AssemblyOpcode.TDIV: 3,
        AssemblyOpcode.TREL: 4,
        AssemblyOpcode.TCVT: 2,
        AssemblyOpcode.TMIN: 3,
        AssemblyOpcode.TMAX: 3,
        AssemblyOpcode.TCMP: 3,
        AssemblyOpcode.TLOAD: 3,
        AssemblyOpcode.TSTORE: 3,
        AssemblyOpcode.TJMP: 1,
        AssemblyOpcode.TBR3: 4,
        AssemblyOpcode.TADDR: 2,
        AssemblyOpcode.TREFLOAD: 2,
        AssemblyOpcode.TREFSTORE: 2,
    }
    if opcode is AssemblyOpcode.TRET:
        if len(operands) != 1:
            raise AssemblyParseError(
                f"{opcode.value} expects 1 operand group, got {len(operands)}",
                line,
            )
    elif opcode is not AssemblyOpcode.TCALL:
        expected = fixed_counts[opcode]
        valid_counts = {expected}
        if opcode is AssemblyOpcode.TADDR:
            valid_counts.add(3)
        if len(operands) not in valid_counts:
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
            lowered = operands[1].lower()
            immediate = (
                float(operands[1])
                if lowered in {"nan", "inf", "+inf", "-inf"}
                or any(character in lowered for character in (".", "e"))
                else int(operands[1], 10)
            )
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
    if opcode is AssemblyOpcode.TREL:
        try:
            relation = int(operands[3], 10)
        except ValueError as error:
            raise AssemblyParseError("TREL relation code must be an integer", line) from error
        return AssemblyInstruction(
            opcode,
            tuple(_parse_register(operand, line) for operand in operands[:3]),
            immediate=relation,
            source=source,
            line=line,
        )
    if opcode is AssemblyOpcode.TCONST_STR:
        destination = _parse_register(operands[0], line)
        return AssemblyInstruction(
            opcode,
            (destination,),
            static_string=_parse_static_string_id(operands[1], line),
            source=source,
            line=line,
        )
    if opcode is AssemblyOpcode.TCALL:
        destinations = _parse_register_group(operands[0], line, allow_empty=True)
        if version == ASSEMBLY_LEGACY_FORMAT_VERSION and (
            len(destinations) != 1 or operands[0].strip().startswith("[")
        ):
            raise AssemblyParseError(
                "0.5.0 TCALL cannot use result destination lists",
                line,
            )
        callee = _parse_label(operands[1], line)
        arguments = tuple(
            _parse_register(operand, line) for operand in operands[2:]
        )
        return AssemblyInstruction(
            opcode,
            (*destinations, *arguments),
            callee=callee,
            source=source,
            line=line,
            result_width=len(destinations),
        )
    if opcode is AssemblyOpcode.TLOAD:
        return AssemblyInstruction(
            opcode,
            (
                _parse_register(operands[0], line),
                _parse_register(operands[2], line),
            ),
            memory=_parse_memory(operands[1], line),
            source=source,
            line=line,
        )
    if opcode is AssemblyOpcode.TSTORE:
        return AssemblyInstruction(
            opcode,
            (
                _parse_register(operands[1], line),
                _parse_register(operands[2], line),
            ),
            memory=_parse_memory(operands[0], line),
            source=source,
            line=line,
        )
    if opcode is AssemblyOpcode.TADDR and operands[1].startswith("m"):
        return AssemblyInstruction(
            opcode,
            (
                _parse_register(operands[0], line),
                *(
                    (_parse_register(operands[2], line),)
                    if len(operands) == 3
                    else ()
                ),
            ),
            memory=_parse_memory(operands[1], line),
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
    if opcode is AssemblyOpcode.TRET:
        registers = _parse_register_group(operands[0], line)
        if version == ASSEMBLY_LEGACY_FORMAT_VERSION and (
            len(registers) != 1 or operands[0].strip().startswith("[")
        ):
            raise AssemblyParseError(
                "0.5.0 TRET cannot use result operand lists",
                line,
            )
        return AssemblyInstruction(
            opcode,
            registers,
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
    static_strings: list[AssemblyStaticString] = []
    static_string_ids: set[str] = set()
    functions: list[AssemblyFunction] = []
    function_names: set[str] = set()
    current_name: str | None = None
    current_return_type: AssemblyType | None = None
    current_result_types: tuple[AssemblyType, ...] = ()
    parameters: list[AssemblyParameter] = []
    registers: dict[int, AssemblyType] = {}
    memory_objects: dict[int, AssemblyMemoryObject] = {}
    blocks: list[AssemblyBlock] = []
    block_labels: set[str] = set()
    current_label: str | None = None
    instructions: list[AssemblyInstruction] = []
    code_started = False
    artifact_started = False
    data_started = False
    in_data_section = False
    version = ASSEMBLY_FORMAT_VERSION

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
        if text.startswith(".s3asm"):
            if (
                artifact_started
                or current_name is not None
                or functions
                or static_strings
                or data_started
            ):
                raise AssemblyParseError(
                    ".s3asm version must precede all functions",
                    line_number,
                )
            version_match = _VERSION_PATTERN.fullmatch(text)
            if version_match is None:
                raise AssemblyParseError(
                    "invalid .s3asm version; expected MAJOR.MINOR.PATCH",
                    line_number,
                    diagnostic_category=DiagnosticCategory.VERSION,
                    diagnostic_code=(
                        DiagnosticCode.ARTIFACT_UNSUPPORTED_VERSION
                    ),
                )
            version = version_match.group(1)
            if version not in {ASSEMBLY_FORMAT_VERSION, ASSEMBLY_LEGACY_FORMAT_VERSION}:
                current_major = ASSEMBLY_FORMAT_VERSION.split(".", 1)[0]
                supplied_major = version.split(".", 1)[0]
                if supplied_major != current_major:
                    message = (
                        f"incompatible S3 Assembly major version {version}; "
                        f"supported version is {ASSEMBLY_FORMAT_VERSION}"
                    )
                else:
                    message = (
                        f"unknown S3 Assembly version {version}; supported "
                        f"version is {ASSEMBLY_FORMAT_VERSION}"
                    )
                raise AssemblyParseError(
                    message,
                    line_number,
                    diagnostic_category=DiagnosticCategory.VERSION,
                    diagnostic_code=(
                        DiagnosticCode.ARTIFACT_UNSUPPORTED_VERSION
                    ),
                )
            artifact_started = True
            continue
        artifact_started = True
        if text == ".data":
            if current_name is not None or functions:
                raise AssemblyParseError(
                    ".data section must precede all functions",
                    line_number,
                )
            if data_started:
                raise AssemblyParseError("duplicate .data section", line_number)
            data_started = True
            in_data_section = True
            continue
        if current_name is None:
            if in_data_section and not text.startswith(".function"):
                entry = _parse_static_string(text, line_number)
                if entry.id in static_string_ids:
                    raise AssemblyParseError(
                        f"duplicate static string '{entry.id}'",
                        line_number,
                    )
                static_string_ids.add(entry.id)
                static_strings.append(entry)
                continue
            in_data_section = False
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
            current_result_types = _parse_type_group(type_text, line_number)
            if (
                version == ASSEMBLY_LEGACY_FORMAT_VERSION
                and (
                    len(current_result_types) != 1
                    or type_text.strip().startswith("[")
                )
            ):
                raise AssemblyParseError(
                    "0.5.0 functions cannot use multi-result type lists",
                    line_number,
                )
            current_return_type = current_result_types[0]
            parameters = []
            registers = {}
            memory_objects = {}
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
                    tuple(
                        memory_objects[index]
                        for index in sorted(memory_objects)
                    ),
                    current_result_types,
                )
            )
            current_name = None
            current_return_type = None
            current_result_types = ()
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

        memory_declaration = _MEMORY_DECLARATION_PATTERN.fullmatch(text)
        if memory_declaration is not None:
            if code_started:
                raise AssemblyParseError(
                    "memory declarations must precede labels and instructions",
                    line_number,
                )
            memory_text, type_text, length_text, mutability = (
                memory_declaration.groups()
            )
            memory = _parse_memory(memory_text, line_number)
            if memory in memory_objects:
                raise AssemblyParseError(
                    f"duplicate memory object m{memory}",
                    line_number,
                )
            memory_objects[memory] = AssemblyMemoryObject(
                memory,
                AssemblyType(type_text),
                int(length_text),
                mutability != "immutable",
            )
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
            _parse_instruction(
                text,
                line_number,
                source_location,
                version=version,
            )
        )

    if current_name is not None:
        raise AssemblyParseError(
            f"function '{current_name}' is missing '.end'",
            len(source.splitlines()) + 1,
        )
    if not functions:
        raise AssemblyParseError("assembly contains no functions", 1)
    return AssemblyProgram(
        tuple(functions),
        ASSEMBLY_FORMAT_VERSION,
        tuple(static_strings),
    )
