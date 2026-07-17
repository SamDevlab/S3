"""Minimal Assembly text renderer core for incremental fixture paths."""

from __future__ import annotations

from dataclasses import dataclass

from bootstrap.s3.static_text import (
    StaticTextDocument,
    StaticTextLineEmitter,
    normalize_static_text_newlines,
)


DEFAULT_ASSEMBLY_TEXT_VERSION = "0.5.0"
AssemblyTextOperand = int | str


@dataclass(frozen=True, slots=True)
class AssemblyTextSource:
    line: int
    column: int
    offset: int

    def __post_init__(self) -> None:
        _require_positive_int(self.line, "source line")
        _require_positive_int(self.column, "source column")
        _require_non_negative_int(self.offset, "source offset")

    def render(self) -> str:
        return f"source={self.line}:{self.column}:{self.offset}"


class AssemblyTextRenderer:
    """Small structured layer over ``StaticTextLineEmitter``.

    This is an incremental Python-side bridge for fixture output paths. It does
    not render arbitrary ``AssemblyProgram`` values and is not the real S3
    renderer implementation.
    """

    def __init__(self) -> None:
        self._emitter = StaticTextLineEmitter()

    def emit_line(self, text: str = "") -> AssemblyTextRenderer:
        self._emitter.emit_line(text)
        return self

    def emit_blank_line(self) -> AssemblyTextRenderer:
        self._emitter.emit_blank_line()
        return self

    def emit_header(
        self,
        version: str = DEFAULT_ASSEMBLY_TEXT_VERSION,
    ) -> AssemblyTextRenderer:
        self._emitter.emit_line(f".s3asm {_line_fragment(version, 'version')}")
        self._emitter.emit_blank_line()
        return self

    def emit_function(
        self,
        name: str,
        return_type: str,
    ) -> AssemblyTextRenderer:
        self._emitter.emit_line(
            f".function {_line_fragment(name, 'function name')} -> "
            f"{_line_fragment(return_type, 'return type')}"
        )
        return self

    def emit_param(
        self,
        register: int,
        type_name: str,
    ) -> AssemblyTextRenderer:
        self._emitter.emit_line(
            f".param r{_register_number(register)}, "
            f"{_line_fragment(type_name, 'parameter type')}",
            indent=1,
        )
        return self

    def emit_register(
        self,
        register: int,
        type_name: str,
    ) -> AssemblyTextRenderer:
        self._emitter.emit_line(
            f".register r{_register_number(register)}, "
            f"{_line_fragment(type_name, 'register type')}",
            indent=1,
        )
        return self

    def emit_label(self, name: str) -> AssemblyTextRenderer:
        self._emitter.emit_line(f".label {_line_fragment(name, 'label')}")
        return self

    def emit_instruction(
        self,
        opcode: str,
        *operands: AssemblyTextOperand,
        source: AssemblyTextSource | None = None,
    ) -> AssemblyTextRenderer:
        opcode_text = _line_fragment(opcode, "opcode")
        operand_text = ", ".join(
            _line_fragment(str(operand), "instruction operand")
            for operand in operands
        )
        if operand_text:
            text = f"{opcode_text:<6} {operand_text}"
        else:
            text = opcode_text
        if source is not None:
            text = f"{text} ; {source.render()}"
        self._emitter.emit_line(text, indent=1)
        return self

    def emit_end(self) -> AssemblyTextRenderer:
        self._emitter.emit_line(".end")
        return self

    def build(self) -> StaticTextDocument:
        return self._emitter.build()


def _line_fragment(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    normalized = normalize_static_text_newlines(value)
    if "\n" in normalized:
        raise ValueError(f"{label} must not contain newlines")
    return normalized


def _register_number(value: int) -> int:
    _require_non_negative_int(value, "register")
    return value


def _require_positive_int(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if value < 1:
        raise ValueError(f"{label} must be positive")


def _require_non_negative_int(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
