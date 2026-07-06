from __future__ import annotations

import hashlib
import math
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from bootstrap.s3.optimizer import OptimizationLevel
from tools.benchmark_statistics import TimingStatistics, summarize_samples
from tools.benchmark_native import (
    NativeArtifact,
    NativeBuildError,
    NativeBuildRequest,
    NativeExecutionError,
    NativeExecutionResult,
    NativeSamplingError,
    NativeSamplingPhase,
    NativeSamplingPlan,
    NativeSamplingResult,
    NativeValidationError,
    NativeValidationFailureCode,
    NativeValidationResult,
    collect_native_samples,
    build_native_artifact,
    execute_native_artifact,
    run_native_sampling_case,
    validate_native_execution,
)


def _request(
    tmp_path: Path,
    optimization: OptimizationLevel = OptimizationLevel.O0,
) -> NativeBuildRequest:
    source = tmp_path / "minimal.s3"
    source.write_text("fn main() -> tryte:\n    return 0\n", encoding="utf-8")
    return NativeBuildRequest(
        workload_id="minimal",
        source_path=source,
        optimization=optimization,
        expected_return=0,
        output_path=tmp_path / "minimal",
        max_instructions=1234,
        max_frames=56,
        source_syntax="0.6",
    )


def _artifact(tmp_path: Path, expected_return: int = 0) -> NativeArtifact:
    executable = tmp_path / "program"
    content = b"\x7fELF-test-artifact"
    executable.write_bytes(content)
    return NativeArtifact(
        workload_id="minimal",
        optimization=OptimizationLevel.O0,
        expected_return=expected_return,
        executable_path=executable,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _result(
    *,
    returncode: int | None = 0,
    stdout: str = "program returned: 0\n",
    stderr: str = "",
    timed_out: bool = False,
    duration_ns: int = 1,
) -> NativeExecutionResult:
    return NativeExecutionResult(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_ns=duration_ns,
    )


def _failure_codes(result) -> set[NativeValidationFailureCode]:
    return {failure.code for failure in result.failures}


@pytest.mark.parametrize(
    ("optimization", "cli_value"),
    (
        (OptimizationLevel.O0, "0"),
        (OptimizationLevel.O1, "1"),
    ),
)
def test_builder_forms_public_cli_command_and_hashes_output(
    tmp_path: Path,
    optimization: OptimizationLevel,
    cli_value: str,
) -> None:
    request = _request(tmp_path, optimization)
    artifact_bytes = b"\x7fELF-built-once"
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        request.output_path.write_bytes(artifact_bytes)
        return subprocess.CompletedProcess(command, 0, "built\n", "")

    artifact = build_native_artifact(
        request,
        process_runner=runner,
        python_executable="python-for-test",
    )

    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command == [
        "python-for-test",
        "-m",
        "bootstrap.s3.cli",
        "build",
        str(request.source_path.resolve()),
        "-O",
        cli_value,
        "-o",
        str(request.output_path.resolve()),
        "--max-instructions",
        "1234",
        "--max-frames",
        "56",
        "--source-syntax",
        "0.6",
    ]
    assert kwargs == {
        "check": False,
        "capture_output": True,
        "text": True,
        "shell": False,
    }
    assert "run-native" not in command
    assert artifact.executable_path == request.output_path.resolve()
    assert artifact.optimization is optimization
    assert artifact.size_bytes == len(artifact_bytes)
    assert artifact.sha256 == hashlib.sha256(artifact_bytes).hexdigest()


def test_builder_rejects_nonzero_status(tmp_path: Path) -> None:
    request = _request(tmp_path)

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, "", "toolchain failed")

    with pytest.raises(
        NativeBuildError,
        match="status 2: toolchain failed",
    ):
        build_native_artifact(request, process_runner=runner)


def test_builder_wraps_process_start_failure(tmp_path: Path) -> None:
    request = _request(tmp_path)

    def runner(command, **kwargs):
        raise FileNotFoundError("python missing")

    with pytest.raises(
        NativeBuildError,
        match="could not start.*python missing",
    ):
        build_native_artifact(request, process_runner=runner)


