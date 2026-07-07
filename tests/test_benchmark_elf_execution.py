from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

import tools.benchmark as benchmark
from bootstrap.s3.optimizer import OptimizationLevel
from tools.benchmark_native import (
    NativeArtifact,
    NativeBuildError,
    NativeExecutionError,
    NativeSamplingError,
    NativeSamplingPhase,
    NativeSamplingPlan,
    NativeSamplingResult,
    NativeValidationFailure,
    NativeValidationFailureCode,
    NativeValidationResult,
)
from tools.benchmark_statistics import TimingStatistics


ROOT = Path(__file__).resolve().parents[1]


def _workload(
    workload_id: str,
    *,
    file_name: str | None = None,
    expected_return: int = 0,
    max_instructions: int = 100000,
    max_frames: int = 1000,
) -> dict:
    return {
        "id": workload_id,
        "file": file_name or f"workloads/{workload_id}.s3",
        "description": f"{workload_id} workload",
        "expected_return": expected_return,
        "max_instructions": max_instructions,
        "max_frames": max_frames,
    }


def _manifest(workloads: list[dict]) -> dict:
    return {"manifest_version": "1.0.0", "workloads": workloads}


def _artifact(
    tmp_path: Path,
    *,
    workload_id: str = "minimal",
    optimization: OptimizationLevel = OptimizationLevel.O0,
    expected_return: int = 0,
    size_bytes: int = 1234,
    sha256: str = "a" * 64,
) -> NativeArtifact:
    executable_path = (
        tmp_path
        / "private-user"
        / "AppData"
        / "Local"
        / "Temp"
        / "secret"
        / "program"
    )
    return NativeArtifact(
        workload_id=workload_id,
        optimization=optimization,
        expected_return=expected_return,
        executable_path=executable_path,
        size_bytes=size_bytes,
        sha256=sha256,
    )


def _result(
    tmp_path: Path,
    *,
    workload_id: str = "minimal",
    optimization: OptimizationLevel = OptimizationLevel.O0,
    expected_return: int = 0,
    samples: tuple[int, ...] = (10, 20, 30, 40, 100),
    mean: float = 40.0,
    median: float = 30.0,
    p95: int = 100,
) -> NativeSamplingResult:
    artifact = _artifact(
        tmp_path,
        workload_id=workload_id,
        optimization=optimization,
        expected_return=expected_return,
    )
    statistics = TimingStatistics(
        sample_count=len(samples),
        unit="ns",
        minimum=min(samples),
        maximum=max(samples),
        mean=mean,
        median=median,
        p95=p95,
    )
    return NativeSamplingResult(
        artifact=artifact,
        actual_return=expected_return,
        warmups=2,
        runs=len(samples),
        samples_ns=samples,
        statistics=statistics,
    )


class RecordingTemporaryDirectory:
    def __init__(self, base_dir: Path, events: list[tuple[str, Path]]):
        self.base_dir = base_dir
        self.events = events
        self.path: Path | None = None

    def __enter__(self) -> str:
        index = sum(1 for kind, _ in self.events if kind == "enter") + 1
        self.path = self.base_dir / f"s3-benchmark-elf-{index}"
        self.path.mkdir(parents=True, exist_ok=False)
        self.events.append(("enter", self.path))
        return str(self.path)

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.path is not None
        self.events.append(("exit", self.path))
        shutil.rmtree(self.path)
        self.events.append(("cleanup", self.path))


class RecordingSampler:
    def __init__(self, result_factory, *, error: Exception | None = None):
        self.result_factory = result_factory
        self.error = error
        self.calls: list[tuple[object, NativeSamplingPlan]] = []

    def __call__(self, request, plan):
        self.calls.append((request, plan))
        if self.error is not None:
            raise self.error
        return self.result_factory(request, plan)


def _run_main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> tuple[int, str, str]:
    monkeypatch.setattr(benchmark.sys, "argv", argv)
    with pytest.raises(SystemExit) as exc_info:
        benchmark.main()
    return exc_info.value.code, *pytest.CaptureFixture.readouterr  # type: ignore[attr-defined]


