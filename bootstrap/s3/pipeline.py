"""End-to-end orchestration for the S3 bootstrap toolchain."""

from __future__ import annotations

from dataclasses import dataclass

from . import ast
from .assembly import AssemblyProgram
from .backends._hosted_execution import _execute_hosted_assembly
from .codegen import generate_assembly
from .compilation_context import CompilationContext
from .emulator import DEFAULT_MAX_FRAMES, DEFAULT_MAX_INSTRUCTIONS
from .ir import IRProgram
from .lexer import SyntaxMode, Token, tokenize
from .lowering import lower
from .module_compilation import SourceCollection, prepare_module_compilation
from .optimizer import OptimizationLevel, optimize_ir
from .parser import parse_tokens
from .semantic import SemanticModel, analyze


@dataclass(frozen=True, slots=True)
class CompilationResult:
    tokens: tuple[Token, ...]
    ast: ast.Program
    semantic_model: SemanticModel
    ir: IRProgram
    assembly: AssemblyProgram

    @property
    def assembly_text(self) -> str:
        return self.assembly.render()


def compile_source(
    source: str,
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> CompilationResult:
    context = CompilationContext(optimization=optimization, mode=mode)
    return _compile_source_with_context(source, context)


def compile_sources(
    sources: SourceCollection,
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    entry_module: str = "main",
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> CompilationResult:
    context = CompilationContext(optimization=optimization, mode=mode)
    plan = prepare_module_compilation(
        sources,
        entry_module=entry_module,
        mode=context.mode,
    )
    semantic_model = analyze(plan.program)
    ir_program = optimize_ir(
        lower(plan.program, semantic_model),
        context.optimization,
    )
    assembly_program = generate_assembly(ir_program)
    return CompilationResult(
        plan.tokens,
        plan.program,
        semantic_model,
        ir_program,
        assembly_program,
    )


def _compile_source_with_context(
    source: str,
    context: CompilationContext,
) -> CompilationResult:
    tokens = tokenize(source, mode=context.mode)
    syntax_tree = parse_tokens(tokens, mode=context.mode)
    semantic_model = analyze(syntax_tree)
    ir_program = optimize_ir(
        lower(syntax_tree, semantic_model),
        context.optimization,
    )
    assembly_program = generate_assembly(ir_program)
    return CompilationResult(
        tokens,
        syntax_tree,
        semantic_model,
        ir_program,
        assembly_program,
    )


def run_source_with_buffer_capture(
    source: str,
    entry: str = "main",
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> tuple[int, list[dict[int, list[int | None]]]]:
    compilation = compile_source(source, optimization, mode=mode)
    from .backends.registry import create_builtin_backend_registry
    registry = create_builtin_backend_registry()
    provider = registry.get_hosted_execution("hosted-emulator")
    capture: list[dict[int, list[int | None]]] = []
    result = provider.execute(
        compilation.assembly,
        entry,
        max_frames=max_frames,
        max_instructions=max_instructions,
        max_memory_trits=3**8,
        capture_memory=capture
    )
    return result, capture


def run_source(
    source: str,
    entry: str = "main",
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> int:
    compilation = compile_source(source, optimization, mode=mode)
    return _execute_hosted_assembly(
        compilation.assembly,
        entry,
        max_frames=max_frames,
        max_instructions=max_instructions,
    )