def test_builder_rejects_success_without_output(tmp_path: Path) -> None:
    request = _request(tmp_path)

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "", "")

    with pytest.raises(NativeBuildError, match="without the requested ELF"):
        build_native_artifact(request, process_runner=runner)


def test_builder_rejects_missing_source_without_starting_process(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    request.source_path.unlink()
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        raise AssertionError("process runner must not be called")

    with pytest.raises(NativeBuildError, match="source is not a file"):
        build_native_artifact(request, process_runner=runner)
    assert calls == []


def test_native_lifecycle_records_are_immutable(tmp_path: Path) -> None:
    request = _request(tmp_path)
    artifact = _artifact(tmp_path)
    result = _result()
    validation = validate_native_execution(result, 0)

    with pytest.raises(FrozenInstanceError):
        request.workload_id = "other"
    with pytest.raises(FrozenInstanceError):
        artifact.size_bytes = 0
    with pytest.raises(FrozenInstanceError):
        result.duration_ns = 2
    with pytest.raises(FrozenInstanceError):
        validation.valid = False


def test_executor_runs_only_the_existing_artifact_and_measures_once(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path)
    process_calls = []
    clock_values = iter((100, 145))
    clock_calls = []

    def clock():
        clock_calls.append(True)
        return next(clock_values)

    def runner(command, **kwargs):
        process_calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            "program returned: 0\n",
            "",
        )

    result = execute_native_artifact(
        artifact,
        timeout=3.5,
        process_runner=runner,
        clock=clock,
    )

    assert len(process_calls) == 1
    command, kwargs = process_calls[0]
    assert command == [str(artifact.executable_path.resolve())]
    assert all("python" not in part.lower() for part in command)
    assert all(part.lower() != "s3" for part in command)
    assert kwargs == {
        "check": False,
        "capture_output": True,
        "text": True,
        "shell": False,
        "timeout": 3.5,
    }
    assert len(clock_calls) == 2
    assert result == NativeExecutionResult(
        returncode=0,
        stdout="program returned: 0\n",
        stderr="",
        timed_out=False,
        duration_ns=45,
    )


def test_executor_rejects_missing_artifact_without_starting_process(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path)
    artifact.executable_path.unlink()
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        raise AssertionError("process runner must not be called")

    with pytest.raises(NativeExecutionError, match="artifact is not a file"):
        execute_native_artifact(
            artifact,
            timeout=1.0,
            process_runner=runner,
        )
    assert calls == []