def _invoke_main(monkeypatch: pytest.MonkeyPatch, argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int | None, str, str]:
    monkeypatch.setattr(benchmark.sys, "argv", argv)
    try:
        benchmark.main()
        code: int | None = None
    except SystemExit as error:
        code = error.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _recording_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest: dict,
    sampler: RecordingSampler,
    events: list[tuple[str, Path]],
) -> None:
    monkeypatch.setattr(benchmark, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(benchmark.run_native_sampling_case, "__call__", sampler.__call__, raising=False)
    monkeypatch.setattr(benchmark, "run_native_sampling_case", sampler)
    monkeypatch.setattr(
        benchmark.tempfile,
        "TemporaryDirectory",
        lambda prefix="": RecordingTemporaryDirectory(tmp_path, events),
    )


def _patch_elf_mode_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest: dict,
    sampler: RecordingSampler,
    events: list[tuple[str, Path]],
) -> None:
    monkeypatch.setattr(benchmark, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(benchmark, "run_native_sampling_case", sampler)

    def factory(prefix: str = ""):
        return RecordingTemporaryDirectory(tmp_path, events)

    monkeypatch.setattr(benchmark.tempfile, "TemporaryDirectory", factory)


def _success_sampler(tmp_path: Path):
    def factory(request, plan):
        return _result(
            tmp_path,
            workload_id=request.workload_id,
            optimization=request.optimization,
            expected_return=request.expected_return,
            samples=(10, 20, 30, 40, 100),
            mean=40.0,
            median=30.0,
            p95=100,
        )

    return factory


def test_parser_accepts_elf_execution_mode_and_help_mentions_it(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        benchmark.sys,
        "argv",
        ["benchmark.py", "--help"],
    )

    with pytest.raises(SystemExit) as error:
        benchmark.parse_args()

    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "elf-execution" in help_text
    assert "hosted-pipeline" in help_text
    assert "native-asm-pipeline" in help_text
    assert "--timeout-seconds" in help_text


@pytest.mark.parametrize(
    "mode",
    ("hosted-pipeline", "native-asm-pipeline", "elf-execution"),
)
def test_parser_accepts_documented_modes_and_timeout_default(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setattr(
        benchmark.sys,
        "argv",
        [
            "benchmark.py",
            "--mode",
            mode,
            "--optimization",
            "O0",
            "--workload",
            "minimal",
        ],
    )

    args = benchmark.parse_args()

    assert args.mode == mode
    assert args.timeout_seconds == 10.0


def test_parser_rejects_cli_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        benchmark.sys,
        "argv",
        [
            "benchmark.py",
            "--mode",
            "cli-end-to-end",
            "--format",
            "json",
        ],
    )

    with pytest.raises(SystemExit) as error:
        benchmark.parse_args()

    assert error.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["benchmark_format_version"] == benchmark.BENCHMARK_FORMAT_VERSION
    assert payload["error"]["code"] == "S3_BENCH_INVALID_ARGUMENT"
    assert "cli-end-to-end" in payload["error"]["message"]


@pytest.mark.parametrize(
    "system,machine",
    (
        ("Windows", "AMD64"),
        ("Windows", "x86_64"),
        ("Linux", "arm64"),
        ("Linux", "aarch64"),
        ("Darwin", "x86_64"),
        ("Darwin", "arm64"),
    ),
)
def test_elf_execution_rejects_unsupported_platforms_before_tempdir(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    system: str,
    machine: str,
) -> None:
    events: list[tuple[str, Path]] = []
    sampler = RecordingSampler(_success_sampler(tmp_path))
    manifest = _manifest([_workload("minimal")])

    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: system)
    monkeypatch.setattr(benchmark.platform, "machine", lambda: machine)

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--format",
            "json",
        ],
        capsys,
    )

    assert code == 1
    payload = json.loads(stdout)
    assert payload["benchmark_format_version"] == benchmark.BENCHMARK_FORMAT_VERSION
    assert payload["error"]["code"] == "S3_BENCH_UNSUPPORTED_PLATFORM"
    assert "Linux x86-64" in payload["error"]["message"]
    assert events == []
    assert sampler.calls == []
    assert stderr == ""


@pytest.mark.parametrize(
    "machine",
    ("x86_64", "AMD64"),
)
def test_elf_execution_accepts_linux_x86_64_hosts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    machine: str,
) -> None:
    events: list[tuple[str, Path]] = []
    manifest = _manifest([_workload("minimal")])
    sampler = RecordingSampler(_success_sampler(tmp_path))
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: machine)

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--format",
            "json",
        ],
        capsys,
    )

    assert code is None
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["results"][0]["mode"] == "elf-execution"
    assert sampler.calls
    assert events and events[0][0] == "enter"


