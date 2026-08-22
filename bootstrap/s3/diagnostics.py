"""Typed diagnostics shared by the hosted S3 toolchain and its CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


DIAGNOSTIC_SCHEMA = "s3-diagnostic"
DIAGNOSTIC_SCHEMA_VERSION = "1.0.0"
DIAGNOSTIC_LIST_SCHEMA = "s3-diagnostic-list"


class DiagnosticSeverity(str, Enum):
    ERROR = "error"


class DiagnosticCategory(str, Enum):
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    LOWERING = "lowering"
    VERIFICATION = "verification"
    ARTIFACT = "artifact"
    VERSION = "version"
    OVERFLOW = "overflow"
    BOUNDS = "bounds"
    UNINITIALIZED = "uninitialized"
    IMMUTABLE_WRITE = "immutable-write"
    FRAME_LIMIT = "frame-limit"
    INSTRUCTION_LIMIT = "instruction-limit"
    TOOLCHAIN = "toolchain"
    UNSUPPORTED_TARGET = "unsupported-target"
    NATIVE_RUNTIME = "native-runtime"
    INTERNAL = "internal"


class DiagnosticPhase(str, Enum):
    CLI = "cli"
    IO = "io"
    LEXING = "lexing"
    PARSING = "parsing"
    SEMANTIC = "semantic"
    LOWERING = "lowering"
    VERIFICATION = "verification"
    ARTIFACT_READ = "artifact-read"
    INITIALIZATION = "initialization"
    ASSEMBLY = "assembly"
    EMULATION = "emulation"
    NATIVE_BACKEND = "native-backend"
    TOOLCHAIN = "toolchain"
    NATIVE_RUNTIME = "native-runtime"
    INTERNAL = "internal"


class DiagnosticCode(str, Enum):
    CLI_USAGE = "S3E_CLI_USAGE"
    IO = "S3E_IO"
    LEX_INVALID_CHARACTER = "S3E_LEX_INVALID_CHARACTER"
    LEX_UNTERMINATED_STRING_LITERAL = "S3E_LEX_UNTERMINATED_STRING_LITERAL"
    LEX_TAB_INDENTATION = "S3E_LEX_TAB_INDENTATION"
    LEX_MIXED_INDENTATION = "S3E_LEX_MIXED_INDENTATION"
    LEX_INVALID_DEDENT = "S3E_LEX_INVALID_DEDENT"
    PARSE_SYNTAX = "S3E_PARSE_SYNTAX"
    PARSE_UNSUPPORTED_STRING_LITERAL = "S3E_PARSE_UNSUPPORTED_STRING_LITERAL"
    PARSE_OBSOLETE_BRACE = "S3E_PARSE_OBSOLETE_BRACE"
    PARSE_OBSOLETE_SEMICOLON = "S3E_PARSE_OBSOLETE_SEMICOLON"
    PARSE_OBSOLETE_SWITCH = "S3E_PARSE_OBSOLETE_SWITCH"
    PARSE_EXPECTED_MATCH_ARM = "S3E_PARSE_EXPECTED_MATCH_ARM"
    PARSE_INVALID_MATCH_ARM = "S3E_PARSE_INVALID_MATCH_ARM"
    SEMANTIC_INVALID_PROGRAM = "S3E_SEMANTIC_INVALID_PROGRAM"
    SEMANTIC_TYPE_MISMATCH = "S3E_SEMANTIC_TYPE_MISMATCH"
    SEMANTIC_UNSUPPORTED_STRING_OPERATION = (
        "S3E_SEMANTIC_UNSUPPORTED_STRING_OPERATION"
    )
    SEMANTIC_INVALID_RETURN_TYPE = "S3E_SEMANTIC_INVALID_RETURN_TYPE"
    SEMANTIC_INVALID_ARGUMENT_TYPE = "S3E_SEMANTIC_INVALID_ARGUMENT_TYPE"
    SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE = "S3E_SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE"
    SEMANTIC_REFERENCE_TARGET_UNINITIALIZED = "S3E_SEMANTIC_REFERENCE_TARGET_UNINITIALIZED"
    SEMANTIC_REFERENCE_SHARED_WRITE = "S3E_SEMANTIC_REFERENCE_SHARED_WRITE"
    SEMANTIC_REFERENCE_ESCAPE = "S3E_SEMANTIC_REFERENCE_ESCAPE"
    SEMANTIC_REFERENCE_RETURN = "S3E_SEMANTIC_REFERENCE_RETURN"
    SEMANTIC_REFERENCE_NESTED = "S3E_SEMANTIC_REFERENCE_NESTED"
    SEMANTIC_REFERENCE_AGGREGATE = "S3E_SEMANTIC_REFERENCE_AGGREGATE"
    SEMANTIC_REFERENCE_IDENTITY = "S3E_SEMANTIC_REFERENCE_IDENTITY"
    SEMANTIC_REFERENCE_LOWERING_UNSUPPORTED = "S3E_SEMANTIC_REFERENCE_LOWERING_UNSUPPORTED"
    SEMANTIC_USE_AFTER_MOVE = "S3E_SEMANTIC_USE_AFTER_MOVE"
    SEMANTIC_BORROW_ESCAPE = "S3E_SEMANTIC_BORROW_ESCAPE"
    SEMANTIC_BORROW_CONFLICT = "S3E_SEMANTIC_BORROW_CONFLICT"
    SEMANTIC_BORROWED_OWNER = "S3E_SEMANTIC_BORROWED_OWNER"
    SEMANTIC_DYNAMIC_TYPE = "S3E_SEMANTIC_DYNAMIC_TYPE"
    SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED = (
        "S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED"
    )
    MODULE_DUPLICATE = "S3E_MODULE_DUPLICATE"
    MODULE_NOT_FOUND = "S3E_MODULE_NOT_FOUND"
    MODULE_CYCLE = "S3E_MODULE_CYCLE"
    MODULE_ENTRY_INVALID = "S3E_MODULE_ENTRY_INVALID"
    IMPORT_DUPLICATE = "S3E_IMPORT_DUPLICATE"
    IMPORT_CONFLICT = "S3E_IMPORT_CONFLICT"
    IMPORT_PRIVATE_SYMBOL = "S3E_IMPORT_PRIVATE_SYMBOL"
    IMPORT_UNKNOWN_SYMBOL = "S3E_IMPORT_UNKNOWN_SYMBOL"
    TYPE_DUPLICATE = "S3E_TYPE_DUPLICATE"
    RECORD_FIELD_DUPLICATE = "S3E_RECORD_FIELD_DUPLICATE"
    RECORD_FIELD_MISSING = "S3E_RECORD_FIELD_MISSING"
    RECORD_FIELD_UNKNOWN = "S3E_RECORD_FIELD_UNKNOWN"
    ENUM_VARIANT_DUPLICATE = "S3E_ENUM_VARIANT_DUPLICATE"
    ENUM_VARIANT_UNKNOWN = "S3E_ENUM_VARIANT_UNKNOWN"
    MATCH_NON_EXHAUSTIVE = "S3E_MATCH_NON_EXHAUSTIVE"
    MATCH_DUPLICATE_ARM = "S3E_MATCH_DUPLICATE_ARM"
    LOWERING_INVALID_PROGRAM = "S3E_LOWERING_INVALID_PROGRAM"
    VERIFY_INVALID_IR = "S3E_VERIFY_INVALID_IR"
    INITIALIZATION_INVALID_ACCESS = "S3E_INITIALIZATION_INVALID_ACCESS"
    INITIALIZATION_UNINITIALIZED = "S3E_INITIALIZATION_UNINITIALIZED"
    INITIALIZATION_IMMUTABLE_WRITE = "S3E_INITIALIZATION_IMMUTABLE_WRITE"
    ARTIFACT_INVALID_IR = "S3E_ARTIFACT_INVALID_IR"
    ARTIFACT_INVALID_JSON = "S3E_ARTIFACT_INVALID_JSON"
    ARTIFACT_UNSUPPORTED_FORMAT = "S3E_ARTIFACT_UNSUPPORTED_FORMAT"
    ARTIFACT_UNSUPPORTED_VERSION = "S3E_ARTIFACT_UNSUPPORTED_VERSION"
    ARTIFACT_INVALID_ASSEMBLY = "S3E_ARTIFACT_INVALID_ASSEMBLY"
    CODEGEN_UNSUPPORTED_IR = "S3E_CODEGEN_UNSUPPORTED_IR"
    ASSEMBLY_INVALID_PROGRAM = "S3E_ASSEMBLY_INVALID_PROGRAM"
    RUNTIME_OVERFLOW = "S3E_RUNTIME_OVERFLOW"
    RUNTIME_BOUNDS = "S3E_RUNTIME_BOUNDS"
    RUNTIME_UNINITIALIZED_REGISTER = "S3E_RUNTIME_UNINITIALIZED_REGISTER"
    RUNTIME_UNINITIALIZED_MEMORY = "S3E_RUNTIME_UNINITIALIZED_MEMORY"
    RUNTIME_IMMUTABLE_WRITE = "S3E_RUNTIME_IMMUTABLE_WRITE"
    RUNTIME_FRAME_LIMIT = "S3E_RUNTIME_FRAME_LIMIT"
    RUNTIME_INSTRUCTION_LIMIT = "S3E_RUNTIME_INSTRUCTION_LIMIT"
    RUNTIME_INVALID_STATE = "S3E_RUNTIME_INVALID_STATE"
    TERNARY_RANGE = "S3E_TERNARY_RANGE"
    NATIVE_BACKEND = "S3E_NATIVE_BACKEND"
    TOOLCHAIN_NOT_FOUND = "S3E_TOOLCHAIN_NOT_FOUND"
    TOOLCHAIN_FAILED = "S3E_TOOLCHAIN_FAILED"
    UNSUPPORTED_TARGET = "S3E_UNSUPPORTED_TARGET"
    NATIVE_PROCESS_FAILED = "S3E_NATIVE_PROCESS_FAILED"
    INTERNAL = "S3E_INTERNAL"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A zero-based code-point offset and one-based line/column."""

    offset: int
    line: int
    column: int

    def __post_init__(self) -> None:
        for name, value in (
            ("offset", self.offset),
            ("line", self.line),
            ("column", self.column),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"source {name} must be an integer")
        if self.offset < 0:
            raise ValueError("source offset must be non-negative")
        if self.line < 1 or self.column < 1:
            raise ValueError("source line and column must be positive")

    def to_dict(self) -> dict[str, int]:
        return {
            "offset": self.offset,
            "line": self.line,
            "column": self.column,
        }