def test_executor_represents_timeout_explicitly(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    clock_values = iter((10, 35))

    def runner(command, **kwargs):
        raise subprocess.TimeoutExpired(
            command,
            kwargs["timeout"],
            output=b"partial",
            stderr=b"waiting",
        )

    result = execute_native_artifact(
        artifact,
        timeout=0.25,
        process_runner=runner,
        clock=lambda: next(clock_values),
    )

    assert result == NativeExecutionResult(
        returncode=None,
        stdout="partial",
        stderr="waiting",
        timed_out=True,
        duration_ns=25,
    )


def test_executor_wraps_process_start_failure(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)

    def runner(command, **kwargs):
        raise PermissionError("not executable")

    with pytest.raises(
        NativeExecutionError,
        match="could not start.*not executable",
    ):
        execute_native_artifact(
            artifact,
            timeout=1.0,
            process_runner=runner,
            clock=lambda: 10,
        )


def test_executor_rejects_backwards_clock(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    clock_values = iter((20, 10))

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            "program returned: 0\n",
            "",
        )

    with pytest.raises(NativeExecutionError, match="clock moved backwards"):
        execute_native_artifact(
            artifact,
            timeout=1.0,
            process_runner=runner,
            clock=lambda: next(clock_values),
        )


@pytest.mark.parametrize("expected_return", (0, 17, -23))
def test_validator_accepts_exact_success_protocol(expected_return: int) -> None:
    validation = validate_native_execution(
        _result(stdout=f"program returned: {expected_return}\n"),
        expected_return,
    )

    assert validation.valid
    assert validation.observed_return == expected_return
    assert validation.failures == ()
    assert validation.require_valid() == expected_return


def test_validator_rejects_wrong_functional_return() -> None:
    validation = validate_native_execution(
        _result(stdout="program returned: 2\n"),
        1,
    )

    assert not validation.valid
    assert validation.observed_return == 2
    assert _failure_codes(validation) == {
        NativeValidationFailureCode.WRONG_RETURN
    }


def test_validator_rejects_nonzero_process_status() -> None:
    validation = validate_native_execution(_result(returncode=7), 0)

    assert not validation.valid
    assert NativeValidationFailureCode.NONZERO_STATUS in _failure_codes(
        validation
    )


def test_validator_rejects_timeout() -> None:
    validation = validate_native_execution(
        _result(returncode=None, stdout="", timed_out=True),
        0,
    )

    assert not validation.valid
    assert _failure_codes(validation) == {
        NativeValidationFailureCode.TIMEOUT
    }


def test_validator_rejects_unexpected_stderr() -> None:
    validation = validate_native_execution(
        _result(stderr="unexpected\n"),
        0,
    )

    assert not validation.valid
    assert NativeValidationFailureCode.STDERR_NOT_EMPTY in _failure_codes(
        validation
    )


def test_validator_rejects_empty_stdout() -> None:
    validation = validate_native_execution(_result(stdout=""), 0)

    assert not validation.valid
    assert NativeValidationFailureCode.STDOUT_EMPTY in _failure_codes(
        validation
    )


def test_validator_rejects_additional_stdout_line() -> None:
    validation = validate_native_execution(
        _result(stdout="program returned: 0\nextra\n"),
        0,
    )

    assert not validation.valid
    assert NativeValidationFailureCode.STDOUT_MALFORMED in _failure_codes(
        validation
    )


@pytest.mark.parametrize(
    "stdout",
    (
        "program returned: 1",
        "program returned: +1\n",
        "program returned: 01\n",
        "program returned: 1.0\n",
        "program returned: 0x1\n",
        "program returned:\n",
        " program returned: 1\n",
        "program returned: 1 \n",
    ),
)
def test_validator_rejects_malformed_stdout(stdout: str) -> None:
    validation = validate_native_execution(_result(stdout=stdout), 1)

    assert not validation.valid
    assert NativeValidationFailureCode.STDOUT_MALFORMED in _failure_codes(
        validation
    )


def test_validator_ignores_duration_for_functional_correctness() -> None:
    short = validate_native_execution(_result(duration_ns=1), 0)
    long = validate_native_execution(_result(duration_ns=10**18), 0)

    assert short.valid
    assert long.valid


def test_validator_rejects_missing_return_code() -> None:
    validation = validate_native_execution(_result(returncode=None), 0)

    assert not validation.valid
    assert NativeValidationFailureCode.MISSING_RETURN_CODE in _failure_codes(
        validation
    )


def test_validator_reports_multiple_structured_failures() -> None:
    validation = validate_native_execution(
        _result(
            returncode=3,
            stdout="bad output\n",
            stderr="bad error\n",
        ),
        0,
    )

    assert _failure_codes(validation) == {
        NativeValidationFailureCode.NONZERO_STATUS,
        NativeValidationFailureCode.STDERR_NOT_EMPTY,
        NativeValidationFailureCode.STDOUT_MALFORMED,
    }
    with pytest.raises(NativeValidationError) as error:
        validation.require_valid()
    assert error.value.result is validation


def test_lifecycle_builds_once_and_executes_same_artifact_twice(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    build_calls = []
    execution_calls = []

    def build_runner(command, **kwargs):
        build_calls.append((command, kwargs))
        request.output_path.write_bytes(b"\x7fELF-one-build")
        return subprocess.CompletedProcess(command, 0, "", "")

    artifact = build_native_artifact(
        request,
        process_runner=build_runner,
    )

    def execution_runner(command, **kwargs):
        execution_calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            "program returned: 0\n",
            "",
        )

    clock_values = iter((0, 1, 2, 3))
    for _ in range(2):
        result = execute_native_artifact(
            artifact,
            timeout=1.0,
            process_runner=execution_runner,
            clock=lambda: next(clock_values),
        )
        assert validate_native_execution(
            result,
            artifact.expected_return,
        ).require_valid() == 0

    assert len(build_calls) == 1
    assert len(execution_calls) == 2
    assert all(
        command == [str(artifact.executable_path)]
        for command, _ in execution_calls
    )


class _RecordingBuilder:
    def __init__(self, artifact: NativeArtifact, events: list[tuple]) -> None:
        self.artifact = artifact
        self.events = events
        self.calls: list[NativeBuildRequest] = []

    def __call__(self, request: NativeBuildRequest) -> NativeArtifact:
        self.calls.append(request)
        self.events.append(("builder", request.workload_id))
        return self.artifact


class _RecordingExecutor:
    def __init__(
        self,
        labels: tuple[str, ...],
        results: list[NativeExecutionResult],
        events: list[tuple],
    ) -> None:
        self.labels = labels
        self.results = results
        self.events = events
        self.calls: list[dict[str, object]] = []

    def __call__(self, artifact: NativeArtifact, *, timeout):
        index = len(self.calls)
        result = self.results[index]
        label = self.labels[index]
        self.calls.append(
            {
                "label": label,
                "artifact": artifact,
                "timeout": timeout,
                "result": result,
            }
        )
        self.events.append(("executor", label, artifact, timeout, result.duration_ns))
        return result


class _RecordingValidator:
    def __init__(self, labels: tuple[str, ...], events: list[tuple]) -> None:
        self.labels = labels
        self.events = events
        self.calls: list[dict[str, object]] = []
        self.validations: list[NativeValidationResult] = []

    def __call__(
        self,
        execution: NativeExecutionResult,
        expected_return: int,
    ) -> NativeValidationResult:
        index = len(self.calls)
        label = self.labels[index]
        validation = validate_native_execution(execution, expected_return)
        self.calls.append(
            {
                "label": label,
                "execution": execution,
                "expected_return": expected_return,
                "validation": validation,
            }
        )
        self.validations.append(validation)
        self.events.append(("validator", label, validation))
        return validation


class _RecordingStatisticsFactory:
    def __init__(
        self,
        events: list[tuple],
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.error = error
        self.calls: list[tuple[int, ...]] = []

    def __call__(self, samples: tuple[int, ...]) -> TimingStatistics:
        samples_tuple = tuple(samples)
        self.calls.append(samples_tuple)
        self.events.append(("statistics", samples_tuple))
        if self.error is not None:
            raise self.error
        return summarize_samples(samples_tuple)


@pytest.mark.parametrize(
    ("warmups", "runs", "timeout"),
    (
        (0, 1, None),
        (1, 1, 3),
        (2, 4, 2.5),
        (3, 2, None),
        (1, 5, 7.0),
    ),
)
def test_native_sampling_plan_accepts_valid_inputs_and_is_immutable(
    warmups: int,
    runs: int,
    timeout: float | None,
) -> None:
    plan = NativeSamplingPlan(warmups=warmups, runs=runs, timeout=timeout)

    assert plan.warmups == warmups
    assert plan.runs == runs
    assert plan.timeout == timeout

    with pytest.raises(FrozenInstanceError):
        plan.warmups = 99


@pytest.mark.parametrize(
    ("warmups", "runs", "timeout", "expected_exception", "message"),
    (
        (-1, 1, None, ValueError, "warmups must be greater than or equal to zero"),
        (True, 1, None, TypeError, "warmups must be an integer"),
        (1.5, 1, None, TypeError, "warmups must be an integer"),
        (0, 0, None, ValueError, "runs must be greater than zero"),
        (0, -1, None, ValueError, "runs must be greater than zero"),
        (0, True, None, TypeError, "runs must be an integer"),
        (0, 1.5, None, TypeError, "runs must be an integer"),
        (0, 1, 0, ValueError, "timeout must be finite and greater than zero"),
        (0, 1, -1, ValueError, "timeout must be finite and greater than zero"),
        (0, 1, True, TypeError, "timeout must be numeric or None"),
        (0, 1, math.nan, ValueError, "timeout must be finite and greater than zero"),
        (0, 1, math.inf, ValueError, "timeout must be finite and greater than zero"),
        (0, 1, -math.inf, ValueError, "timeout must be finite and greater than zero"),
        (0, 1, "1", TypeError, "timeout must be numeric or None"),
    ),
)
def test_native_sampling_plan_rejects_invalid_inputs(
    warmups,
    runs,
    timeout,
    expected_exception,
    message,
) -> None:
    with pytest.raises(expected_exception, match=message):
        NativeSamplingPlan(warmups=warmups, runs=runs, timeout=timeout)


def test_native_sampling_result_preserves_values_and_is_immutable(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path, expected_return=7)
    statistics = TimingStatistics(
        sample_count=3,
        unit="ns",
        minimum=10,
        maximum=30,
        mean=20.0,
        median=20.0,
        p95=30,
    )

    result = NativeSamplingResult(
        artifact=artifact,
        actual_return=7,
        warmups=2,
        runs=3,
        samples_ns=(10, 20, 30),
        statistics=statistics,
    )

    assert result.artifact is artifact
    assert result.statistics is statistics
    assert result.actual_return == 7
    assert result.warmups == 2
    assert result.runs == 3
    assert result.samples_ns == (10, 20, 30)
    assert result.total_execution_count == 6

    with pytest.raises(FrozenInstanceError):
        result.runs = 4


@pytest.mark.parametrize(
    ("kwargs", "expected_exception", "message"),
    (
        (
            {
                "actual_return": 8,
                "warmups": 2,
                "runs": 3,
                "samples_ns": (10, 20, 30),
                "statistics": TimingStatistics(
                    sample_count=3,
                    unit="ns",
                    minimum=10,
                    maximum=30,
                    mean=20.0,
                    median=20.0,
                    p95=30,
                ),
            },
            ValueError,
            "actual_return must equal the artifact's expected return",
        ),
        (
            {
                "actual_return": 7,
                "warmups": 2,
                "runs": 3,
                "samples_ns": (10, 20),
                "statistics": TimingStatistics(
                    sample_count=3,
                    unit="ns",
                    minimum=10,
                    maximum=30,
                    mean=20.0,
                    median=20.0,
                    p95=30,
                ),
            },
            ValueError,
            "samples_ns length must equal runs",
        ),
        (
            {
                "actual_return": 7,
                "warmups": 2,
                "runs": 3,
                "samples_ns": (10, -1, 30),
                "statistics": TimingStatistics(
                    sample_count=3,
                    unit="ns",
                    minimum=10,
                    maximum=30,
                    mean=20.0,
                    median=20.0,
                    p95=30,
                ),
            },
            ValueError,
            "native timing sample 2 must be non-negative",
        ),
        (
            {
                "actual_return": 7,
                "warmups": 2,
                "runs": 3,
                "samples_ns": (10, 20, 30),
                "statistics": TimingStatistics(
                    sample_count=2,
                    unit="ns",
                    minimum=10,
                    maximum=30,
                    mean=20.0,
                    median=20.0,
                    p95=30,
                ),
            },
            ValueError,
            "statistics sample_count must equal runs",
        ),
        (
            {
                "actual_return": 7,
                "warmups": 2,
                "runs": 3,
                "samples_ns": (10, 20, 30),
                "statistics": TimingStatistics(
                    sample_count=3,
                    unit="us",
                    minimum=10,
                    maximum=30,
                    mean=20.0,
                    median=20.0,
                    p95=30,
                ),
            },
            ValueError,
            "statistics unit must be 'ns'",
        ),
    ),
)
def test_native_sampling_result_rejects_invalid_invariants(
    tmp_path: Path,
    kwargs,
    expected_exception,
    message,
) -> None:
    artifact = _artifact(tmp_path, expected_return=7)

    with pytest.raises(expected_exception, match=message):
        NativeSamplingResult(artifact=artifact, **kwargs)


def test_run_native_sampling_case_records_order_and_discards_preflight_and_warmups(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    artifact = _artifact(tmp_path)
    events: list[tuple] = []
    labels = (
        "preflight",
        "warmup 1",
        "warmup 2",
        "measurement 1",
        "measurement 2",
        "measurement 3",
        "measurement 4",
        "measurement 5",
    )
    executor = _RecordingExecutor(
        labels=labels,
        results=[
            _result(duration_ns=9999),
            _result(duration_ns=8000),
            _result(duration_ns=7000),
            _result(duration_ns=10),
            _result(duration_ns=20),
            _result(duration_ns=30),
            _result(duration_ns=40),
            _result(duration_ns=100),
        ],
        events=events,
    )
    validator = _RecordingValidator(labels=labels, events=events)
    statistics_factory = _RecordingStatisticsFactory(events=events)
    builder = _RecordingBuilder(artifact=artifact, events=events)
    plan = NativeSamplingPlan(warmups=2, runs=5, timeout=None)

    result = run_native_sampling_case(
        request,
        plan,
        builder=builder,
        executor=executor,
        validator=validator,
        statistics_factory=statistics_factory,
    )

    assert builder.calls == [request]
    assert len(executor.calls) == 8
    assert len(validator.calls) == 8
    assert len(statistics_factory.calls) == 1
    assert statistics_factory.calls[0] == (10, 20, 30, 40, 100)
    assert result.artifact is artifact
    assert all(call["artifact"] is artifact for call in executor.calls)
    assert result.samples_ns == (10, 20, 30, 40, 100)
    assert result.statistics == TimingStatistics(
        sample_count=5,
        unit="ns",
        minimum=10,
        maximum=100,
        mean=40.0,
        median=30.0,
        p95=100,
    )
    assert result.total_execution_count == 8

    assert events == [
        ("builder", "minimal"),
        ("executor", "preflight", artifact, None, 9999),
        ("validator", "preflight", validator.validations[0]),
        ("executor", "warmup 1", artifact, None, 8000),
        ("validator", "warmup 1", validator.validations[1]),
        ("executor", "warmup 2", artifact, None, 7000),
        ("validator", "warmup 2", validator.validations[2]),
        ("executor", "measurement 1", artifact, None, 10),
        ("validator", "measurement 1", validator.validations[3]),
        ("executor", "measurement 2", artifact, None, 20),
        ("validator", "measurement 2", validator.validations[4]),
        ("executor", "measurement 3", artifact, None, 30),
        ("validator", "measurement 3", validator.validations[5]),
        ("executor", "measurement 4", artifact, None, 40),
        ("validator", "measurement 4", validator.validations[6]),
        ("executor", "measurement 5", artifact, None, 100),
        ("validator", "measurement 5", validator.validations[7]),
        ("statistics", (10, 20, 30, 40, 100)),
    ]


@pytest.mark.parametrize(
    ("failure_result", "expected_codes", "message"),
    (
        (
            _result(returncode=None, stdout="program returned: 0\n", timed_out=True),
            {NativeValidationFailureCode.TIMEOUT},
            "native execution timed out",
        ),
        (
            _result(returncode=None, stdout="program returned: 0\n"),
            {NativeValidationFailureCode.MISSING_RETURN_CODE},
            "did not report a process status",
        ),
        (
            _result(returncode=7, stdout="program returned: 0\n"),
            {NativeValidationFailureCode.NONZERO_STATUS},
            "exited with status 7",
        ),
        (
            _result(returncode=0, stdout="program returned: 0\n", stderr="oops\n"),
            {NativeValidationFailureCode.STDERR_NOT_EMPTY},
            "unexpected stderr",
        ),
        (
            _result(returncode=0, stdout=""),
            {NativeValidationFailureCode.STDOUT_EMPTY},
            "emitted no stdout",
        ),
        (
            _result(returncode=0, stdout="program returned: 0"),
            {NativeValidationFailureCode.STDOUT_MALFORMED},
            "does not match the success protocol",
        ),
        (
            _result(returncode=0, stdout="program returned: 7\n"),
            {NativeValidationFailureCode.WRONG_RETURN},
            "returned 7, expected 0",
        ),
    ),
)
def test_collect_native_samples_rejects_preflight_failures(
    tmp_path: Path,
    failure_result: NativeExecutionResult,
    expected_codes: set[NativeValidationFailureCode],
    message: str,
) -> None:
    artifact = _artifact(tmp_path)
    events: list[tuple] = []
    labels = ("preflight",)
    executor = _RecordingExecutor(labels=labels, results=[failure_result], events=events)
    validator = _RecordingValidator(labels=labels, events=events)
    statistics_factory = _RecordingStatisticsFactory(events=events)
    plan = NativeSamplingPlan(warmups=2, runs=3, timeout=None)

    with pytest.raises(NativeSamplingError) as error:
        collect_native_samples(
            artifact,
            plan,
            executor=executor,
            validator=validator,
            statistics_factory=statistics_factory,
        )

    assert error.value.phase is NativeSamplingPhase.PREFLIGHT
    assert error.value.index is None
    assert error.value.validation is validator.validations[0]
    assert error.value.failure_codes == tuple(expected_codes)
    assert message in str(error.value)
    assert len(executor.calls) == 1
    assert len(validator.calls) == 1
    assert statistics_factory.calls == []


@pytest.mark.parametrize(
    ("failure_position",),
    ((1,), (2,), (3,)),
)
def test_collect_native_samples_stops_on_warmup_failure(
    tmp_path: Path,
    failure_position: int,
) -> None:
    artifact = _artifact(tmp_path)
    events: list[tuple] = []
    labels = (
        "preflight",
        "warmup 1",
        "warmup 2",
        "warmup 3",
        "measurement 1",
        "measurement 2",
    )
    results = [_result()]
    for index in range(1, failure_position):
        results.append(_result(duration_ns=1000 + index))
    failing_result = _result(returncode=0, stdout="program returned: 7\n")
    results.append(failing_result)
    executor = _RecordingExecutor(labels=labels[: len(results)], results=results, events=events)
    validator = _RecordingValidator(labels=labels[: len(results)], events=events)
    statistics_factory = _RecordingStatisticsFactory(events=events)
    plan = NativeSamplingPlan(warmups=3, runs=2, timeout=None)

    with pytest.raises(NativeSamplingError) as error:
        collect_native_samples(
            artifact,
            plan,
            executor=executor,
            validator=validator,
            statistics_factory=statistics_factory,
        )

    assert error.value.phase is NativeSamplingPhase.WARMUP
    assert error.value.index == failure_position
    assert error.value.validation is validator.validations[failure_position]
    assert len(executor.calls) == failure_position + 1
    assert len(validator.calls) == failure_position + 1
    assert [call["label"] for call in executor.calls] == [
        "preflight",
        *[f"warmup {index}" for index in range(1, failure_position + 1)],
    ]
    assert statistics_factory.calls == []


@pytest.mark.parametrize(
    ("failure_position",),
    ((1,), (2,), (3,)),
)
def test_collect_native_samples_stops_on_measurement_failure(
    tmp_path: Path,
    failure_position: int,
) -> None:
    artifact = _artifact(tmp_path)
    events: list[tuple] = []
    labels = (
        "preflight",
        "warmup 1",
        "warmup 2",
        "measurement 1",
        "measurement 2",
        "measurement 3",
    )
    results = [_result(), _result(duration_ns=1000), _result(duration_ns=1001)]
    for index in range(1, failure_position):
        results.append(_result(duration_ns=2000 + index))
    results.append(_result(returncode=0, stdout="program returned: 7\n"))
    executor = _RecordingExecutor(labels=labels[: len(results)], results=results, events=events)
    validator = _RecordingValidator(labels=labels[: len(results)], events=events)
    statistics_factory = _RecordingStatisticsFactory(events=events)
    plan = NativeSamplingPlan(warmups=2, runs=3, timeout=None)

    with pytest.raises(NativeSamplingError) as error:
        collect_native_samples(
            artifact,
            plan,
            executor=executor,
            validator=validator,
            statistics_factory=statistics_factory,
        )

    assert error.value.phase is NativeSamplingPhase.MEASUREMENT
    assert error.value.index == failure_position
    assert error.value.validation is validator.validations[failure_position + 2]
    assert len(executor.calls) == failure_position + 3
    assert len(validator.calls) == failure_position + 3
    assert [call["label"] for call in executor.calls] == [
        "preflight",
        "warmup 1",
        "warmup 2",
        *[f"measurement {index}" for index in range(1, failure_position + 1)],
    ]
    assert statistics_factory.calls == []


def test_collect_native_samples_propagates_executor_and_statistics_failures(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path)
    events: list[tuple] = []
    labels = ("preflight", "warmup 1", "measurement 1")
    validator = _RecordingValidator(labels=labels, events=events)
    plan = NativeSamplingPlan(warmups=1, runs=1, timeout=None)

    def failing_executor(artifact: NativeArtifact, *, timeout):
        events.append(("executor", "preflight", artifact, timeout, 0))
        raise NativeExecutionError("executor failed")

    with pytest.raises(NativeExecutionError, match="executor failed"):
        collect_native_samples(
            artifact,
            plan,
            executor=failing_executor,
            validator=validator,
            statistics_factory=_RecordingStatisticsFactory(events=events),
        )

    assert validator.calls == []

    executor = _RecordingExecutor(
        labels=labels,
        results=[_result(), _result(duration_ns=1), _result(duration_ns=2)],
        events=events,
    )
    statistics_factory = _RecordingStatisticsFactory(
        events=events,
        error=RuntimeError("statistics failed"),
    )

    with pytest.raises(RuntimeError, match="statistics failed"):
        collect_native_samples(
            artifact,
            plan,
            executor=executor,
            validator=validator,
            statistics_factory=statistics_factory,
        )

    assert len(executor.calls) == 3
    assert len(validator.calls) == 3
    assert statistics_factory.calls == [(2,)]


def test_run_native_sampling_case_uses_defaults_resolved_at_call_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    artifact = _artifact(tmp_path)
    events: list[tuple] = []
    labels = ("preflight", "measurement 1")
    builder = _RecordingBuilder(artifact=artifact, events=events)
    executor = _RecordingExecutor(
        labels=labels,
        results=[_result(duration_ns=0), _result(duration_ns=11)],
        events=events,
    )
    validator = _RecordingValidator(labels=labels, events=events)
    statistics_factory = _RecordingStatisticsFactory(events=events)
    plan = NativeSamplingPlan(warmups=0, runs=1, timeout=2.5)

    monkeypatch.setattr("tools.benchmark_native.build_native_artifact", builder)
    monkeypatch.setattr("tools.benchmark_native.execute_native_artifact", executor)
    monkeypatch.setattr("tools.benchmark_native.validate_native_execution", validator)
    monkeypatch.setattr("tools.benchmark_native.summarize_samples", statistics_factory)

    result = run_native_sampling_case(request, plan)

    assert builder.calls == [request]
    assert len(executor.calls) == 2
    assert len(validator.calls) == 2
    assert statistics_factory.calls == [(11,)]
    assert result.artifact is artifact
    assert result.samples_ns == (11,)
    assert result.statistics.sample_count == 1
    assert events == [
        ("builder", "minimal"),
        ("executor", "preflight", artifact, 2.5, 0),
        ("validator", "preflight", validator.validations[0]),
        ("executor", "measurement 1", artifact, 2.5, 11),
        ("validator", "measurement 1", validator.validations[1]),
        ("statistics", (11,)),
    ]


@pytest.mark.parametrize(
    ("kwargs",),
    (
        ({"warmups": -1, "runs": 1, "timeout": None},),
        ({"warmups": True, "runs": 1, "timeout": None},),
        ({"warmups": 0, "runs": 0, "timeout": None},),
        ({"warmups": 0, "runs": True, "timeout": None},),
        ({"warmups": 0, "runs": 1.5, "timeout": None},),
        ({"warmups": 0, "runs": 1, "timeout": 0},),
    ),
)
def test_invalid_native_sampling_plan_has_no_side_effects(kwargs) -> None:
    builder_calls: list[object] = []
    executor_calls: list[object] = []
    validator_calls: list[object] = []
    statistics_calls: list[object] = []

    def builder(request):
        builder_calls.append(request)
        raise AssertionError("builder must not be called")

    def executor(*args, **kwargs):
        executor_calls.append((args, kwargs))
        raise AssertionError("executor must not be called")

    def validator(*args, **kwargs):
        validator_calls.append((args, kwargs))
        raise AssertionError("validator must not be called")

    def statistics_factory(*args, **kwargs):
        statistics_calls.append((args, kwargs))
        raise AssertionError("statistics factory must not be called")

    with pytest.raises((TypeError, ValueError)):
        NativeSamplingPlan(**kwargs)

    assert builder_calls == []
    assert executor_calls == []
    assert validator_calls == []
    assert statistics_calls == []
    assert not (builder_calls or executor_calls or validator_calls or statistics_calls)
