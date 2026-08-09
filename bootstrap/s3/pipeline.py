"""End-to-end orchestration for the S3 bootstrap toolchain."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256

from . import ast
from .assembly import ASSEMBLY_FORMAT_VERSION, AssemblyProgram
from .backends._hosted_execution import _execute_hosted_assembly
from .codegen import generate_assembly
from .compilation_context import CompilationContext
from .diagnostics import DiagnosticCode, SemanticError
from .emulator import DEFAULT_MAX_FRAMES, DEFAULT_MAX_INSTRUCTIONS
from .ir import IRProgram
from .ir_serialization import IR_FORMAT_VERSION
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


COMPILATION_CACHE_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class CompilationCacheInfo:
    hits: int
    misses: int
    max_entries: int
    current_entries: int


@dataclass(frozen=True, slots=True)
class _CompilationCacheKey:
    cache_version: str
    ir_version: str
    assembly_version: str
    source_sha256: str
    optimization: str
    mode: str


class CompilationCache:
    """Explicit bounded cache for immutable-by-contract compilation results."""

    def __init__(self, max_entries: int = 128) -> None:
        if isinstance(max_entries, bool) or not isinstance(max_entries, int):
            raise TypeError("max_entries must be an integer")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._entries: OrderedDict[_CompilationCacheKey, CompilationResult] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def compile(
        self,
        source: str,
        optimization: OptimizationLevel | str = OptimizationLevel.O0,
        *,
        mode: SyntaxMode = SyntaxMode.V0_6,
    ) -> CompilationResult:
        context = CompilationContext(optimization=optimization, mode=mode)
        key = _compilation_cache_key(source, context)
        cached = self._entries.pop(key, None)
        if cached is not None:
            self._entries[key] = cached
            self._hits += 1
            return cached

        self._misses += 1
        result = _compile_source_with_context(source, context)
        self._entries[key] = result
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        return result

    def clear(self) -> None:
        self._entries.clear()
        self._hits = 0
        self._misses = 0

    def info(self) -> CompilationCacheInfo:
        return CompilationCacheInfo(
            hits=self._hits,
            misses=self._misses,
            max_entries=self._max_entries,
            current_entries=len(self._entries),
        )


def _compilation_cache_key(
    source: str,
    context: CompilationContext,
) -> _CompilationCacheKey:
    optimization = OptimizationLevel.parse(context.optimization)
    if not isinstance(context.mode, SyntaxMode):
        raise TypeError("mode must be a SyntaxMode")
    return _CompilationCacheKey(
        cache_version=COMPILATION_CACHE_VERSION,
        ir_version=IR_FORMAT_VERSION,
        assembly_version=ASSEMBLY_FORMAT_VERSION,
        source_sha256=sha256(source.encode("utf-8")).hexdigest(),
        optimization=optimization.value,
        mode=context.mode.value,
    )


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
    assembly_program = AssemblyProgram(()) if semantic_model.contains_references else generate_assembly(ir_program)
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
    assembly_program = AssemblyProgram(()) if semantic_model.contains_references else generate_assembly(ir_program)
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
    if compilation.semantic_model.contains_references:
        from .ir_emulator import execute_ir
        return execute_ir(compilation.ir, entry, optimization), []
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
    if compilation.semantic_model.contains_references:
        from .ir_emulator import execute_ir
        return execute_ir(compilation.ir, entry, optimization)
    return _execute_hosted_assembly(
        compilation.assembly,
        entry,
        max_frames=max_frames,
        max_instructions=max_instructions,
    )
