"""Compiler selection at the canonical IR boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .assembly import AssemblyProgram
from .codegen import generate_assembly
from .compiler_ng_ir_bridge import NGIRDecodeError, decode_ng_ir_events
from .diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    DiagnosticSource,
    LexError,
    ParseError,
    SemanticError,
    SourceLocation,
)
from .ir import (
    DYNAMIC_BUILTIN_SIGNATURES,
    IRModule,
    IROpcode,
    IRType,
    composite_vector_runtime_signature,
)
from .lexer import SyntaxMode
from .native_compiler import (
    NativeDiagnosticCategory,
    NativeDiagnosticCode,
    NativeDiagnosticPhase,
    NativeDiagnosticRecord,
    NativeS3CTransportError,
    NativeSourceSetResult,
    require_s3c_ng_executable,
    run_native_source_set,
)
from .optimizer import OptimizationLevel, optimize_dynamic_ir, optimize_ir
from .pipeline import CompilationResult, compile_source, compile_sources
from .verifier import verify_ir


class CompilerKind(StrEnum):
    PYTHON = "python"
    S3C_NG = "s3c-ng"


DEFAULT_COMPILER = CompilerKind.PYTHON


@dataclass(frozen=True, slots=True)
class NativeCompilationResult:
    ir: IRModule
    assembly: AssemblyProgram
    native_result: NativeSourceSetResult
    compiler: CompilerKind = CompilerKind.S3C_NG

    def require_ordinary_artifacts(self) -> tuple[IRModule, AssemblyProgram]:
        return self.ir, self.assembly

    @property
    def assembly_text(self) -> str:
        return self.assembly.render()


CompilationOutput = CompilationResult | NativeCompilationResult


def compilation_requires_ir_execution(compilation: CompilationOutput) -> bool:
    """Select the hosted executor from the compiled value model, not its frontend."""

    if isinstance(compilation, NativeCompilationResult):
        return _requires_conservative_optimization(compilation.ir)
    return bool(
        compilation.semantic_model.contains_references
        or compilation.semantic_model.contains_dynamic
    )


def compile_with_provider(
    source: str,
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    compiler: CompilerKind | str = DEFAULT_COMPILER,
    mode: SyntaxMode = SyntaxMode.V0_6,
    executable: Path | None = None,
    logical_path: str = "main.s3",
    entry_module: str = "main",
) -> CompilationOutput:
    selected = CompilerKind(compiler)
    if selected is CompilerKind.PYTHON:
        return compile_source(source, optimization, mode=mode)
    return compile_source_set_with_provider(
        {logical_path: source},
        optimization,
        compiler=selected,
        mode=mode,
        executable=executable,
        entry_module=entry_module,
    )


def compile_source_set_with_provider(
    sources: Mapping[str, str],
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    compiler: CompilerKind | str = DEFAULT_COMPILER,
    mode: SyntaxMode = SyntaxMode.V0_6,
    executable: Path | None = None,
    entry_module: str = "main",
) -> CompilationOutput:
    selected = CompilerKind(compiler)
    if selected is CompilerKind.PYTHON:
        return compile_sources(
            sources,
            optimization,
            entry_module=entry_module,
            mode=mode,
        )
    if mode is not SyntaxMode.V0_6:
        raise NativeS3CTransportError(
            "S3C-NG currently accepts source syntax 0.6 only"
        )

    artifact = require_s3c_ng_executable(executable)
    result = run_native_source_set(
        artifact,
        sources,
        entry_module=entry_module,
    )
    if result.status != 0:
        if result.diagnostics:
            if len(result.diagnostics) != 1:
                raise NativeS3CTransportError(
                    "S3C-NG returned multiple diagnostics before multi-diagnostic formatting is qualified"
                )
            record = result.diagnostics[0]
            if (
                record.category_id == NativeDiagnosticCategory.SEMANTIC
                and record.phase_id == NativeDiagnosticPhase.SEMANTIC
            ):
                raise _native_semantic_error(record, sources)
            raise _native_frontend_error(record, sources)
        raise NativeS3CTransportError(
            f"S3C-NG rejected the source set (status={result.status})"
        )
    try:
        ir = decode_ng_ir_events(result.source, result.events)
    except NGIRDecodeError as error:
        raise NativeS3CTransportError(
            f"S3C-NG emitted invalid canonical IR: {error}"
        ) from error
    verify_ir(ir)

    level = OptimizationLevel.parse(optimization)
    optimizer = optimize_dynamic_ir if _requires_conservative_optimization(ir) else optimize_ir
    ir = optimizer(ir, level)
    return NativeCompilationResult(ir, generate_assembly(ir), result)


_NATIVE_DIAGNOSTICS: dict[int, tuple[DiagnosticCode, str]] = {
    NativeDiagnosticCode.MODULE_NOT_FOUND: (
        DiagnosticCode.MODULE_NOT_FOUND,
        "imported module was not found",
    ),
    NativeDiagnosticCode.MODULE_CYCLE: (
        DiagnosticCode.MODULE_CYCLE,
        "module dependency cycle prevents compilation",
    ),
    NativeDiagnosticCode.IMPORT_UNKNOWN_SYMBOL: (
        DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
        "imported symbol is not exported",
    ),
    NativeDiagnosticCode.IMPORT_PRIVATE_SYMBOL: (
        DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
        "imported symbol is private",
    ),
}


def _native_semantic_error(
    record: NativeDiagnosticRecord,
    sources: Mapping[str, str],
) -> SemanticError:
    code_and_message = _NATIVE_DIAGNOSTICS.get(record.code_id)
    if code_and_message is None or record.message_id != record.code_id:
        raise NativeS3CTransportError("S3C-NG diagnostic code or message identifier is unknown")

    no_location = (
        record.code_id == NativeDiagnosticCode.MODULE_CYCLE
        and record.source_unit_index == -1
        and record.start_byte == -1
        and record.end_byte == -1
    )
    path: str | None = None
    location: SourceLocation | None = None
    source: DiagnosticSource | None = None
    if not no_location:
        paths = sorted(sources)
        if record.source_unit_index < 0 or record.source_unit_index >= len(paths):
            raise NativeS3CTransportError("S3C-NG diagnostic references an unknown source unit")
        path = paths[record.source_unit_index]
        source_bytes = sources[path].encode("utf-8")
        if record.start_byte < 0 or record.end_byte > len(source_bytes):
            raise NativeS3CTransportError("S3C-NG diagnostic span exceeds its source unit")
        try:
            source_text = source_bytes.decode("utf-8")
            prefix = source_bytes[: record.start_byte].decode("utf-8")
            through_end = source_bytes[: record.end_byte].decode("utf-8")
        except UnicodeError as error:
            raise NativeS3CTransportError(
                "S3C-NG diagnostic span is not on UTF-8 boundaries"
            ) from error

    def line_column(prefix_text: str) -> tuple[int, int]:
        line = prefix_text.count("\n") + 1
        column = len(prefix_text.rsplit("\n", 1)[-1]) + 1
        return line, column

    context: dict[str, object] = {}
    if not no_location:
        start_offset = len(prefix)
        end_offset = len(through_end)
        line, column = line_column(prefix)
        end_line, end_column = line_column(through_end)
        if end_offset > len(source_text):
            raise NativeS3CTransportError("S3C-NG diagnostic span exceeds decoded source")
        location = SourceLocation(start_offset, line, column)
        source = DiagnosticSource(
            offset=start_offset,
            line=line,
            column=column,
            end_offset=end_offset,
            end_line=end_line,
            end_column=end_column,
        )
        context = {"file": path, "source": source}
    code, message = code_and_message
    return SemanticError(
        message,
        location,
        diagnostic_category=DiagnosticCategory.SEMANTIC,
        diagnostic_code=code,
        diagnostic_phase=DiagnosticPhase.SEMANTIC,
        diagnostic_context=context,
    )


def _native_frontend_error(
    record: NativeDiagnosticRecord,
    sources: Mapping[str, str],
) -> LexError | ParseError:
    identities = {
        NativeDiagnosticCode.LEX_INVALID_CHARACTER: (
            NativeDiagnosticCategory.SYNTAX,
            NativeDiagnosticPhase.LEXING,
            LexError,
            DiagnosticCode.LEX_INVALID_CHARACTER,
            "invalid character",
        ),
        NativeDiagnosticCode.LEX_UNTERMINATED_STRING_LITERAL: (
            NativeDiagnosticCategory.SYNTAX,
            NativeDiagnosticPhase.LEXING,
            LexError,
            DiagnosticCode.LEX_UNTERMINATED_STRING_LITERAL,
            "unterminated string literal",
        ),
        NativeDiagnosticCode.PARSE_SYNTAX: (
            NativeDiagnosticCategory.SYNTAX,
            NativeDiagnosticPhase.PARSING,
            ParseError,
            DiagnosticCode.PARSE_SYNTAX,
            "syntax error",
        ),
    }
    identity = identities.get(record.code_id)
    if (
        identity is None
        or record.category_id != identity[0]
        or record.phase_id != identity[1]
        or record.message_id != record.code_id
    ):
        raise NativeS3CTransportError(
            "S3C-NG frontend diagnostic category, phase, code, or message is unknown"
        )
    source_index = record.source_unit_index
    paths = sorted(sources)
    if source_index < 0 or source_index >= len(paths):
        raise NativeS3CTransportError(
            "S3C-NG frontend diagnostic references an unknown source unit"
        )
    path = paths[source_index]
    source_bytes = sources[path].encode("utf-8")
    if (
        record.start_byte < 0
        or record.end_byte < record.start_byte
        or record.end_byte > len(source_bytes)
    ):
        raise NativeS3CTransportError(
            "S3C-NG frontend diagnostic span exceeds its source unit"
        )
    try:
        prefix = source_bytes[: record.start_byte].decode("utf-8")
        source_bytes[: record.end_byte].decode("utf-8")
    except UnicodeError as error:
        raise NativeS3CTransportError(
            "S3C-NG frontend diagnostic span is not on UTF-8 boundaries"
        ) from error
    location = SourceLocation(
        len(prefix),
        prefix.count("\n") + 1,
        len(prefix.rsplit("\n", 1)[-1]) + 1,
    )
    error_type = identity[2]
    return error_type(
        identity[4],
        location,
        diagnostic_code=identity[3],
        diagnostic_context={"file": path},
    )


def _requires_conservative_optimization(module: IRModule) -> bool:
    dynamic_types = {IRType.BYTES, IRType.TEXT, IRType.VECTOR, IRType.REFERENCE}
    reference_opcodes = {
        IROpcode.ADDRESS_OF,
        IROpcode.AGGREGATE_ADDRESS_OF,
        IROpcode.AGGREGATE_FIELD_ADDRESS,
        IROpcode.REFERENCE_LOAD,
        IROpcode.REFERENCE_STORE,
        IROpcode.SLICE_LENGTH,
        IROpcode.SLICE_LOAD,
        IROpcode.SLICE_STORE,
    }
    for function in module.functions:
        if any(register.type in dynamic_types for register in function.registers):
            return True
        if any(parameter.type in dynamic_types for parameter in function.parameters):
            return True
        if any(memory.element_type in dynamic_types for memory in function.memory_objects):
            return True
        for instruction in function.instructions:
            if instruction.opcode in reference_opcodes:
                return True
            callee = instruction.callee or ""
            if callee in DYNAMIC_BUILTIN_SIGNATURES:
                return True
            if composite_vector_runtime_signature(callee) is not None:
                return True
    return False