@pytest.mark.parametrize(
    "timeout_arg, expected_timeout",
    (
        (None, 10.0),
        ("3", 3.0),
        ("2.5", 2.5),
        ("0.1", 0.1),
    ),
)
def test_elf_execution_forwards_timeout_to_sampling_plan(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    timeout_arg: str | None,
    expected_timeout: float,
) -> None:
    events: list[tuple[str, Path]] = []
    manifest = _manifest([_workload("minimal")])
    sampler = RecordingSampler(_success_sampler(tmp_path))
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    argv = [
        "benchmark.py",
        "--mode",
        "elf-execution",
        "--optimization",
        "O0",
        "--workload",
        "minimal",
        "--format",
        "json",
    ]
    if timeout_arg is not None:
        argv.extend(["--timeout-seconds", timeout_arg])

    code, stdout, _ = _invoke_main(monkeypatch, argv, capsys)

    assert code is None
    payload = json.loads(stdout)
    assert payload["results"][0]["metrics"]["execution"]["total_execution_count"] == 8
    assert len(sampler.calls) == 1
    request, plan = sampler.calls[0]
    assert isinstance(plan, NativeSamplingPlan)
    assert plan.timeout == expected_timeout
    assert request.source_syntax == "0.6"


def test_elf_execution_validates_workloads_and_build_request_adaptation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    events: list[tuple[str, Path]] = []
    manifest = _manifest(
        [
            _workload("arithmetic", expected_return=42, max_instructions=11, max_frames=22),
            _workload("minimal", expected_return=0, max_instructions=33, max_frames=44),
        ]
    )
    sampler = RecordingSampler(_success_sampler(tmp_path))
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "both",
            "--workload",
            "all",
            "--warmups",
            "2",
            "--runs",
            "5",
            "--format",
            "json",
            "--include-samples",
        ],
        capsys,
    )

    assert code is None
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["benchmark_format_version"] == benchmark.BENCHMARK_FORMAT_VERSION
    assert [result["workload"] for result in payload["results"]] == ["arithmetic", "minimal"]
    assert [sorted(result) for result in payload["results"]] == [
        ["O0", "O1", "status", "workload"],
        ["O0", "O1", "status", "workload"],
    ]

    assert len(sampler.calls) == 4
    request0, plan0 = sampler.calls[0]
    request1, plan1 = sampler.calls[1]
    request2, plan2 = sampler.calls[2]
    request3, plan3 = sampler.calls[3]

    assert request0.workload_id == "arithmetic"
    assert request1.workload_id == "arithmetic"
    assert request2.workload_id == "minimal"
    assert request3.workload_id == "minimal"
    assert request0.optimization is OptimizationLevel.O0
    assert request1.optimization is OptimizationLevel.O1
    assert request2.optimization is OptimizationLevel.O0
    assert request3.optimization is OptimizationLevel.O1

    for request, expected_return, max_instructions, max_frames in (
        (request0, 42, 11, 22),
        (request1, 42, 11, 22),
        (request2, 0, 33, 44),
        (request3, 0, 33, 44),
    ):
        assert request.source_path == ROOT / "benchmarks" / "workloads" / f"{request.workload_id}.s3"
        assert request.expected_return == expected_return
        assert request.max_instructions == max_instructions
        assert request.max_frames == max_frames
        assert request.source_syntax == "0.6"
        assert request.output_path.parent.name.startswith("s3-benchmark-elf-")
        assert ROOT not in request.output_path.parents

    assert [plan.warmups for _, plan in sampler.calls] == [2, 2, 2, 2]
    assert [plan.runs for _, plan in sampler.calls] == [5, 5, 5, 5]
    assert [plan.timeout for _, plan in sampler.calls] == [10.0, 10.0, 10.0, 10.0]
    assert len({request.output_path for request, _ in sampler.calls}) == 4
    assert len(events) == 12
    assert [kind for kind, _ in events] == [
        "enter",
        "exit",
        "cleanup",
        "enter",
        "exit",
        "cleanup",
        "enter",
        "exit",
        "cleanup",
        "enter",
        "exit",
        "cleanup",
    ]