@dataclass(frozen=True, slots=True)
class DiagnosticSource:
    """An optional source span; unavailable coordinates are omitted."""

    offset: int | None = None
    line: int | None = None
    column: int | None = None
    end_offset: int | None = None
    end_line: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("offset", self.offset),
            ("line", self.line),
            ("column", self.column),
            ("end_offset", self.end_offset),
            ("end_line", self.end_line),
            ("end_column", self.end_column),
        ):
            if (
                value is not None
                and (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                )
            ):
                raise TypeError(f"source {name} must be an integer")
        if all(
            value is None
            for value in (
                self.offset,
                self.line,
                self.column,
                self.end_offset,
                self.end_line,
                self.end_column,
            )
        ):
            raise ValueError("diagnostic source must contain a position")
        if self.offset is not None and self.offset < 0:
            raise ValueError("source offset must be non-negative")
        for name, value in (
            ("line", self.line),
            ("column", self.column),
            ("end_line", self.end_line),
            ("end_column", self.end_column),
        ):
            if value is not None and value < 1:
                raise ValueError(f"source {name} must be positive")
        if self.column is not None and self.line is None:
            raise ValueError("source column requires a line")
        if self.end_offset is not None:
            if self.offset is None:
                raise ValueError("end_offset requires offset")
            if self.end_offset < self.offset:
                raise ValueError("end_offset must not precede offset")
        if (self.end_line is None) != (self.end_column is None):
            raise ValueError("end_line and end_column must be provided together")
        if self.end_line is not None:
            if self.line is None:
                raise ValueError("end position requires a start line")
            assert self.end_column is not None
            if self.end_line < self.line:
                raise ValueError("end line must not precede start line")
            if (
                self.end_line == self.line
                and self.column is not None
                and self.end_column < self.column
            ):
                raise ValueError("end column must not precede start column")

    @classmethod
    def from_location(cls, location: SourceLocation) -> DiagnosticSource:
        return cls(
            offset=location.offset,
            line=location.line,
            column=location.column,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            name: value
            for name, value in (
                ("offset", self.offset),
                ("line", self.line),
                ("column", self.column),
                ("end_offset", self.end_offset),
                ("end_line", self.end_line),
                ("end_column", self.end_column),
            )
            if value is not None
        }


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: DiagnosticSeverity
    category: DiagnosticCategory
    phase: DiagnosticPhase
    code: DiagnosticCode
    message: str
    file: str | None = None
    source: DiagnosticSource | None = None
    function: str | None = None
    block: str | None = None
    opcode: str | None = None
    memory: str | None = None
    index: int | None = None
    value: int | None = None
    lower_bound: int | None = None
    upper_bound: int | None = None
    limit: int | None = None
    exit_code: int | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.severity, DiagnosticSeverity):
            raise TypeError("diagnostic severity must be a DiagnosticSeverity")
        if not isinstance(self.category, DiagnosticCategory):
            raise TypeError("diagnostic category must be a DiagnosticCategory")
        if not isinstance(self.phase, DiagnosticPhase):
            raise TypeError("diagnostic phase must be a DiagnosticPhase")
        if not isinstance(self.code, DiagnosticCode):
            raise TypeError("diagnostic code must be a DiagnosticCode")
        if not isinstance(self.message, str):
            raise TypeError("diagnostic message must be a string")
        if not self.message:
            raise ValueError("diagnostic message must not be empty")
        for name, value in (
            ("file", self.file),
            ("function", self.function),
            ("block", self.block),
            ("opcode", self.opcode),
            ("memory", self.memory),
        ):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"diagnostic {name} must be a string")
        if self.source is not None and not isinstance(
            self.source,
            DiagnosticSource,
        ):
            raise TypeError("diagnostic source must be a DiagnosticSource")
        for name, value in (
            ("index", self.index),
            ("value", self.value),
            ("lower_bound", self.lower_bound),
            ("upper_bound", self.upper_bound),
            ("limit", self.limit),
            ("exit_code", self.exit_code),
        ):
            if (
                value is not None
                and (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                )
            ):
                raise TypeError(f"diagnostic {name} must be an integer")
        if not isinstance(self.notes, tuple):
            raise TypeError("diagnostic notes must be a tuple")
        if any(not isinstance(note, str) for note in self.notes):
            raise TypeError("diagnostic notes must contain only strings")
        if any(not note for note in self.notes):
            raise ValueError("diagnostic notes must not be empty")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema": DIAGNOSTIC_SCHEMA,
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "severity": self.severity.value,
            "category": self.category.value,
            "phase": self.phase.value,
            "code": self.code.value,
            "message": self.message,
        }
        optional: tuple[tuple[str, object | None], ...] = (
            ("file", self.file),
            ("source", None if self.source is None else self.source.to_dict()),
            ("function", self.function),
            ("block", self.block),
            ("opcode", self.opcode),
            ("memory", self.memory),
            ("index", self.index),
            ("value", self.value),
            ("lower_bound", self.lower_bound),
            ("upper_bound", self.upper_bound),
            ("limit", self.limit),
            ("exit_code", self.exit_code),
            ("notes", list(self.notes) if self.notes else None),
        )
        result.update(
            (name, value)
            for name, value in optional
            if value is not None
        )
        return result

    def to_json(self) -> str:
        return (
            json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )


