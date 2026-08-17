"""Deterministic user-facing S3 test runner for M1.46."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import re
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from queue import Empty
from typing import Any, Mapping

from .backends.x86_64 import (
    NativeBackendError,
    NativePlatformError,
    NativeToolchain,
    NativeToolchainError,
    generate_native_assembly,
)
from .emulator import DEFAULT_MAX_FRAMES, DEFAULT_MAX_INSTRUCTIONS, Emulator
from .ir_emulator import execute_ir
from .optimizer import OptimizationLevel
from .pipeline import compile_source, compile_sources


class TestRunnerError(ValueError):
    """Raised when a test manifest violates the runner contract."""

    __test__ = False


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_MODES = {"hosted", "native", "both"}
_STATUS_EXIT = {
    "PASS": 0,
    "SKIP": 0,
    "FAIL": 1,
    "TIMEOUT": 1,
    "CAPABILITY_DENIED": 1,
    "RESOURCE_LIMIT": 1,
    "INFRASTRUCTURE_FAILURE": 2,
}
_CAPABILITY_MARKERS = {
    "host_capability_grant": "resource",
    "resource_open": "resource",
    "resource_is_open": "resource",
    "resource_kind": "resource",
    "resource_invoke": "resource",
    "resource_close": "resource",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative_path(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise TestRunnerError(f"{field} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise TestRunnerError(f"{field} must stay inside the manifest directory")
    return "/".join(path.parts)


def _sorted_strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise TestRunnerError(f"{field} must be a list of non-empty strings")
    result = tuple(sorted(value))
    if len(set(result)) != len(result):
        raise TestRunnerError(f"{field} must not contain duplicates")
    return result


@dataclass(frozen=True, slots=True)
class S3TestCase:
    name: str
    sources: tuple[str, ...]
    expected: int
    entry: str = "main"
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            raise TestRunnerError(f"invalid test name {self.name!r}")
        if not self.sources:
            raise TestRunnerError(f"test {self.name!r} requires at least one source")
        if not isinstance(self.expected, int) or isinstance(self.expected, bool):
            raise TestRunnerError(f"test {self.name!r} expected must be an integer")
        if not isinstance(self.entry, str) or _NAME.fullmatch(self.entry) is None:
            raise TestRunnerError(f"invalid entry for test {self.name!r}")
        if tuple(sorted(set(self.capabilities))) != self.capabilities:
            raise TestRunnerError(f"test {self.name!r} capabilities must be sorted and unique")
        unknown = set(self.capabilities) - {"resource"}
        if unknown:
            raise TestRunnerError(f"unsupported capability {sorted(unknown)[0]!r}")


@dataclass(frozen=True, slots=True)
class S3TestManifest:
    path: Path
    manifest_sha256: str
    seed: int
    timeout_ms: int
    max_frames: int
    max_instructions: int
    optimization: str
    mode: str
    tests: tuple[S3TestCase, ...]

    @classmethod
    def load(cls, path: str | Path) -> S3TestManifest:
        manifest_path = Path(path).resolve()
        try:
            raw_bytes = manifest_path.read_bytes()
            data = tomllib.loads(raw_bytes.decode("utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
            raise TestRunnerError(f"cannot read test manifest {manifest_path}: {error}") from error
        runner = data.get("runner", {})
        if not isinstance(runner, Mapping):
            raise TestRunnerError("[runner] must be a table")
        seed = runner.get("seed", 0)
        timeout_ms = runner.get("timeout_ms", 10000)
        max_frames = runner.get("max_frames", DEFAULT_MAX_FRAMES)
        max_instructions = runner.get("max_instructions", DEFAULT_MAX_INSTRUCTIONS)
        for field, value in (
            ("seed", seed),
            ("timeout_ms", timeout_ms),
            ("max_frames", max_frames),
            ("max_instructions", max_instructions),
        ):
            minimum = 0 if field == "seed" else 1
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                qualifier = "non-negative" if field == "seed" else "positive"
                raise TestRunnerError(f"runner {field} must be a {qualifier} integer")
        if timeout_ms > 3_600_000:
            raise TestRunnerError("runner timeout_ms must not exceed 3600000")
        try:
            optimization = OptimizationLevel.parse(runner.get("optimization", "O0")).value
        except ValueError as error:
            raise TestRunnerError(f"unsupported optimization level: {error}") from error
        mode = runner.get("mode", "hosted")
        if mode not in _MODES:
            raise TestRunnerError(f"unsupported test runner mode {mode!r}")
        raw_tests = data.get("test", [])
        if not isinstance(raw_tests, list) or not raw_tests:
            raise TestRunnerError("test manifest requires at least one [[test]]")
        tests: list[S3TestCase] = []
        for raw in raw_tests:
            if not isinstance(raw, Mapping):
                raise TestRunnerError("each [[test]] must be a table")
            sources = raw.get("sources")
            if sources is None and "source" in raw:
                sources = [raw["source"]]
            normalized_sources = tuple(
                sorted(_relative_path(item, field="test source") for item in sources)
            ) if isinstance(sources, list) else (_relative_path(sources, field="test source"),)
            tests.append(
                S3TestCase(
                    raw.get("name"),
                    normalized_sources,
                    raw.get("expected"),
                    raw.get("entry", "main"),
                    _sorted_strings(raw.get("capabilities", []), field="test capabilities"),
                )
            )
        ordered = tuple(sorted(tests, key=lambda test: test.name))
        if len({test.name for test in ordered}) != len(ordered):
            raise TestRunnerError("test names must be unique")
        return cls(
            manifest_path,
            _sha256(raw_bytes),
            seed,
            timeout_ms,
            max_frames,
            max_instructions,
            optimization,
            mode,
            ordered,
        )


def _error_text(error: BaseException) -> str:
    message = str(error).strip().replace("\r", "").replace("\n", " ")
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def _outcome(status: str, **fields: object) -> dict[str, object]:
    if status not in _STATUS_EXIT:
        raise TestRunnerError(f"unsupported runner status {status!r}")
    result: dict[str, object] = {
        "status": status,
        "failure_class": None if status == "PASS" else status,
        "exit_status": _STATUS_EXIT[status],
        "stdout": "",
        "stderr": "",
        "capability_denials": [],
        "resource_failure": status in {"TIMEOUT", "RESOURCE_LIMIT"},
    }
    result.update(fields)
    return result


def _hosted_failure_status(error: BaseException) -> str:
    message = str(error).lower()
    if "frame limit" in message or "instruction limit" in message:
        return "RESOURCE_LIMIT"
    return "FAIL"


def _compile_test_sources(
    sources: dict[str, str],
    optimization: str,
    entry: str,
):
    if len(sources) == 1:
        return compile_source(next(iter(sources.values())), optimization)
    return compile_sources(sources, optimization, entry_module=entry)


def _hosted_worker(
    sources: dict[str, str],
    entry: str,
    optimization: str,
    max_frames: int,
    max_instructions: int,
    result_queue: Any,
) -> None:
    try:
        compilation = _compile_test_sources(sources, optimization, entry)
        if compilation.semantic_model.contains_references or compilation.semantic_model.contains_dynamic:
            value = execute_ir(compilation.ir, entry, optimization)
        else:
            value = Emulator(
                max_frames=max_frames,
                max_instructions=max_instructions,
            ).execute(compilation.assembly, entry)
        if not isinstance(value, int):
            raise TestRunnerError("test entry must return one integer result")
        result_queue.put(_outcome("PASS", value=value))
    except BaseException as error:
        result_queue.put(
            _outcome(
                _hosted_failure_status(error),
                error=_error_text(error),
            )
        )


class S3TestRunner:
    def __init__(self, manifest: S3TestManifest) -> None:
        self.manifest = manifest
        self.root = manifest.path.parent

    def _load_sources(self, case: S3TestCase) -> dict[str, str]:
        sources: dict[str, str] = {}
        for relative in case.sources:
            path = (self.root / relative).resolve()
            try:
                path.relative_to(self.root)
            except ValueError as error:
                raise TestRunnerError(f"test source escapes manifest directory: {relative}") from error
            if not path.is_file():
                raise TestRunnerError(f"missing test source: {relative}")
            sources[relative] = path.read_text(encoding="utf-8")
        return sources

    @staticmethod
    def _required_capabilities(sources: Mapping[str, str]) -> tuple[str, ...]:
        required: set[str] = set()
        combined = "\n".join(sources.values())
        for marker, capability in _CAPABILITY_MARKERS.items():
            if re.search(rf"\b{re.escape(marker)}\s*\(", combined):
                required.add(capability)
        return tuple(sorted(required))

    def _run_hosted(self, case: S3TestCase, sources: dict[str, str]) -> dict[str, object]:
        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue()
        process = context.Process(
            target=_hosted_worker,
            args=(
                sources,
                case.entry,
                self.manifest.optimization,
                self.manifest.max_frames,
                self.manifest.max_instructions,
                result_queue,
            ),
        )
        process.start()
        process.join(self.manifest.timeout_ms / 1000)
        if process.is_alive():
            process.terminate()
            process.join()
            return _outcome("TIMEOUT", error="timeout")
        try:
            result = result_queue.get(timeout=0.5)
        except Empty:
            return _outcome(
                "INFRASTRUCTURE_FAILURE",
                error=f"worker exited with status {process.exitcode}",
            )
        finally:
            result_queue.close()
        if result.get("status") != "PASS":
            return result
        value = result.get("value")
        if value != case.expected:
            return _outcome(
                "FAIL",
                error=f"expected {case.expected}, got {value}",
                value=value,
            )
        return _outcome("PASS", value=value)

    def _run_native(self, case: S3TestCase, sources: dict[str, str]) -> dict[str, object]:
        try:
            compilation = _compile_test_sources(sources, self.manifest.optimization, case.entry)
            native = generate_native_assembly(compilation.assembly)
            toolchain = NativeToolchain.detect()
        except NativePlatformError:
            return _outcome("SKIP", reason="native toolchain unavailable")
        except NativeToolchainError as error:
            return _outcome("INFRASTRUCTURE_FAILURE", error=_error_text(error))
        except NativeBackendError as error:
            return _outcome("FAIL", error=_error_text(error))
        except Exception as error:
            return _outcome("FAIL", error=_error_text(error))
        try:
            with tempfile.TemporaryDirectory(prefix="s3-test-native-") as temporary:
                executable = toolchain.build(native, Path(temporary) / "program")
                completed = toolchain.run(
                    executable,
                    timeout=self.manifest.timeout_ms / 1000,
                )
        except NativeToolchainError as error:
            status = "TIMEOUT" if "timed out" in str(error).lower() else "INFRASTRUCTURE_FAILURE"
            return _outcome(status, error=_error_text(error))
        if completed.returncode != 0:
            return _outcome("FAIL", error=f"native exit status {completed.returncode}")
        match = re.fullmatch(r"program returned: (-?\d+)", completed.stdout.strip())
        if match is None:
            return _outcome(
                "FAIL",
                error="native output did not match runner schema",
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        value = int(match.group(1))
        if value != case.expected:
            return _outcome(
                "FAIL",
                error=f"expected {case.expected}, got {value}",
                value=value,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return _outcome(
            "PASS",
            value=value,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def run(self, mode: str | None = None) -> dict[str, object]:
        selected_mode = mode or self.manifest.mode
        if selected_mode not in _MODES:
            raise TestRunnerError(f"unsupported test runner mode {selected_mode!r}")
        reports: list[dict[str, object]] = []
        for case in self.manifest.tests:
            sources = self._load_sources(case)
            required = self._required_capabilities(sources)
            missing = tuple(sorted(set(required) - set(case.capabilities)))
            started_ns = time.monotonic_ns()
            case_report: dict[str, object] = {
                "name": case.name,
                "test_id": case.name,
                "discovery_index": len(reports),
                "sources": list(case.sources),
                "entry": case.entry,
                "expected": case.expected,
                "capabilities": list(case.capabilities),
            }
            if missing:
                failure = _outcome(
                    "CAPABILITY_DENIED",
                    error=f"undeclared capability: {missing[0]}",
                    capability_denials=list(missing),
                )
                if selected_mode in {"hosted", "both"}:
                    case_report["hosted"] = failure
                if selected_mode in {"native", "both"}:
                    case_report["native"] = failure
            else:
                if selected_mode in {"hosted", "both"}:
                    case_report["hosted"] = self._run_hosted(case, sources)
                if selected_mode in {"native", "both"}:
                    case_report["native"] = self._run_native(case, sources)
            outcomes = [
                value["status"]
                for key, value in case_report.items()
                if key in {"hosted", "native"}
            ]
            failure_order = (
                "INFRASTRUCTURE_FAILURE",
                "TIMEOUT",
                "RESOURCE_LIMIT",
                "CAPABILITY_DENIED",
                "FAIL",
            )
            case_report["status"] = next(
                (status for status in failure_order if status in outcomes),
                "SKIP" if "SKIP" in outcomes else "PASS",
            )
            case_report["failure_class"] = (
                None if case_report["status"] == "PASS" else case_report["status"]
            )
            case_report["exit_status"] = _STATUS_EXIT[case_report["status"]]
            case_report["duration_ms"] = (time.monotonic_ns() - started_ns) // 1_000_000
            case_report["stdout"] = ""
            case_report["stderr"] = ""
            case_report["capability_denials"] = list(missing)
            case_report["resource_failure"] = case_report["status"] in {"TIMEOUT", "RESOURCE_LIMIT"}
            reports.append(case_report)
        counts = {status: sum(report["status"] == status for report in reports) for status in ("PASS", "FAIL", "SKIP")}
        for status in _STATUS_EXIT:
            counts.setdefault(status, sum(report["status"] == status for report in reports))
        overall = next(
            (
                status
                for status in (
                    "INFRASTRUCTURE_FAILURE",
                    "TIMEOUT",
                    "RESOURCE_LIMIT",
                    "CAPABILITY_DENIED",
                    "FAIL",
                    "SKIP",
                    "PASS",
                )
                if counts[status]
            ),
            "PASS",
        )
        return {
            "schema": "s3-test-report",
            "schema_version": "s3.test-report.v1",
            "project": self.root.name,
            "target": "linux-x86_64",
            "profile": self.manifest.optimization,
            "manifest_sha256": self.manifest.manifest_sha256,
            "seed": self.manifest.seed,
            "timeout_ms": self.manifest.timeout_ms,
            "max_frames": self.manifest.max_frames,
            "max_instructions": self.manifest.max_instructions,
            "optimization": self.manifest.optimization,
            "mode": selected_mode,
            "tests": reports,
            "summary": {
                "status": overall,
                "passed": counts["PASS"],
                "failed": counts["FAIL"],
                "skipped": counts["SKIP"],
                "timed_out": counts["TIMEOUT"],
                "capability_denied": counts["CAPABILITY_DENIED"],
                "resource_limited": counts["RESOURCE_LIMIT"],
                "infrastructure_failed": counts["INFRASTRUCTURE_FAILURE"],
            },
        }


def render_test_report(report: Mapping[str, object]) -> str:
    return json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def run_test_manifest(path: str | Path, *, mode: str | None = None) -> dict[str, object]:
    return S3TestRunner(S3TestManifest.load(path)).run(mode)