@pytest.mark.parametrize("format_name", ("json", "text"))
def test_elf_execution_output_sanitizes_private_data(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    format_name: str,
) -> None:
    private_token = "PRIVATE_TOKEN_SENTINEL"
    private_stdout = "PRIVATE_STDOUT_SENTINEL"
    private_stderr = "PRIVATE_STDERR_SENTINEL"
    private_path = "PRIVATE_PATH_SENTINEL"

    def result_factory(request, plan):
        artifact = _artifact(tmp_path, workload_id=request.workload_id)
        artifact = NativeArtifact(
            workload_id=artifact.workload_id,
            optimization=artifact.optimization,
            expected_return=artifact.expected_return,
            executable_path=Path(private_path),
            size_bytes=artifact.size_bytes,
            sha256=artifact.sha256,
        )
        return NativeSamplingResult(
            artifact=artifact,
            actual_return=request.expected_return,
            warmups=plan.warmups,
            runs=plan.runs,
            samples_ns=(10, 20, 30, 40, 100),
            statistics=TimingStatistics(
                sample_count=5,
                unit="ns",
                minimum=10,
                maximum=100,
                mean=40.0,
                median=30.0,
                p95=100,
            ),
        )

    events: list[tuple[str, Path]] = []
    manifest = _manifest([_workload("minimal")])
    sampler = RecordingSampler(result_factory)
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--warmups",
            "2",
            "--runs",
            "5",
            "--format",
            format_name,
            "--include-samples",
        ],
        capsys,
    )

    assert code is None
    assert private_token not in stdout
    assert private_path not in stdout
    assert private_stdout not in stdout
    assert private_stderr not in stdout
    assert "traceback" not in stdout.lower()
    assert stderr == ""

    if format_name == "json":
        payload = json.loads(stdout)
        assert payload["benchmark_format_version"] == benchmark.BENCHMARK_FORMAT_VERSION
        assert payload["results"][0]["metrics"]["native_artifact"]["artifact_kind"] == benchmark.ELF_ARTIFACT_KIND
        assert payload["results"][0]["metrics"]["execution"]["build_count"] == 1
        assert payload["results"][0]["timing"]["unit"] == "ns"
    else:
        assert "artifact size: 1234 bytes" in stdout
        assert "artifact sha256:" in stdout
        assert "warmups: 2" in stdout
        assert "runs: 5" in stdout
        assert "p95" in stdout


@pytest.mark.parametrize("non_finite", (math.nan, math.inf, -math.inf))
def test_elf_execution_strict_json_rejects_non_finite_statistics(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    non_finite: float,
) -> None:
    def result_factory(request, plan):
        return NativeSamplingResult(
            artifact=_artifact(tmp_path, workload_id=request.workload_id),
            actual_return=request.expected_return,
            warmups=plan.warmups,
            runs=plan.runs,
            samples_ns=(10, 20, 30, 40, 100),
            statistics=TimingStatistics(
                sample_count=5,
                unit="ns",
                minimum=10,
                maximum=100,
                mean=non_finite,
                median=30.0,
                p95=100,
            ),
        )

    events: list[tuple[str, Path]] = []
    manifest = _manifest([_workload("minimal")])
    sampler = RecordingSampler(result_factory)
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--warmups",
            "2",
            "--runs",
            "5",
            "--format",
            "json",
        ],
        capsys,
    )

    assert code == 1
    payload = json.loads(stdout)
    assert payload["error"]["code"] == "S3_BENCH_NATIVE_SAMPLING_FAILED"
    assert "NaN" not in stdout
    assert "Infinity" not in stdout
    assert "-Infinity" not in stdout
    assert stderr == ""
    assert events and events[0][0] == "enter"


@pytest.mark.parametrize(
    "error_exc,error_code",
    (
        (NativeBuildError("build failed"), "S3_BENCH_NATIVE_BUILD_FAILED"),
        (NativeExecutionError("execution failed"), "S3_BENCH_NATIVE_EXECUTION_FAILED"),
        (
            NativeSamplingError(
                NativeSamplingPhase.PREFLIGHT,
                None,
                NativeValidationResult(
                    valid=False,
                    expected_return=0,
                    observed_return=None,
                    failures=(
                        NativeValidationFailure(
                            NativeValidationFailureCode.STDOUT_EMPTY,
                            "native execution emitted no stdout",
                        ),
                    ),
                ),
            ),
            "S3_BENCH_NATIVE_VALIDATION_FAILED",
        ),
        (ValueError("sampling failed"), "S3_BENCH_NATIVE_SAMPLING_FAILED"),
    ),
)
def test_elf_execution_reports_structured_errors_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    error_exc: Exception,
    error_code: str,
) -> None:
    events: list[tuple[str, Path]] = []
    manifest = _manifest([_workload("minimal")])
    sampler = RecordingSampler(_success_sampler(tmp_path), error=error_exc)
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--format",
            "json",
        ],
        capsys,
    )

    assert code == 1
    payload = json.loads(stdout)
    assert payload["benchmark_format_version"] == benchmark.BENCHMARK_FORMAT_VERSION
    assert payload["error"]["code"] == error_code
    assert "traceback" not in stderr.lower()
    assert events and events[0][0] == "enter"
    assert events[-1][0] == "cleanup"