@dataclass(frozen=True, slots=True)
class DiagnosticCollection:
    """Stable, bounded presentation of compiler diagnostics."""

    diagnostics: tuple[Diagnostic, ...]
    max_items: int = 256

    def __post_init__(self) -> None:
        if isinstance(self.max_items, bool) or not isinstance(self.max_items, int) or self.max_items <= 0:
            raise ValueError("diagnostic max_items must be a positive integer")
        if not isinstance(self.diagnostics, tuple) or any(not isinstance(item, Diagnostic) for item in self.diagnostics):
            raise TypeError("diagnostics must be a tuple of Diagnostic values")
        if len(self.diagnostics) > self.max_items:
            raise ValueError("diagnostic collection exceeds its bounded capacity")
        ordered = tuple(sorted(self.diagnostics, key=_diagnostic_sort_key))
        if ordered != self.diagnostics:
            raise ValueError("diagnostics must be in canonical order")

    @classmethod
    def from_iterable(cls, diagnostics: object, *, max_items: int = 256) -> "DiagnosticCollection":
        if isinstance(diagnostics, (str, bytes)):
            raise TypeError("diagnostics must be an iterable of Diagnostic values")
        try:
            values = tuple(diagnostics)  # type: ignore[arg-type]
        except TypeError as error:
            raise TypeError("diagnostics must be iterable") from error
        if any(not isinstance(item, Diagnostic) for item in values):
            raise TypeError("diagnostics must contain only Diagnostic values")
        return cls(tuple(sorted(values, key=_diagnostic_sort_key)), max_items)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": DIAGNOSTIC_LIST_SCHEMA,
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"

    def to_text(self) -> str:
        lines: list[str] = []
        for item in self.diagnostics:
            location = ""
            if item.source is not None and item.source.line is not None:
                column = item.source.column or 1
                location = f":{item.source.line}:{column}"
            prefix = f"{item.file}{location}: " if item.file else ""
            lines.append(f"{prefix}{item.code.value}: {item.message}")
            lines.extend(f"  note: {note}" for note in item.notes)
        return "\n".join(lines) + ("\n" if lines else "")


