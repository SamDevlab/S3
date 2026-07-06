"""Internal native-artifact lifecycle primitives for S3 benchmarks."""

from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from bootstrap.s3.optimizer import OptimizationLevel

if __package__:
    from .benchmark_statistics import TimingStatistics, summarize_samples
else:
    from benchmark_statistics import TimingStatistics, summarize_samples


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]
Clock = Callable[[], int]


class NativeBenchmarkError(RuntimeError):
    """Base error for the internal native benchmark lifecycle."""


class NativeBuildError(NativeBenchmarkError):
    """Raised when the existing S3 CLI cannot produce the requested ELF."""


class NativeExecutionError(NativeBenchmarkError):
    """Raised when a native artifact cannot be started or measured."""


@dataclass(frozen=True, slots=True)
class NativeBuildRequest:
    """Inputs required to build one ELF artifact."""

    workload_id: str
    source_path: Path
    optimization: OptimizationLevel
    expected_return: int
    output_path: Path
    max_instructions: int
    max_frames: int
    source_syntax: str


@dataclass(frozen=True, slots=True)
class NativeArtifact:
    """A built ELF and its deterministic internal metadata."""

    workload_id: str
    optimization: OptimizationLevel
    expected_return: int
    executable_path: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class NativeExecutionResult:
    """Raw observations from one direct ELF execution."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_ns: int


@dataclass(frozen=True, slots=True)
class NativeSamplingPlan:
    """Validated execution counts and timeout for one sampling case."""

    warmups: int
    runs: int
    timeout: float | None

    def __post_init__(self) -> None:
        if isinstance(self.warmups, bool) or not isinstance(self.warmups, int):
            raise TypeError("warmups must be an integer")
        if self.warmups < 0:
            raise ValueError("warmups must be greater than or equal to zero")
        if isinstance(self.runs, bool) or not isinstance(self.runs, int):
            raise TypeError("runs must be an integer")
        if self.runs <= 0:
            raise ValueError("runs must be greater than zero")
        if self.timeout is None:
            return
        if isinstance(self.timeout, bool) or not isinstance(
            self.timeout, (int, float)
        ):
            raise TypeError("timeout must be numeric or None")
        if isinstance(self.timeout, float) and not math.isfinite(self.timeout):
            raise ValueError("timeout must be finite and greater than zero")
        if self.timeout <= 0:
            raise ValueError("timeout must be finite and greater than zero")


class NativeValidationFailureCode(str, Enum):
    """Stable internal categories for functional validation failures."""

    TIMEOUT = "timeout"
    MISSING_RETURN_CODE = "missing-return-code"
    NONZERO_STATUS = "nonzero-status"
    STDERR_NOT_EMPTY = "stderr-not-empty"
    STDOUT_EMPTY = "stdout-empty"
    STDOUT_MALFORMED = "stdout-malformed"
    WRONG_RETURN = "wrong-return"


@dataclass(frozen=True, slots=True)
class NativeValidationFailure:
    """One structured reason that an execution is invalid."""

    code: NativeValidationFailureCode
    message: str


@dataclass(frozen=True, slots=True)
class NativeValidationResult:
    """Functional validation independent from process execution."""

    valid: bool
    expected_return: int
    observed_return: int | None
    failures: tuple[NativeValidationFailure, ...]

    def require_valid(self) -> int:
        """Return the observed value or raise for an invalid execution."""
        if not self.valid:
            raise NativeValidationError(self)
        assert self.observed_return is not None
        return self.observed_return


class NativeValidationError(NativeBenchmarkError):
    """Raised when an invalid result is required to be valid."""

    def __init__(self, result: NativeValidationResult) -> None:
        self.result = result
        details = ", ".join(failure.code.value for failure in result.failures)
        super().__init__(f"native execution failed validation: {details}")


class NativeSamplingPhase(str, Enum):
    """Execution phases in one validated native sampling lifecycle."""

    PREFLIGHT = "preflight"
    WARMUP = "warmup"
    MEASUREMENT = "measurement"


class NativeSamplingError(NativeBenchmarkError):
    """A validation failure tied to its sampling phase and iteration."""

    phase: NativeSamplingPhase
    index: int | None
    validation: NativeValidationResult

    def __init__(
        self,
        phase: NativeSamplingPhase,
        index: int | None,
        validation: NativeValidationResult,
    ) -> None:
        if phase is NativeSamplingPhase.PREFLIGHT:
            if index is not None:
                raise ValueError("preflight sampling errors cannot have an index")
            location = phase.value
        else:
            if isinstance(index, bool) or not isinstance(index, int) or index < 1:
                raise ValueError(
                    "warmup and measurement sampling errors need a positive index"
                )
            location = f"{phase.value} {index}"

        self.phase = phase
        self.index = index
        self.validation = validation
        details = "; ".join(
            f"{failure.code.value}: {failure.message}"
            for failure in validation.failures
        )
        if not details:
            details = "validation reported no failure details"
        super().__init__(f"native sampling {location} failed validation: {details}")

    @property
    def failure_codes(self) -> tuple[NativeValidationFailureCode, ...]:
        """Return the structured validation categories in stable order."""
        return tuple(failure.code for failure in self.validation.failures)

    @property
    def failure_reasons(self) -> tuple[str, ...]:
        """Return the structured validation messages in stable order."""
        return tuple(failure.message for failure in self.validation.failures)


@dataclass(frozen=True, slots=True)
class NativeSamplingResult:
    """Validated timings collected from one reused native artifact."""

    artifact: NativeArtifact
    actual_return: int
    warmups: int
    runs: int
    samples_ns: tuple[int, ...]
    statistics: TimingStatistics

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, NativeArtifact):
            raise TypeError("artifact must be a NativeArtifact")
        if isinstance(self.actual_return, bool) or not isinstance(
            self.actual_return, int
        ):
            raise TypeError("actual_return must be an integer")
        if self.actual_return != self.artifact.expected_return:
            raise ValueError(
                "actual_return must equal the artifact's expected return"
            )
        if isinstance(self.warmups, bool) or not isinstance(self.warmups, int):
            raise TypeError("warmups must be an integer")
        if self.warmups < 0:
            raise ValueError("warmups must be greater than or equal to zero")
        if isinstance(self.runs, bool) or not isinstance(self.runs, int):
            raise TypeError("runs must be an integer")
        if self.runs <= 0:
            raise ValueError("runs must be greater than zero")
        if not isinstance(self.samples_ns, tuple):
            raise TypeError("samples_ns must be a tuple")
        if len(self.samples_ns) != self.runs:
            raise ValueError("samples_ns length must equal runs")
        for index, sample in enumerate(self.samples_ns, start=1):
            if isinstance(sample, bool) or not isinstance(sample, int):
                raise TypeError(
                    f"native timing sample {index} must be an integer"
                )
            if sample < 0:
                raise ValueError(
                    f"native timing sample {index} must be non-negative"
                )
        if not isinstance(self.statistics, TimingStatistics):
            raise TypeError("statistics must be TimingStatistics")
        if (
            isinstance(self.statistics.sample_count, bool)
            or not isinstance(self.statistics.sample_count, int)
            or self.statistics.sample_count != self.runs
        ):
            raise ValueError("statistics sample_count must equal runs")
        if self.statistics.unit != "ns":
            raise ValueError("statistics unit must be 'ns'")

    @property
    def total_execution_count(self) -> int:
        """Count preflight, warmups, and measured executions."""
        return 1 + self.warmups + self.runs


def build_native_artifact(
    request: NativeBuildRequest,
    *,
    process_runner: ProcessRunner = subprocess.run,
    python_executable: str = sys.executable,
) -> NativeArtifact:
    """Build one ELF through the existing public S3 CLI."""
    source_path = request.source_path.resolve()
    output_path = request.output_path.resolve()
    if not source_path.is_file():
        raise NativeBuildError(f"native benchmark source is not a file: {source_path}")

    optimization = request.optimization.value.removeprefix("O")
    command = [
        python_executable,
        "-m",
        "bootstrap.s3.cli",
        "build",
        os.fspath(source_path),
        "-O",
        optimization,
        "-o",
        os.fspath(output_path),
        "--max-instructions",
        str(request.max_instructions),
        "--max-frames",
        str(request.max_frames),
        "--source-syntax",
        request.source_syntax,
    ]
    try:
        completed = process_runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
    except OSError as error:
        raise NativeBuildError(
            f"could not start the S3 native build command: {error}"
        ) from error

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        suffix = f": {details}" if details else ""
        raise NativeBuildError(
            f"S3 native build exited with status {completed.returncode}{suffix}"
        )
    if not output_path.is_file():
        raise NativeBuildError(
            "S3 native build reported success without the requested ELF"
        )

    try:
        artifact_bytes = output_path.read_bytes()
    except OSError as error:
        raise NativeBuildError(
            f"could not read the built native artifact: {error}"
        ) from error

    return NativeArtifact(
        workload_id=request.workload_id,
        optimization=request.optimization,
        expected_return=request.expected_return,
        executable_path=output_path,
        size_bytes=len(artifact_bytes),
        sha256=hashlib.sha256(artifact_bytes).hexdigest(),
    )


def execute_native_artifact(
    artifact: NativeArtifact,
    *,
    timeout: float | None,
    process_runner: ProcessRunner = subprocess.run,
    clock: Clock = time.perf_counter_ns,
) -> NativeExecutionResult:
    """Execute an existing ELF directly and record one duration."""
    executable_path = artifact.executable_path.resolve()
    if not executable_path.is_file():
        raise NativeExecutionError(
            f"native benchmark artifact is not a file: {executable_path}"
        )

    started_at = clock()
    try:
        completed = process_runner(
            [os.fspath(executable_path)],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        finished_at = clock()
        return NativeExecutionResult(
            returncode=None,
            stdout=_coerce_text(error.stdout),
            stderr=_coerce_text(error.stderr),
            timed_out=True,
            duration_ns=_duration(started_at, finished_at),
        )
    except OSError as error:
        raise NativeExecutionError(
            f"could not start native benchmark artifact '{executable_path}': "
            f"{error}"
        ) from error
    finished_at = clock()

    return NativeExecutionResult(
        returncode=completed.returncode,
        stdout=_coerce_text(completed.stdout),
        stderr=_coerce_text(completed.stderr),
        timed_out=False,
        duration_ns=_duration(started_at, finished_at),
    )


_SUCCESS_STDOUT = re.compile(
    r"program returned: (0|[1-9][0-9]*|-[1-9][0-9]*)\n"
)


def validate_native_execution(
    result: NativeExecutionResult,
    expected_return: int,
) -> NativeValidationResult:
    """Validate one raw execution without filesystem or process access."""
    if result.timed_out:
        return _invalid(
            expected_return,
            None,
            NativeValidationFailure(
                NativeValidationFailureCode.TIMEOUT,
                "native execution timed out",
            ),
        )

    failures: list[NativeValidationFailure] = []
    if result.returncode is None:
        failures.append(
            NativeValidationFailure(
                NativeValidationFailureCode.MISSING_RETURN_CODE,
                "native execution did not report a process status",
            )
        )
    elif result.returncode != 0:
        failures.append(
            NativeValidationFailure(
                NativeValidationFailureCode.NONZERO_STATUS,
                f"native execution exited with status {result.returncode}",
            )
        )

    if result.stderr:
        failures.append(
            NativeValidationFailure(
                NativeValidationFailureCode.STDERR_NOT_EMPTY,
                "native execution emitted unexpected stderr",
            )
        )

    observed_return: int | None = None
    if not result.stdout:
        failures.append(
            NativeValidationFailure(
                NativeValidationFailureCode.STDOUT_EMPTY,
                "native execution emitted no stdout",
            )
        )
    else:
        match = _SUCCESS_STDOUT.fullmatch(result.stdout)
        if match is None:
            failures.append(
                NativeValidationFailure(
                    NativeValidationFailureCode.STDOUT_MALFORMED,
                    "native execution stdout does not match the success protocol",
                )
            )
        else:
            observed_return = int(match.group(1))
            if observed_return != expected_return:
                failures.append(
                    NativeValidationFailure(
                        NativeValidationFailureCode.WRONG_RETURN,
                        (
                            f"native execution returned {observed_return}, "
                            f"expected {expected_return}"
                        ),
                    )
                )

    if failures:
        return NativeValidationResult(
            valid=False,
            expected_return=expected_return,
            observed_return=observed_return,
            failures=tuple(failures),
        )
    return NativeValidationResult(
        valid=True,
        expected_return=expected_return,
        observed_return=observed_return,
        failures=(),
    )


def _invalid(
    expected_return: int,
    observed_return: int | None,
    *failures: NativeValidationFailure,
) -> NativeValidationResult:
    return NativeValidationResult(
        valid=False,
        expected_return=expected_return,
        observed_return=observed_return,
        failures=tuple(failures),
    )


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _duration(started_at: int, finished_at: int) -> int:
    duration = finished_at - started_at
    if duration < 0:
        raise NativeExecutionError("native execution clock moved backwards")
    return duration


NativeBuilder = Callable[[NativeBuildRequest], NativeArtifact]
NativeExecutor = Callable[..., NativeExecutionResult]
NativeValidator = Callable[
    [NativeExecutionResult, int], NativeValidationResult
]
StatisticsFactory = Callable[[Sequence[int]], TimingStatistics]


def collect_native_samples(
    artifact: NativeArtifact,
    plan: NativeSamplingPlan,
    *,
    executor: NativeExecutor | None = None,
    validator: NativeValidator | None = None,
    statistics_factory: StatisticsFactory | None = None,
) -> NativeSamplingResult:
    """Collect validated timings from one already-built native artifact."""
    if not isinstance(plan, NativeSamplingPlan):
        raise TypeError("plan must be a NativeSamplingPlan")
    selected_executor = execute_native_artifact if executor is None else executor
    selected_validator = validate_native_execution if validator is None else validator
    selected_statistics_factory = (
        summarize_samples if statistics_factory is None else statistics_factory
    )

    _, actual_return = _execute_and_validate_sample(
        artifact,
        plan,
        NativeSamplingPhase.PREFLIGHT,
        None,
        selected_executor,
        selected_validator,
    )

    for index in range(1, plan.warmups + 1):
        _execute_and_validate_sample(
            artifact,
            plan,
            NativeSamplingPhase.WARMUP,
            index,
            selected_executor,
            selected_validator,
        )

    samples: list[int] = []
    for index in range(1, plan.runs + 1):
        execution, _ = _execute_and_validate_sample(
            artifact,
            plan,
            NativeSamplingPhase.MEASUREMENT,
            index,
            selected_executor,
            selected_validator,
        )
        samples.append(execution.duration_ns)

    samples_ns = tuple(samples)
    statistics = selected_statistics_factory(samples_ns)
    return NativeSamplingResult(
        artifact=artifact,
        actual_return=actual_return,
        warmups=plan.warmups,
        runs=plan.runs,
        samples_ns=samples_ns,
        statistics=statistics,
    )


def run_native_sampling_case(
    request: NativeBuildRequest,
    plan: NativeSamplingPlan,
    *,
    builder: NativeBuilder | None = None,
    executor: NativeExecutor | None = None,
    validator: NativeValidator | None = None,
    statistics_factory: StatisticsFactory | None = None,
) -> NativeSamplingResult:
    """Build exactly once, then sample the same native artifact."""
    if not isinstance(plan, NativeSamplingPlan):
        raise TypeError("plan must be a NativeSamplingPlan")
    selected_builder = build_native_artifact if builder is None else builder
    artifact = selected_builder(request)
    return collect_native_samples(
        artifact,
        plan,
        executor=executor,
        validator=validator,
        statistics_factory=statistics_factory,
    )


def _execute_and_validate_sample(
    artifact: NativeArtifact,
    plan: NativeSamplingPlan,
    phase: NativeSamplingPhase,
    index: int | None,
    executor: NativeExecutor,
    validator: NativeValidator,
) -> tuple[NativeExecutionResult, int]:
    execution = executor(artifact, timeout=plan.timeout)
    try:
        validation = validator(execution, artifact.expected_return)
    except NativeValidationError as error:
        raise NativeSamplingError(phase, index, error.result) from error
    if not isinstance(validation, NativeValidationResult):
        raise TypeError("validator must return NativeValidationResult")
    if not validation.valid:
        raise NativeSamplingError(phase, index, validation)
    return execution, validation.require_valid()