@pytest.mark.parametrize(
    "timeout_arg",
    ("0", "-1", "nan", "inf", "-inf", "bogus"),
)
def test_elf_execution_rejects_invalid_timeout_before_tempdir(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    timeout_arg: str,
) -> None:
    events: list[tuple[str, Path]] = []
    manifest = _manifest([_workload("minimal")])
    sampler = RecordingSampler(_success_sampler(tmp_path))
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--warmups",
            "2",
            "--runs",
            "5",
            "--format",
            "json",
            "--timeout-seconds",
            timeout_arg,
        ],
        capsys,
    )

    assert code == 1
    payload = json.loads(stdout)
    assert payload["benchmark_format_version"] == benchmark.BENCHMARK_FORMAT_VERSION
    assert payload["error"]["code"] == "S3_BENCH_INVALID_ARGUMENT"
    assert events == []
    assert sampler.calls == []
    assert stderr == ""


@pytest.mark.parametrize("mode", ("hosted-pipeline", "native-asm-pipeline"))
def test_legacy_modes_do_not_use_elf_tempdirs_or_sampler(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    mode: str,
) -> None:
    manifest = _manifest([_workload("minimal")])
    events: list[tuple[str, Path]] = []
    sampler = RecordingSampler(_success_sampler(tmp_path))
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    def hosted_pipeline(source, opt, max_inst, max_frames, clock=None):
        return 0, {"parsing": 1}, {"ir": {}}, {"execution": {"executed_s3_opcodes": 0, "maximum_frame_depth_observed": 0, "function_call_count": 0}}, 1, 1, 0

    def native_asm_pipeline(source, opt, max_inst, max_frames, clock=None):
        return "assembly", {"parsing": 1}, {"ir": {}, "native_artifact": {"artifact_kind": "gnu-x86-64-assembly", "textual_size_bytes": 1, "line_count": 1, "sha256": "a" * 64}}, 1, 1, 0

    monkeypatch.setattr(benchmark, "run_hosted_pipeline", hosted_pipeline)
    monkeypatch.setattr(benchmark, "run_native_asm_pipeline", native_asm_pipeline)

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            mode,
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--format",
            "json",
            "--timeout-seconds",
            "-1",
        ],
        capsys,
    )

    assert code is None
    payload = json.loads(stdout)
    assert payload["benchmark_format_version"] == benchmark.BENCHMARK_FORMAT_VERSION
    assert payload["results"][0]["status"] == "passed"
    assert events == []
    assert sampler.calls == []
    assert stderr == ""


def test_elf_execution_output_to_file_and_textual_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    manifest = _manifest([_workload("minimal")])
    events: list[tuple[str, Path]] = []
    sampler = RecordingSampler(_success_sampler(tmp_path))
    _patch_elf_mode_environment(monkeypatch, tmp_path, manifest, sampler, events)
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    json_output = tmp_path / "out.json"
    text_output = tmp_path / "out.txt"

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--warmups",
            "2",
            "--runs",
            "5",
            "--format",
            "json",
            "--output",
            str(json_output),
            "--include-samples",
        ],
        capsys,
    )

    assert code is None
    assert stdout == ""
    assert stderr == ""
    json_payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert json_payload["benchmark_format_version"] == benchmark.BENCHMARK_FORMAT_VERSION
    assert json_payload["results"][0]["metrics"]["execution"]["runs"] == 5

    code, stdout, stderr = _invoke_main(
        monkeypatch,
        [
            "benchmark.py",
            "--mode",
            "elf-execution",
            "--optimization",
            "O0",
            "--workload",
            "minimal",
            "--warmups",
            "2",
            "--runs",
            "5",
            "--format",
            "text",
            "--output",
            str(text_output),
        ],
        capsys,
    )

    assert code is None
    assert stdout == ""
    assert stderr == ""
    text_payload = text_output.read_text(encoding="utf-8")
    assert "workload: minimal" in text_payload
    assert "mode: elf-execution" in text_payload
    assert "optimization: O0" in text_payload
    assert "artifact size: 1234 bytes" in text_payload
    assert "artifact sha256:" in text_payload
    assert "PRIVATE_TOKEN_SENTINEL" not in text_payload
