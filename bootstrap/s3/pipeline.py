"""End-to-end orchestration for the S3 bootstrap toolchain."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from . import ast
from .assembly import ASSEMBLY_FORMAT_VERSION, AssemblyProgram
from .async_frontend import AsyncStateMachinePlan, AsyncSuspensionPoint
from .async_ir import AsyncIRPollKind, AsyncIRProgram, execute_async_program, lower_executable_async_ir
from .async_language import (
    AsyncAction,
    AsyncActionKind,
    AsyncExecutableProgram,
    AsyncLanguageSyntax,
    lower_async_language_program,
    parse_async_language_source,
    prepare_async_module_sources,
)
from .async_validation import validate_async_language_semantics
from .backends._hosted_execution import _execute_hosted_assembly
from .codegen import generate_assembly
from .compilation_context import CompilationContext
from .emulator import DEFAULT_MAX_FRAMES, DEFAULT_MAX_INSTRUCTIONS
from .ir import IRProgram
from .ir_serialization import IR_FORMAT_VERSION
from .lexer import SyntaxMode, Token
from .generics import specialize_generic_functions
from .lowering import lower
from .module_compilation import SourceCollection, prepare_module_compilation
from .optimizer import OptimizationLevel, optimize_ir
from .semantic import SemanticModel, analyze


@dataclass(frozen=True, slots=True)
class CompilationResult:
    tokens: tuple[Token, ...]
    ast: ast.Program
    semantic_model: SemanticModel
    ir: IRProgram
    assembly: AssemblyProgram
    async_syntax: AsyncLanguageSyntax = AsyncLanguageSyntax()
    async_state_machines: tuple[AsyncStateMachinePlan, ...] = ()
    async_ir: AsyncIRProgram | None = None

    @property
    def assembly_text(self) -> str:
        return self.assembly.render()


COMPILATION_CACHE_VERSION = "1.2.0"


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


def _compilation_cache_key(source: str, context: CompilationContext) -> _CompilationCacheKey:
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
    raw_items = sources.items() if isinstance(sources, Mapping) else sources
    materialized = tuple(raw_items)
    # Validate every original source before the module preprocessor erases
    # contextual async/Future syntax.  This keeps PR182's fail-closed rules
    # authoritative in multi-file compilation too.
    for _path, source in materialized:
        validate_async_language_semantics(parse_async_language_source(source, mode=context.mode))
    async_preparation = prepare_async_module_sources(materialized, entry_module=entry_module, mode=context.mode)
    plan = prepare_module_compilation(
        async_preparation.core_sources,
        entry_module=entry_module,
        mode=context.mode,
    )
    syntax_tree = specialize_generic_functions(plan.program)
    semantic_model = analyze(syntax_tree)
    ir_program = lower(syntax_tree, semantic_model)
    if not semantic_model.contains_dynamic:
        ir_program = optimize_ir(ir_program, context.optimization)
    assembly_program = generate_assembly(ir_program)
    executable = async_preparation.executable
    async_ir = lower_executable_async_ir(executable)
    combined_syntax = _combined_module_syntax(async_preparation.parsed_sources)
    return CompilationResult(
        plan.tokens,
        syntax_tree,
        semantic_model,
        ir_program,
        assembly_program,
        combined_syntax,
        _compat_state_plans(executable),
        async_ir,
    )


def _compile_source_with_context(source: str, context: CompilationContext) -> CompilationResult:
    parsed = parse_async_language_source(source, mode=context.mode)
    validate_async_language_semantics(parsed)
    executable = lower_async_language_program(parsed)
    async_state_machines = _compat_state_plans(executable)
    async_ir = lower_executable_async_ir(executable)
    syntax_tree = specialize_generic_functions(parsed.program)
    semantic_model = analyze(syntax_tree)
    ir_program = lower(syntax_tree, semantic_model)
    if not semantic_model.contains_dynamic:
        ir_program = optimize_ir(ir_program, context.optimization)
    assembly_program = generate_assembly(ir_program)
    return CompilationResult(
        parsed.tokens,
        syntax_tree,
        semantic_model,
        ir_program,
        assembly_program,
        parsed.syntax,
        async_state_machines,
        async_ir,
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
    async_value = _run_async_entry(compilation, entry, max_instructions=max_instructions)
    if async_value is not None:
        return async_value, []
    if compilation.semantic_model.contains_references or compilation.semantic_model.contains_dynamic:
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
        capture_memory=capture,
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
    async_value = _run_async_entry(compilation, entry, max_instructions=max_instructions)
    if async_value is not None:
        return async_value
    if compilation.semantic_model.contains_references or compilation.semantic_model.contains_dynamic:
        from .ir_emulator import execute_ir
        return execute_ir(compilation.ir, entry, optimization)
    return _execute_hosted_assembly(
        compilation.assembly,
        entry,
        max_frames=max_frames,
        max_instructions=max_instructions,
    )


def _run_async_entry(compilation: CompilationResult, entry: str, *, max_instructions: int) -> int | None:
    program = compilation.async_ir
    if program is None or program.executable(entry) is None:
        return None
    executable = program.executable(entry)
    if executable is None or not executable.async_function:
        return None
    max_polls = max(1, min(int(max_instructions), 100_000))
    result = execute_async_program(program, entry, max_polls=max_polls)
    if result.kind is not AsyncIRPollKind.READY:
        raise RuntimeError(f"async execution failed: {result.error or result.kind.value}")
    if isinstance(result.value, bool) or not isinstance(result.value, int):
        raise RuntimeError("S3 async entry must produce an integer scalar result")
    return result.value


def _compat_state_plans(executable: AsyncExecutableProgram) -> tuple[AsyncStateMachinePlan, ...]:
    result: list[AsyncStateMachinePlan] = []
    for function in executable.functions:
        if not function.async_function:
            continue
        await_actions = [action for action in function.actions if _is_await_action(action)]
        points = tuple(
            AsyncSuspensionPoint(
                index,
                action.source_offset,
                action.callee or action.source_future or "Future",
                f"suspended_{index}",
                f"running_{index + 1}",
            )
            for index, action in enumerate(await_actions)
        )
        states: list[str] = ["created", "running_0"]
        for point in points:
            states.extend((point.suspended_state, point.resume_state))
        states.extend(("completed", "failed", "cancelled"))
        result.append(AsyncStateMachinePlan(function.name, function.frame_slots, points, tuple(states)))
    return tuple(result)


def _is_await_action(action: AsyncAction) -> bool:
    return action.kind in {AsyncActionKind.AWAIT_CALL, AsyncActionKind.AWAIT_FUTURE} or (
        action.kind is AsyncActionKind.DISCARD and (action.callee is not None or action.source_future is not None)
    )


def _combined_module_syntax(parsed_sources) -> AsyncLanguageSyntax:
    functions = []
    awaits = []
    futures = []
    hashes = []
    for _path, parsed in parsed_sources:
        functions.extend(parsed.syntax.functions)
        awaits.extend(parsed.syntax.awaits)
        futures.extend(parsed.syntax.futures)
        hashes.append(parsed.syntax.source_sha256)
    digest = sha256("\n".join(hashes).encode("ascii")).hexdigest() if hashes else ""
    return AsyncLanguageSyntax(tuple(functions), tuple(awaits), tuple(futures), digest)
