"""Core implementation of the versioned s3bench protocol."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import platform
import statistics as stdlib_statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

BENCHMARK_SCHEMA_VERSION = "1.0.0"
MANIFEST_VERSION = "1.0.0"
DEFAULT_WARMUPS = 3
DEFAULT_SAMPLES = 15
DEFAULT_TARGET_SAMPLE_NS = 200_000_000
DEFAULT_MAX_LOOPS = 1_000_000
DEFAULT_MAX_CALIBRATION_ATTEMPTS = 20
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_CAPTURE_BYTES = 1_048_576

COMPARABILITY = {
    "COMPARABLE",
    "PARTIALLY_COMPARABLE",
    "NOT_COMPARABLE",
}


class BenchmarkError(RuntimeError):
    """A benchmark phase could not produce a valid observation."""


class AdapterUnavailable(BenchmarkError):
    """A requested implementation cannot run in the detected environment."""


class ManifestError(ValueError):
    """The versioned workload manifest is invalid."""


@dataclass(frozen=True, slots=True)
class Statistics:
    median_ns: float
    mean_ns: float
    minimum_ns: int
    maximum_ns: int
    standard_deviation_ns: float
    coefficient_of_variation: float
    percentile_95_ns: int


@dataclass(frozen=True, slots=True)
class Calibration:
    loops_per_sample: int
    attempts: int
    last_duration_ns: int


@dataclass(frozen=True, slots=True)
class CommandResult:
    arguments: tuple[str, ...]
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    output_truncated: bool
    duration_ns: int


@dataclass(frozen=True, slots=True)
class BuildArtifact:
    path: Path | None = None
    compile_duration_ns: int | None = None
    link_duration_ns: int | None = None
    artifact_size_bytes: int | None = None
    artifact_metrics: Mapping[str, int] = field(default_factory=dict)
    compiler_name: str | None = None
    compiler_version: str | None = None
    compiler_flags: tuple[str, ...] = ()
    linker: str | None = None
    notes: tuple[str, ...] = ()
    payload: object | None = None


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    checksum: str | None
    duration_ns: int
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = 0
    timed_out: bool = False
    output_truncated: bool = False
    startup_duration_ns: int | None = None
    kernel_duration_ns: int | None = None
    end_to_end_duration_ns: int | None = None
    peak_memory_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class Case:
    campaign: str
    benchmark_id: str
    workload_version: str
    category: str
    suite: str
    implementation: str
    adapter: str
    execution_mode: str
    optimization_mode: str
    input_id: str
    input_size: int
    expected_checksum: str
    timeout_seconds: float
    timed_region: str
    source: Path | None
    configuration: Mapping[str, object] = field(default_factory=dict)

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.benchmark_id,
            self.implementation,
            self.execution_mode,
            self.optimization_mode,
        )


class Adapter(Protocol):
    """Execution boundary implemented by S3 and external toolchain adapters."""

    def build(self, case: Case, build_dir: Path) -> BuildArtifact:
        """Build one benchmark case without measuring its runtime."""

    def execute(
        self,
        case: Case,
        artifact: BuildArtifact,
        loops: int,
        timeout_seconds: float,
    ) -> ExecutionObservation:
        """Execute exactly ``loops`` kernel repetitions."""


def compute_statistics(samples: Sequence[int]) -> Statistics:
    if not samples:
        raise ValueError("at least one sample is required")
    if any(not isinstance(value, int) or value < 0 for value in samples):
        raise ValueError("samples must be non-negative integer nanoseconds")
    ordered = sorted(samples)
    mean = float(stdlib_statistics.fmean(ordered))
    deviation = float(stdlib_statistics.stdev(ordered)) if len(ordered) > 1 else 0.0
    cv = deviation / mean if mean else 0.0
    percentile_index = math.ceil(0.95 * len(ordered)) - 1
    return Statistics(
        median_ns=float(stdlib_statistics.median(ordered)),
        mean_ns=mean,
        minimum_ns=ordered[0],
        maximum_ns=ordered[-1],
        standard_deviation_ns=deviation,
        coefficient_of_variation=cv,
        percentile_95_ns=ordered[percentile_index],
    )


def calibrate(
    measure: Callable[[int], int],
    *,
    target_sample_ns: int = DEFAULT_TARGET_SAMPLE_NS,
    initial_loops: int = 1,
    maximum_loops: int = DEFAULT_MAX_LOOPS,
    maximum_attempts: int = DEFAULT_MAX_CALIBRATION_ATTEMPTS,
) -> Calibration:
    if target_sample_ns <= 0:
        raise ValueError("target_sample_ns must be positive")
    if initial_loops <= 0 or maximum_loops < initial_loops:
        raise ValueError("loop bounds are invalid")
    if maximum_attempts <= 0:
        raise ValueError("maximum_attempts must be positive")

    loops = initial_loops
    last_duration = 0
    for attempt in range(1, maximum_attempts + 1):
        last_duration = measure(loops)
        if not isinstance(last_duration, int) or last_duration < 0:
            raise BenchmarkError("calibration returned an invalid duration")
        if last_duration >= target_sample_ns or loops == maximum_loops:
            return Calibration(loops, attempt, last_duration)
        if last_duration == 0:
            proposed = loops * 10
        else:
            ratio = max(2, math.ceil(target_sample_ns / last_duration))
            proposed = loops * min(ratio, 10)
        loops = min(maximum_loops, proposed)
    raise BenchmarkError("calibration attempt limit reached")


def run_command(
    arguments: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    clock: Callable[[], int] = time.perf_counter_ns,
) -> CommandResult:
    if not arguments or any(not isinstance(value, str) or not value for value in arguments):
        raise ValueError("command arguments must be non-empty strings")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    start = clock()
    try:
        completed = subprocess.run(
            list(arguments),
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout_seconds,
            check=False,
        )
        duration = clock() - start
        stdout, stdout_truncated = _bounded_output(completed.stdout)
        stderr, stderr_truncated = _bounded_output(completed.stderr)
        return CommandResult(
            tuple(arguments),
            stdout,
            stderr,
            completed.returncode,
            False,
            stdout_truncated or stderr_truncated,
            duration,
        )
    except subprocess.TimeoutExpired as error:
        duration = clock() - start
        stdout, stdout_truncated = _bounded_output(_decode_timeout_output(error.stdout))
        stderr, stderr_truncated = _bounded_output(_decode_timeout_output(error.stderr))
        return CommandResult(
            tuple(arguments),
            stdout,
            stderr,
            None,
            True,
            stdout_truncated or stderr_truncated,
            duration,
        )


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _bounded_output(value: str) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= MAX_CAPTURE_BYTES:
        return value, False
    bounded = encoded[:MAX_CAPTURE_BYTES].decode("utf-8", errors="ignore")
    return bounded, True


def extract_checksum(stdout: str) -> str:
    matches = [
        line.removeprefix("checksum=").strip()
        for line in stdout.splitlines()
        if line.startswith("checksum=")
    ]
    if len(matches) != 1 or not matches[0]:
        raise BenchmarkError("output must contain exactly one checksum=<value> line")
    return matches[0]


def load_manifest(path: Path) -> tuple[dict[str, object], tuple[Case, ...]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"could not read manifest: {error}") from error
    if not isinstance(document, dict):
        raise ManifestError("manifest root must be an object")
    if document.get("manifest_version") != MANIFEST_VERSION:
        raise ManifestError("unsupported manifest version")
    campaign = _required_string(document, "campaign")
    workloads = document.get("workloads")
    if not isinstance(workloads, list) or not workloads:
        raise ManifestError("manifest workloads must be a non-empty array")

    root = (path.parent.parent if path.parent.name == "manifests" else path.parent).resolve()
    seen_ids: set[str] = set()
    cases: list[Case] = []
    for workload in workloads:
        if not isinstance(workload, dict):
            raise ManifestError("workload entries must be objects")
        benchmark_id = _required_string(workload, "benchmark_id")
        if benchmark_id in seen_ids:
            raise ManifestError(f"duplicate benchmark ID: {benchmark_id}")
        seen_ids.add(benchmark_id)
        workload_version = _required_string(workload, "workload_version")
        category = _required_string(workload, "category")
        suite = _required_string(workload, "suite")
        if suite not in {"portable", "s3-specific"}:
            raise ManifestError(f"invalid suite for {benchmark_id}")
        _required_string(workload, "objective")
        expected_checksum = _required_string(workload, "expected_checksum")
        timed_region = _required_string(workload, "timed_region")
        input_data = workload.get("input")
        if not isinstance(input_data, dict):
            raise ManifestError(f"missing input for {benchmark_id}")
        input_id = _required_string(input_data, "id")
        input_size = input_data.get("size")
        if not isinstance(input_size, int) or input_size < 0:
            raise ManifestError(f"invalid input size for {benchmark_id}")
        implementations = workload.get("implementations")
        if not isinstance(implementations, list) or not implementations:
            raise ManifestError(f"missing implementations for {benchmark_id}")
        for implementation in implementations:
            if not isinstance(implementation, dict):
                raise ManifestError(f"invalid implementation for {benchmark_id}")
            source = _resolve_optional_source(root, implementation.get("source"))
            optimization_modes = implementation.get("optimization_modes")
            if not isinstance(optimization_modes, list) or not optimization_modes:
                raise ManifestError(f"missing optimization modes for {benchmark_id}")
            for optimization_mode in optimization_modes:
                if not isinstance(optimization_mode, str) or not optimization_mode:
                    raise ManifestError(f"invalid optimization mode for {benchmark_id}")
                timeout = implementation.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
                if not isinstance(timeout, (int, float)) or timeout <= 0:
                    raise ManifestError(f"invalid timeout for {benchmark_id}")
                cases.append(
                    Case(
                        campaign=campaign,
                        benchmark_id=benchmark_id,
                        workload_version=workload_version,
                        category=category,
                        suite=suite,
                        implementation=_required_string(implementation, "id"),
                        adapter=_required_string(implementation, "adapter"),
                        execution_mode=_required_string(implementation, "execution_mode"),
                        optimization_mode=optimization_mode,
                        input_id=input_id,
                        input_size=input_size,
                        expected_checksum=expected_checksum,
                        timeout_seconds=float(timeout),
                        timed_region=timed_region,
                        source=source,
                        configuration=dict(implementation),
                    )
                )
    cases.sort(key=lambda case: case.identity)
    return document, tuple(cases)


def _required_string(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"missing non-empty string: {key}")
    return value


def _resolve_optional_source(root: Path, value: object) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ManifestError("source must be a non-empty relative path")
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ManifestError("source path escapes the manifest directory") from error
    if not candidate.is_file():
        raise ManifestError(f"source file does not exist: {value}")
    return candidate


def collect_environment_metadata(
    *,
    repository_root: Path,
    runner_type: str,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    return {
        "repository_sha": _git_value(repository_root, ["rev-parse", "HEAD"]),
        "repository_dirty": bool(
            _git_value(repository_root, ["status", "--porcelain", "--untracked-files=normal"])
        ),
        "operating_system": platform.system(),
        "architecture": platform.machine(),
        "cpu_model": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "physical_cpu_count": None,
        "total_memory_bytes": _total_memory_bytes(),
        "python_version": platform.python_version(),
        "runner_type": runner_type,
        "timestamp_utc": timestamp_utc or dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def _git_value(root: Path, arguments: Sequence[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def _total_memory_bytes() -> int | None:
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            return None
    return None


class BenchmarkHarness:
    """Runs cases through the normative correctness-first phase sequence."""

    def __init__(
        self,
        adapters: Mapping[str, Adapter],
        *,
        repository_root: Path,
        clock: Callable[[], int] = time.perf_counter_ns,
    ) -> None:
        self._adapters = dict(adapters)
        self._repository_root = repository_root.resolve()
        self._clock = clock

    def discover(
        self,
        cases: Sequence[Case],
        *,
        benchmark_ids: set[str] | None = None,
        categories: set[str] | None = None,
        implementations: set[str] | None = None,
        execution_modes: set[str] | None = None,
        optimization_modes: set[str] | None = None,
    ) -> tuple[Case, ...]:
        selected = [
            case
            for case in cases
            if (benchmark_ids is None or case.benchmark_id in benchmark_ids)
            and (categories is None or case.category in categories)
            and (implementations is None or case.implementation in implementations)
            and (execution_modes is None or case.execution_mode in execution_modes)
            and (optimization_modes is None or case.optimization_mode in optimization_modes)
        ]
        return tuple(sorted(selected, key=lambda case: case.identity))

    def run_case(
        self,
        case: Case,
        *,
        build_dir: Path,
        warmups: int = DEFAULT_WARMUPS,
        samples: int = DEFAULT_SAMPLES,
        loops: int | None = None,
        target_sample_ns: int = DEFAULT_TARGET_SAMPLE_NS,
        verify_only: bool = False,
        build_only: bool = False,
        maximum_loops: int = DEFAULT_MAX_LOOPS,
    ) -> dict[str, object]:
        if warmups < 0 or samples <= 0:
            raise ValueError("warmups must be non-negative and samples must be positive")
        adapter = self._adapters.get(case.adapter)
        if adapter is None:
            raise BenchmarkError(f"adapter is unavailable: {case.adapter}")

        phase_status = {name: "pending" for name in (
            "discover", "build", "verify", "warmup", "calibrate", "measure",
            "summarize", "export", "compare", "render_report",
        )}
        phase_status["discover"] = "complete"
        artifact = adapter.build(case, build_dir)
        phase_status["build"] = "complete"
        if build_only:
            return self._base_result(case, artifact, phase_status, "built", warmups, samples)

        verification = adapter.execute(case, artifact, 1, case.timeout_seconds)
        self._require_valid_observation(case, verification)
        phase_status["verify"] = "complete"
        if verify_only:
            result = self._base_result(case, artifact, phase_status, "verified", warmups, samples)
            result["observed_checksum"] = verification.checksum
            result["correctness_status"] = "verified"
            return result

        for _ in range(warmups):
            observation = adapter.execute(case, artifact, 1, case.timeout_seconds)
            self._require_valid_observation(case, observation)
        phase_status["warmup"] = "complete"

        if loops is None:
            calibration = calibrate(
                lambda count: self._measured_duration(case, adapter, artifact, count),
                target_sample_ns=target_sample_ns,
                maximum_loops=maximum_loops,
            )
            loops = calibration.loops_per_sample
        else:
            if loops <= 0 or loops > maximum_loops:
                raise ValueError("loops is outside the configured bounds")
            calibration = Calibration(loops, 0, 0)
        phase_status["calibrate"] = "complete"

        raw_durations: list[int] = []
        last_observation = verification
        for _ in range(samples):
            last_observation = adapter.execute(case, artifact, loops, case.timeout_seconds)
            self._require_valid_observation(case, last_observation)
            raw_durations.append(last_observation.duration_ns)
        phase_status["measure"] = "complete"
        summary = compute_statistics(raw_durations)
        phase_status["summarize"] = "complete"

        result = self._base_result(case, artifact, phase_status, "measured", warmups, samples)
        result.update(
            {
                "observed_checksum": last_observation.checksum,
                "correctness_status": "verified",
                "loops_per_sample": loops,
                "raw_durations_ns": raw_durations,
                "median_ns": summary.median_ns,
                "mean_ns": summary.mean_ns,
                "minimum_ns": summary.minimum_ns,
                "maximum_ns": summary.maximum_ns,
                "standard_deviation_ns": summary.standard_deviation_ns,
                "coefficient_of_variation": summary.coefficient_of_variation,
                "percentile_95_ns": summary.percentile_95_ns,
                "startup_duration_ns": last_observation.startup_duration_ns,
                "kernel_duration_ns": last_observation.kernel_duration_ns,
                "end_to_end_duration_ns": last_observation.end_to_end_duration_ns,
                "peak_memory_bytes": last_observation.peak_memory_bytes,
                "calibration_attempts": calibration.attempts,
            }
        )
        if summary.coefficient_of_variation > 0.10:
            result["notes"].append("high variability: coefficient of variation exceeds 0.10")
        return result

    def _measured_duration(
        self,
        case: Case,
        adapter: Adapter,
        artifact: BuildArtifact,
        loops: int,
    ) -> int:
        observation = adapter.execute(case, artifact, loops, case.timeout_seconds)
        self._require_valid_observation(case, observation)
        return observation.duration_ns

    @staticmethod
    def _require_valid_observation(case: Case, observation: ExecutionObservation) -> None:
        if observation.timed_out:
            raise BenchmarkError(f"{case.benchmark_id}: execution timed out")
        if observation.output_truncated:
            raise BenchmarkError(f"{case.benchmark_id}: output was truncated")
        if observation.exit_code != 0:
            raise BenchmarkError(
                f"{case.benchmark_id}: execution failed with status {observation.exit_code}"
            )
        if observation.checksum != case.expected_checksum:
            raise BenchmarkError(
                f"{case.benchmark_id}: checksum mismatch; expected "
                f"{case.expected_checksum}, observed {observation.checksum}"
            )

    def _base_result(
        self,
        case: Case,
        artifact: BuildArtifact,
        phase_status: Mapping[str, str],
        status: str,
        warmups: int,
        samples: int,
    ) -> dict[str, object]:
        metadata = collect_environment_metadata(
            repository_root=self._repository_root,
            runner_type="local",
        )
        notes = list(artifact.notes)
        return {
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "campaign": case.campaign,
            "benchmark_id": case.benchmark_id,
            "workload_version": case.workload_version,
            "category": case.category,
            "suite": case.suite,
            "implementation": case.implementation,
            "execution_mode": case.execution_mode,
            "optimization_mode": case.optimization_mode,
            "phase": "end_to_end",
            "status": status,
            "phase_status": dict(phase_status),
            "input_id": case.input_id,
            "input_size": case.input_size,
            "expected_checksum": case.expected_checksum,
            "observed_checksum": None,
            "correctness_status": "not-run" if status == "built" else "pending",
            "warmup_count": warmups,
            "sample_count": samples,
            "loops_per_sample": None,
            "raw_durations_ns": [],
            "median_ns": None,
            "mean_ns": None,
            "minimum_ns": None,
            "maximum_ns": None,
            "standard_deviation_ns": None,
            "coefficient_of_variation": None,
            "percentile_95_ns": None,
            "compile_duration_ns": artifact.compile_duration_ns,
            "link_duration_ns": artifact.link_duration_ns,
            "startup_duration_ns": None,
            "kernel_duration_ns": None,
            "end_to_end_duration_ns": None,
            "artifact_size_bytes": artifact.artifact_size_bytes,
            "artifact_metrics": dict(sorted(artifact.artifact_metrics.items())),
            "peak_memory_bytes": None,
            **metadata,
            "compiler_name": artifact.compiler_name,
            "compiler_version": artifact.compiler_version,
            "compiler_flags": list(artifact.compiler_flags),
            "linker": artifact.linker,
            "notes": notes,
            "comparability_classification": "NOT_COMPARABLE",
        }


def validate_result_document(document: Mapping[str, object]) -> None:
    required = {
        "schema_version", "campaign", "benchmark_id", "workload_version",
        "category", "implementation", "execution_mode", "optimization_mode",
        "phase", "input_id", "input_size", "expected_checksum",
        "correctness_status", "warmup_count", "sample_count",
        "raw_durations_ns", "repository_sha", "repository_dirty",
        "operating_system", "architecture", "python_version", "runner_type",
        "timestamp_utc", "notes", "artifact_metrics", "comparability_classification",
    }
    missing = sorted(required.difference(document))
    if missing:
        raise ValueError(f"result is missing required fields: {', '.join(missing)}")
    if document.get("schema_version") != BENCHMARK_SCHEMA_VERSION:
        raise ValueError("unsupported result schema version")
    if document.get("comparability_classification") not in COMPARABILITY:
        raise ValueError("invalid comparability classification")
    raw = document.get("raw_durations_ns")
    if not isinstance(raw, list) or any(not isinstance(value, int) or value < 0 for value in raw):
        raise ValueError("raw durations must be non-negative integer nanoseconds")
    serialized = json.dumps(document, allow_nan=False)
    forbidden = ("hostname", "username", "home_directory", "environment")
    if any(key in document for key in forbidden):
        raise ValueError("result contains forbidden private metadata")
    if _contains_personal_path(serialized):
        raise ValueError("result contains a personal absolute path")


def unavailable_result(
    case: Case,
    *,
    repository_root: Path,
    reason: str,
    runner_type: str = "local",
) -> dict[str, object]:
    metadata = collect_environment_metadata(
        repository_root=repository_root,
        runner_type=runner_type,
    )
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "campaign": case.campaign,
        "benchmark_id": case.benchmark_id,
        "workload_version": case.workload_version,
        "category": case.category,
        "suite": case.suite,
        "implementation": case.implementation,
        "execution_mode": case.execution_mode,
        "optimization_mode": case.optimization_mode,
        "phase": "end_to_end",
        "status": "unavailable",
        "phase_status": {"discover": "complete", "build": "unavailable"},
        "input_id": case.input_id,
        "input_size": case.input_size,
        "expected_checksum": case.expected_checksum,
        "observed_checksum": None,
        "correctness_status": "not-run",
        "warmup_count": 0,
        "sample_count": 1,
        "loops_per_sample": None,
        "raw_durations_ns": [],
        "median_ns": None,
        "mean_ns": None,
        "minimum_ns": None,
        "maximum_ns": None,
        "standard_deviation_ns": None,
        "coefficient_of_variation": None,
        "percentile_95_ns": None,
        "compile_duration_ns": None,
        "link_duration_ns": None,
        "startup_duration_ns": None,
        "kernel_duration_ns": None,
        "end_to_end_duration_ns": None,
        "artifact_size_bytes": None,
        "peak_memory_bytes": None,
        "artifact_metrics": {},
        **metadata,
        "compiler_name": None,
        "compiler_version": None,
        "compiler_flags": [],
        "linker": None,
        "notes": [reason],
        "comparability_classification": "NOT_COMPARABLE",
    }


def _contains_personal_path(value: str) -> bool:
    lowered = value.lower().replace("\\\\", "/").replace("\\", "/")
    return "/users/" in lowered or "/home/" in lowered


def write_json(path: Path, results: Sequence[Mapping[str, object]]) -> None:
    ordered = sorted(
        results,
        key=lambda result: (
            str(result.get("benchmark_id", "")),
            str(result.get("implementation", "")),
            str(result.get("execution_mode", "")),
            str(result.get("optimization_mode", "")),
        ),
    )
    for result in ordered:
        validate_result_document(result)
    payload = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "results": ordered,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def duration_per_loop_ns(
    result: Mapping[str, object],
    *,
    duration_key: str = "median_ns",
) -> float | None:
    duration = result.get(duration_key)
    loops = result.get("loops_per_sample")
    if (
        not isinstance(duration, (int, float))
        or not isinstance(loops, int)
        or isinstance(loops, bool)
        or loops <= 0
    ):
        return None
    return float(duration) / loops


def compare_results(
    results: Sequence[Mapping[str, object]],
    *,
    reference_implementation: str,
) -> list[dict[str, object]]:
    by_workload: dict[str, list[Mapping[str, object]]] = {}
    for result in results:
        by_workload.setdefault(str(result["benchmark_id"]), []).append(result)
    comparisons: list[dict[str, object]] = []
    for benchmark_id in sorted(by_workload):
        group = by_workload[benchmark_id]
        reference = next(
            (item for item in group if item.get("implementation") == reference_implementation),
            None,
        )
        reference_per_loop = duration_per_loop_ns(reference) if reference else None
        for item in sorted(group, key=lambda entry: str(entry.get("implementation"))):
            median = item.get("median_ns")
            median_per_loop = duration_per_loop_ns(item)
            comparable = item.get("comparability_classification") == "COMPARABLE"
            ratio = None
            if comparable and median_per_loop is not None and reference_per_loop is not None and reference_per_loop > 0:
                ratio = median_per_loop / reference_per_loop
            comparisons.append(
                {
                    "benchmark_id": benchmark_id,
                    "implementation": item.get("implementation"),
                    "median_ns": median,
                    "median_ns_per_loop": median_per_loop,
                    "loops_per_sample": item.get("loops_per_sample"),
                    "reference_implementation": reference_implementation,
                    "normalized_ratio": ratio,
                    "comparability_classification": item.get("comparability_classification"),
                }
            )
    return comparisons


def render_markdown(
    results: Sequence[Mapping[str, object]],
    *,
    title: str = "S3 Benchmark Report",
) -> str:
    lines = [
        f"# {title}",
        "",
        "Median is the primary statistic. Missing values are rendered as `unavailable`.",
        "",
        "| Benchmark | Implementation | Mode | Optimization | Median/sample (ns) | Loops | Median/loop (ns) | CV | Classification |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in sorted(
        results,
        key=lambda item: (
            str(item.get("benchmark_id", "")),
            str(item.get("implementation", "")),
            str(item.get("execution_mode", "")),
            str(item.get("optimization_mode", "")),
        ),
    ):
        median = _render_value(result.get("median_ns"))
        median_per_loop = _render_value(duration_per_loop_ns(result))
        cv = _render_value(result.get("coefficient_of_variation"))
        lines.append(
            f"| {result.get('benchmark_id')} | {result.get('implementation')} | "
            f"{result.get('execution_mode')} | {result.get('optimization_mode')} | "
            f"{median} | {_render_value(result.get('loops_per_sample'))} | "
            f"{median_per_loop} | {cv} | {result.get('comparability_classification')} |"
        )
    lines.extend(("", "Raw samples remain in the companion JSON result file.", ""))
    return "\n".join(lines)


def _render_value(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
