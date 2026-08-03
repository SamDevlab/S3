"""Concrete S3, reference, and external-toolchain benchmark adapters."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from bootstrap.s3.backends._hosted_execution import _execute_hosted_assembly
from bootstrap.s3.backends.x86_64.backend import generate_native_assembly
from bootstrap.s3.backends.x86_64.toolchain import NativeToolchain
from bootstrap.s3.pipeline import compile_source

from .core import (
    Adapter,
    AdapterUnavailable,
    BenchmarkError,
    BuildArtifact,
    Case,
    ExecutionObservation,
    extract_checksum,
    run_command,
)


@dataclass(frozen=True, slots=True)
class Toolchain:
    name: str
    command: str | None
    version: str | None
    available: bool
    detection_command: tuple[str, ...]


def detect_toolchains() -> dict[str, Toolchain]:
    specifications = {
        "clang": ("clang", ("--version",)),
        "gcc": ("gcc", ("--version",)),
        "rustc": ("rustc", ("--version",)),
        "cargo": ("cargo", ("--version",)),
        "zig": ("zig", ("version",)),
        "linker": ("ld", ("--version",)),
        "wsl": ("wsl", ("--status",)),
    }
    detected: dict[str, Toolchain] = {}
    for name, (command_name, version_arguments) in specifications.items():
        command = shutil.which(command_name)
        detection = (command_name, *version_arguments)
        version = _tool_version([command, *version_arguments]) if command else None
        detected[name] = Toolchain(name, command, version, command is not None, detection)
    return detected


def _tool_version(arguments: Sequence[str | None]) -> str | None:
    if not arguments or arguments[0] is None:
        return None
    try:
        completed = subprocess.run(
            [str(value) for value in arguments],
            capture_output=True,
            text=True,
            shell=False,
            timeout=10.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip() or completed.stderr.strip()
    return output.splitlines()[0] if output else None


class S3EmulatorAdapter:
    def build(self, case: Case, build_dir: Path) -> BuildArtifact:
        if case.source is None:
            raise BenchmarkError("S3 emulator case has no source")
        source = case.source.read_text(encoding="utf-8")
        started = time.perf_counter_ns()
        compilation = compile_source(source, case.optimization_mode)
        duration = time.perf_counter_ns() - started
        assembly_size = len(compilation.assembly_text.encode("utf-8"))
        return BuildArtifact(
            compile_duration_ns=duration,
            artifact_size_bytes=assembly_size,
            compiler_name="s3-bootstrap-python",
            compiler_version=None,
            compiler_flags=(case.optimization_mode,),
            payload=compilation,
            notes=("in-process compile; link phase is not applicable",),
        )

    def execute(
        self,
        case: Case,
        artifact: BuildArtifact,
        loops: int,
        timeout_seconds: float,
    ) -> ExecutionObservation:
        del timeout_seconds
        compilation = artifact.payload
        if compilation is None or not hasattr(compilation, "assembly"):
            raise BenchmarkError("S3 emulator artifact is invalid")
        started = time.perf_counter_ns()
        result = 0
        for _ in range(loops):
            result = _execute_hosted_assembly(compilation.assembly, "main")
        duration = time.perf_counter_ns() - started
        return ExecutionObservation(
            checksum=str(result),
            duration_ns=duration,
            kernel_duration_ns=duration,
            end_to_end_duration_ns=duration,
        )


class S3NativeAdapter:
    def build(self, case: Case, build_dir: Path) -> BuildArtifact:
        if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
            raise AdapterUnavailable("S3 native execution requires Linux x86-64")
        if case.source is None:
            raise BenchmarkError("S3 native case has no source")
        build_dir.mkdir(parents=True, exist_ok=True)
        source = case.source.read_text(encoding="utf-8")
        compile_started = time.perf_counter_ns()
        compilation = compile_source(source, case.optimization_mode)
        native_assembly = generate_native_assembly(compilation.assembly)
        compile_duration = time.perf_counter_ns() - compile_started
        toolchain = NativeToolchain.detect()
        executable = build_dir / _artifact_name(case, "s3-native")
        link_started = time.perf_counter_ns()
        toolchain.build(native_assembly, executable)
        link_duration = time.perf_counter_ns() - link_started
        return BuildArtifact(
            path=executable,
            compile_duration_ns=compile_duration,
            link_duration_ns=link_duration,
            artifact_size_bytes=executable.stat().st_size,
            compiler_name=Path(toolchain.compiler).name,
            compiler_version=_tool_version((toolchain.compiler, "--version")),
            compiler_flags=(case.optimization_mode,),
            linker=toolchain.linker,
        )

    def execute(
        self,
        case: Case,
        artifact: BuildArtifact,
        loops: int,
        timeout_seconds: float,
    ) -> ExecutionObservation:
        if artifact.path is None:
            raise BenchmarkError("S3 native artifact has no executable")
        started = time.perf_counter_ns()
        last_exit = 0
        for _ in range(loops):
            result = run_command(
                [os.fspath(artifact.path)],
                cwd=artifact.path.parent,
                timeout_seconds=timeout_seconds,
            )
            if result.timed_out or result.exit_code is None:
                return _observation_from_command(result, checksum=None)
            last_exit = result.exit_code
        duration = time.perf_counter_ns() - started
        return ExecutionObservation(
            checksum=str(last_exit),
            duration_ns=duration,
            exit_code=0,
            startup_duration_ns=None,
            kernel_duration_ns=None,
            end_to_end_duration_ns=duration,
        )


class PythonReferenceAdapter:
    def build(self, case: Case, build_dir: Path) -> BuildArtifact:
        del build_dir
        if case.source is None:
            raise BenchmarkError("Python reference case has no source")
        return BuildArtifact(
            path=case.source,
            artifact_size_bytes=case.source.stat().st_size,
            compiler_name="CPython",
            compiler_version=platform.python_version(),
            notes=("interpreted reference; compile and link phases are unavailable",),
        )

    def execute(
        self,
        case: Case,
        artifact: BuildArtifact,
        loops: int,
        timeout_seconds: float,
    ) -> ExecutionObservation:
        if artifact.path is None:
            raise BenchmarkError("Python reference artifact has no source")
        arguments = [sys.executable, os.fspath(artifact.path), case.benchmark_id, str(loops)]
        result = run_command(arguments, cwd=artifact.path.parent, timeout_seconds=timeout_seconds)
        checksum = None if result.timed_out or result.output_truncated else extract_checksum(result.stdout)
        return _observation_from_command(result, checksum=checksum)


class ExternalCompilerAdapter:
    def __init__(self, language: str, toolchain: Toolchain) -> None:
        self._language = language
        self._toolchain = toolchain

    def build(self, case: Case, build_dir: Path) -> BuildArtifact:
        if not self._toolchain.available or self._toolchain.command is None:
            raise AdapterUnavailable(f"{self._language} toolchain is unavailable")
        if case.source is None:
            raise BenchmarkError(f"{self._language} case has no source")
        build_dir.mkdir(parents=True, exist_ok=True)
        executable = build_dir / _artifact_name(case, self._language)
        if os.name == "nt":
            executable = executable.with_suffix(".exe")
        flags = _compiler_flags(case, self._language)
        if self._language == "c":
            object_path = executable.with_suffix(".o")
            compile_result = run_command(
                [self._toolchain.command, *flags, "-c", os.fspath(case.source), "-o", os.fspath(object_path)],
                cwd=build_dir,
                timeout_seconds=case.timeout_seconds,
            )
            _require_command_success(compile_result, "C compile")
            link_result = run_command(
                [self._toolchain.command, os.fspath(object_path), "-o", os.fspath(executable)],
                cwd=build_dir,
                timeout_seconds=case.timeout_seconds,
            )
            _require_command_success(link_result, "C link")
            compile_duration = compile_result.duration_ns
            link_duration = link_result.duration_ns
        elif self._language == "rust":
            compile_result = run_command(
                [self._toolchain.command, *flags, os.fspath(case.source), "-o", os.fspath(executable)],
                cwd=build_dir,
                timeout_seconds=case.timeout_seconds,
            )
            _require_command_success(compile_result, "Rust build")
            compile_duration = compile_result.duration_ns
            link_duration = None
        elif self._language == "zig":
            compile_result = run_command(
                [self._toolchain.command, "build-exe", os.fspath(case.source), *flags, f"-femit-bin={executable}"],
                cwd=build_dir,
                timeout_seconds=case.timeout_seconds,
            )
            _require_command_success(compile_result, "Zig build")
            compile_duration = compile_result.duration_ns
            link_duration = None
        else:
            raise BenchmarkError(f"unsupported external language: {self._language}")
        if not executable.is_file():
            raise BenchmarkError(f"{self._language} build produced no executable")
        return BuildArtifact(
            path=executable,
            compile_duration_ns=compile_duration,
            link_duration_ns=link_duration,
            artifact_size_bytes=executable.stat().st_size,
            compiler_name=self._toolchain.name,
            compiler_version=self._toolchain.version,
            compiler_flags=tuple(flags),
            linker=self._toolchain.name if self._language == "c" else None,
            notes=("compiler driver includes link phase",) if link_duration is None else (),
        )

    def execute(
        self,
        case: Case,
        artifact: BuildArtifact,
        loops: int,
        timeout_seconds: float,
    ) -> ExecutionObservation:
        if artifact.path is None:
            raise BenchmarkError(f"{self._language} artifact has no executable")
        result = run_command(
            [os.fspath(artifact.path), case.benchmark_id, str(loops)],
            cwd=artifact.path.parent,
            timeout_seconds=timeout_seconds,
        )
        checksum = None if result.timed_out or result.output_truncated else extract_checksum(result.stdout)
        return _observation_from_command(result, checksum=checksum)


def create_adapter_registry(toolchains: Mapping[str, Toolchain] | None = None) -> dict[str, Adapter]:
    tools = dict(toolchains or detect_toolchains())
    c_toolchain = tools["clang"] if tools["clang"].available else tools["gcc"]
    return {
        "s3-emulator": S3EmulatorAdapter(),
        "s3-native": S3NativeAdapter(),
        "python-reference": PythonReferenceAdapter(),
        "c": ExternalCompilerAdapter("c", c_toolchain),
        "rust": ExternalCompilerAdapter("rust", tools["rustc"]),
        "zig": ExternalCompilerAdapter("zig", tools["zig"]),
    }


def _compiler_flags(case: Case, language: str) -> list[str]:
    configured = case.configuration.get("compiler_flags", {})
    if not isinstance(configured, Mapping):
        raise BenchmarkError("compiler_flags must be an optimization mapping")
    flags = configured.get(case.optimization_mode)
    if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
        raise BenchmarkError(
            f"missing compiler flags for {language} {case.optimization_mode}"
        )
    return list(flags)


def _require_command_success(result, phase: str) -> None:
    if result.timed_out:
        raise BenchmarkError(f"{phase} timed out")
    if result.output_truncated:
        raise BenchmarkError(f"{phase} output was truncated")
    if result.exit_code != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise BenchmarkError(f"{phase} failed with status {result.exit_code}: {details}")


def _observation_from_command(result, *, checksum: str | None) -> ExecutionObservation:
    return ExecutionObservation(
        checksum=checksum,
        duration_ns=result.duration_ns,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        output_truncated=result.output_truncated,
        end_to_end_duration_ns=result.duration_ns,
    )


def _artifact_name(case: Case, prefix: str) -> str:
    safe_id = case.benchmark_id.replace(".", "-")
    safe_opt = case.optimization_mode.replace("=", "-")
    return f"{prefix}-{safe_id}-{safe_opt}"