def _diagnostic_sort_key(item: Diagnostic) -> tuple[object, ...]:
    source = item.source
    return (
        item.file or "",
        source.line if source is not None and source.line is not None else 0,
        source.column if source is not None and source.column is not None else 0,
        item.phase.value,
        item.code.value,
        item.message,
    )


class S3Error(Exception):
    """Base class for source diagnostics intended for command-line users."""

    category = "S3 error"
    diagnostic_category = DiagnosticCategory.INTERNAL
    diagnostic_code = DiagnosticCode.INTERNAL
    diagnostic_phase = DiagnosticPhase.INTERNAL

    def __init__(
        self,
        message: str,
        location: SourceLocation | None = None,
        *,
        diagnostic_category: DiagnosticCategory | None = None,
        diagnostic_code: DiagnosticCode | None = None,
        diagnostic_phase: DiagnosticPhase | None = None,
        diagnostic_context: Mapping[str, Any] | None = None,
    ):
        self.message = message
        self.diagnostic_message = message
        self.location = location
        if diagnostic_category is not None:
            self.diagnostic_category = diagnostic_category
        if diagnostic_code is not None:
            self.diagnostic_code = diagnostic_code
        if diagnostic_phase is not None:
            self.diagnostic_phase = diagnostic_phase
        self.diagnostic_context = dict(diagnostic_context or {})
        if location is None:
            rendered = f"{self.category}: {message}"
        else:
            rendered = (
                f"{location.line}:{location.column}: "
                f"{self.category}: {message}"
            )
        super().__init__(rendered)

    def add_diagnostic_context(self, **context: object) -> None:
        for name, value in context.items():
            if value is not None and name not in self.diagnostic_context:
                self.diagnostic_context[name] = value


