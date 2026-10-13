"""Compiler selection at the canonical IR boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .assembly import AssemblyProgram
from .codegen import generate_assembly
from .compiler_ng_ir_bridge import NGIRDecodeError, decode_ng_ir_events
from .ir import (
    DYNAMIC_BUILTIN_SIGNATURES,
    IRModule,
    IROpcode,
    IRType,
    composite_vector_runtime_signature,
)
from .lexer import SyntaxMode
from .native_compiler import (
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
