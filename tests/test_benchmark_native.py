from __future__ import annotations

import hashlib
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from bootstrap.s3.optimizer import OptimizationLevel
from tools.benchmark_native import (
    NativeArtifact,
    NativeBuildError,
    NativeBuildRequest,
    NativeExecutionError,
    NativeExecutionResult,
    NativeValidationError,
    NativeValidationFailureCode,
    build_native_artifact,
    execute_native_artifact,
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