class LexError(S3Error):
    category = "lexical error"
    diagnostic_category = DiagnosticCategory.SYNTAX
    diagnostic_code = DiagnosticCode.LEX_INVALID_CHARACTER
    diagnostic_phase = DiagnosticPhase.LEXING

class IndentationError(LexError):
    category = "indentation error"
    diagnostic_code = DiagnosticCode.LEX_INVALID_DEDENT


class ParseError(S3Error):
    category = "parse error"
    diagnostic_category = DiagnosticCategory.SYNTAX
    diagnostic_code = DiagnosticCode.PARSE_SYNTAX
    diagnostic_phase = DiagnosticPhase.PARSING


class SemanticError(S3Error):
    category = "semantic error"
    diagnostic_category = DiagnosticCategory.SEMANTIC
    diagnostic_code = DiagnosticCode.SEMANTIC_INVALID_PROGRAM
    diagnostic_phase = DiagnosticPhase.SEMANTIC


class LoweringError(S3Error):
    category = "lowering error"
    diagnostic_category = DiagnosticCategory.LOWERING
    diagnostic_code = DiagnosticCode.LOWERING_INVALID_PROGRAM
    diagnostic_phase = DiagnosticPhase.LOWERING


def diagnostic_from_exception(
    error: Exception,
    *,
    file: str | None = None,
) -> Diagnostic:
    """Convert an annotated public exception without parsing its message."""

    if isinstance(error, OSError):
        error_file = getattr(error, "filename", None)
        return Diagnostic(
            DiagnosticSeverity.ERROR,
            DiagnosticCategory.ARTIFACT,
            DiagnosticPhase.IO,
            DiagnosticCode.IO,
            str(error),
            file=str(error_file) if error_file is not None else file,
        )
    if isinstance(error, UnicodeError):
        return Diagnostic(
            DiagnosticSeverity.ERROR,
            DiagnosticCategory.ARTIFACT,
            DiagnosticPhase.IO,
            DiagnosticCode.IO,
            str(error),
            file=file,
        )

    category = getattr(
        error,
        "diagnostic_category",
        DiagnosticCategory.INTERNAL,
    )
    code = getattr(error, "diagnostic_code", DiagnosticCode.INTERNAL)
    phase = getattr(error, "diagnostic_phase", DiagnosticPhase.INTERNAL)
    message = getattr(
        error,
        "diagnostic_message",
        getattr(error, "message", str(error)),
    )
    context = dict(getattr(error, "diagnostic_context", {}))
    location = getattr(error, "location", None)
    source = context.pop("source", None)
    if source is None and isinstance(location, SourceLocation):
        source = DiagnosticSource.from_location(location)
    if source is not None and not isinstance(source, DiagnosticSource):
        raise TypeError("diagnostic source context must be a DiagnosticSource")
    context_file = context.pop("file", None)
    notes = context.pop("notes", ())
    if isinstance(notes, str):
        notes = (notes,)
    known = {
        name: context.pop(name, None)
        for name in (
            "function",
            "block",
            "opcode",
            "memory",
            "index",
            "value",
            "lower_bound",
            "upper_bound",
            "limit",
            "exit_code",
        )
    }
    if context:
        unknown = ", ".join(sorted(context))
        raise ValueError(f"unknown diagnostic context field(s): {unknown}")
    return Diagnostic(
        DiagnosticSeverity.ERROR,
        category,
        phase,
        code,
        message or type(error).__name__,
        file=str(context_file) if context_file is not None else file,
        source=source,
        notes=tuple(notes),
        **known,
    )
