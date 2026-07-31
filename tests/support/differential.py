from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bootstrap.s3.assembly import AssemblyError
from bootstrap.s3.codegen import CodegenError
from bootstrap.s3.diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    S3Error,
    diagnostic_from_exception,
)
from bootstrap.s3.emulator import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_MAX_INSTRUCTIONS,
    AssemblyValue,
    Emulator,
)
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ternary import TernaryRangeError


MemorySnapshot = tuple[tuple[int, tuple[AssemblyValue | None, ...]], ...]


class DifferentialEngine(Enum):
    HOSTED_EMULATOR = "hosted-emulator"


@dataclass(frozen=True, slots=True)
class DifferentialExpectation:
    return_value: AssemblyValue | None = None
    error_category: DiagnosticCategory | str | None = None
    error_code: DiagnosticCode | str | None = None
    memory: MemorySnapshot | None = None


@dataclass(frozen=True, slots=True)
class DifferentialCase:
    name: str
    source: str
    expectation: DifferentialExpectation
    mode: SyntaxMode = SyntaxMode.V0_6
    entry: str = "main"
    max_frames: int = DEFAULT_MAX_FRAMES
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS
    observable_memory: tuple[int, ...] = ()
    tags: tuple[str, ...] = ()
    exercised_passes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ObservedResult:
    engine: DifferentialEngine
    optimization: OptimizationLevel
    return_value: AssemblyValue | None = None
    error_category: str | None = None
    error_code: str | None = None
    error_phase: str | None = None
    memory: MemorySnapshot = ()

    @property
    def succeeded(self) -> bool:
        return self.error_category is None


def run_hosted_matrix(
    case: DifferentialCase,
    *,
    optimizations: tuple[
        OptimizationLevel | str,
        ...,
    ] = (OptimizationLevel.O0, OptimizationLevel.O1),
) -> tuple[ObservedResult, ...]:
    return tuple(
        _run_hosted(case, OptimizationLevel.parse(optimization))
        for optimization in optimizations
    )


def assert_hosted_equivalence(
    case: DifferentialCase,
) -> tuple[ObservedResult, ...]:
    observations = run_hosted_matrix(case)
    for observation in observations:
        _assert_matches_expectation(case, observation)
    _assert_pairwise_equivalent(case, observations)
    return observations


def _run_hosted(
    case: DifferentialCase,
    optimization: OptimizationLevel,
) -> ObservedResult:
    memory_capture: list[dict[int, list[AssemblyValue | None]]] = []
    try:
        compilation = compile_source(
            case.source,
            optimization,
            mode=case.mode,
        )
        return_value = Emulator(
            max_frames=case.max_frames,
            max_instructions=case.max_instructions,
        ).execute(
            compilation.assembly,
            case.entry,
            capture_memory=memory_capture,
        )
    except (
        AssemblyError,
        CodegenError,
        S3Error,
        TernaryRangeError,
    ) as error:
        diagnostic = diagnostic_from_exception(error)
        return ObservedResult(
            DifferentialEngine.HOSTED_EMULATOR,
            optimization,
            error_category=diagnostic.category.value,
            error_code=diagnostic.code.value,
            error_phase=diagnostic.phase.value,
        )
    return ObservedResult(
        DifferentialEngine.HOSTED_EMULATOR,
        optimization,
        return_value=return_value,
        memory=_normalize_memory(memory_capture, case.observable_memory),
    )


def _normalize_memory(
    memory_capture: list[dict[int, list[AssemblyValue | None]]],
    observable_memory: tuple[int, ...],
) -> MemorySnapshot:
    if not memory_capture or not observable_memory:
        return ()
    final_frame = memory_capture[-1]
    return tuple(
        (index, tuple(final_frame[index]))
        for index in observable_memory
        if index in final_frame
    )


def _assert_matches_expectation(
    case: DifferentialCase,
    observation: ObservedResult,
) -> None:
    expected = case.expectation
    expected_category = _enum_value(expected.error_category)
    expected_code = _enum_value(expected.error_code)
    if expected_category is not None:
        assert observation.error_category == expected_category, _summary(
            case,
            observation,
        )
        if expected_code is not None:
            assert observation.error_code == expected_code, _summary(
                case,
                observation,
            )
        return

    assert observation.succeeded, _summary(case, observation)
    assert observation.return_value == expected.return_value, _summary(
        case,
        observation,
    )
    if expected.memory is not None:
        assert observation.memory == expected.memory, _summary(
            case,
            observation,
        )


def _assert_pairwise_equivalent(
    case: DifferentialCase,
    observations: tuple[ObservedResult, ...],
) -> None:
    first = observations[0]
    for observation in observations[1:]:
        assert observation.engine is first.engine, _summary(case, observation)
        assert observation.succeeded == first.succeeded, _summary(
            case,
            observation,
        )
        if first.succeeded:
            assert observation.return_value == first.return_value, _summary(
                case,
                observation,
            )
            assert observation.memory == first.memory, _summary(
                case,
                observation,
            )
        else:
            assert observation.error_category == first.error_category, _summary(
                case,
                observation,
            )
            assert observation.error_code == first.error_code, _summary(
                case,
                observation,
            )


def _enum_value(
    value: DiagnosticCategory | DiagnosticCode | DiagnosticPhase | str | None,
) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return value


def _summary(case: DifferentialCase, observation: ObservedResult) -> str:
    return (
        f"{case.name} {observation.engine.value} "
        f"{observation.optimization.value}: "
        f"return={observation.return_value!r} "
        f"error_category={observation.error_category!r} "
        f"error_code={observation.error_code!r} "
        f"memory={observation.memory!r} "
        f"passes={case.exercised_passes!r}"
    )
