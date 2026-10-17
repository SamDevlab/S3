"""Characterize equivalent Python and native S3C-NG provider workloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from bootstrap.s3.assembly_fingerprint import assembly_program_sha256
from bootstrap.s3.compiler_provider import CompilerKind, compile_source_set_with_provider
from bootstrap.s3.native_compiler import require_s3c_ng_executable
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.ir_serialization import serialize_ir
from tests.test_language_maturity_workloads import (
    _generated_pebble_cases,
    _ordering_program,
    _pebble_program,
)
from tools.native_s3c_ng import compiler_source_set


@dataclass(frozen=True, slots=True)
class Workload:
    name: str
    sources: dict[str, str]
    entry_module: str


def _workloads(repository: Path) -> tuple[Workload, ...]:
    return (
        Workload(
            "small",
            {
                "app.s3": (
                    "module app\n"
                    "fn answer(value: i64) -> i64:\n"
                    "    return value\n"
                    "fn main() -> i64:\n"
                    "    return answer(42)\n"
                )
            },
            "app",
        ),
        Workload(
            "multimodule-ordering-search",
            _ordering_program((29, -4, 8, 8, 17, 0), (-4, 8, 17, 30)),
            "main",
        ),
        Workload(
            "real-pebble-workload",
            {"main.s3": _pebble_program(_generated_pebble_cases(count=12))},
            "main",
        ),
        Workload(
            "self-source",
            compiler_source_set(repository),
            "app",
        ),
    )


def _compile_and_hash(
    sources: dict[str, str],
    *,
    provider: CompilerKind,
    executable: Path,
    entry_module: str,
) -> tuple[int, str, str]:
    started = time.perf_counter_ns()
    output = compile_source_set_with_provider(
        sources,
        OptimizationLevel.O0,
        compiler=provider,
        executable=executable if provider is CompilerKind.S3C_NG else None,
        entry_module=entry_module,
    )
    elapsed = time.perf_counter_ns() - started
    ir, assembly = output.require_ordinary_artifacts()
    ir_hash = hashlib.sha256(serialize_ir(ir).encode("utf-8")).hexdigest()
    assembly_hash = assembly_program_sha256(assembly)
    return elapsed, ir_hash, assembly_hash


def _measure_workload(workload: Workload, executable: Path, runs: int) -> dict[str, object]:
    providers = (CompilerKind.PYTHON, CompilerKind.S3C_NG)
    expected: tuple[str, str] | None = None
    for provider in providers:
        _, ir_hash, assembly_hash = _compile_and_hash(
            workload.sources,
            provider=provider,
            executable=executable,
            entry_module=workload.entry_module,
        )
        identity = (ir_hash, assembly_hash)
        if expected is None:
            expected = identity
        elif identity != expected:
            raise RuntimeError(f"{workload.name}: compiler providers emitted different IR or Assembly")

    samples: dict[CompilerKind, list[int]] = {provider: [] for provider in providers}
    for index in range(runs):
        order = providers if index % 2 == 0 else tuple(reversed(providers))
        for provider in order:
            elapsed, ir_hash, assembly_hash = _compile_and_hash(
                workload.sources,
                provider=provider,
                executable=executable,
                entry_module=workload.entry_module,
            )
            if (ir_hash, assembly_hash) != expected:
                raise RuntimeError(f"{workload.name}: output changed during timing")
            samples[provider].append(elapsed)

    python_median = statistics.median(samples[CompilerKind.PYTHON]) / 1_000_000
    native_median = statistics.median(samples[CompilerKind.S3C_NG]) / 1_000_000
    return {
        "name": workload.name,
        "source_units": len(workload.sources),
        "source_bytes": sum(len(source.encode("utf-8")) for source in workload.sources.values()),
        "ir_sha256": expected[0],
        "assembly_sha256": expected[1],
        "python_samples_ms": [round(value / 1_000_000, 3) for value in samples[CompilerKind.PYTHON]],
        "s3c_ng_samples_ms": [round(value / 1_000_000, 3) for value in samples[CompilerKind.S3C_NG]],
        "python_median_ms": round(python_median, 3),
        "s3c_ng_median_ms": round(native_median, 3),
        "s3c_ng_to_python_ratio": round(native_median / python_median, 3) if python_median else None,
    }


def _measure_cli_startup(executable: Path, runs: int) -> dict[str, object]:
    source = (
        "fn answer(value: i64) -> i64:\n"
        "    return value\n"
        "fn main() -> i64:\n"
        "    return answer(42)\n"
    )
    providers = (CompilerKind.PYTHON, CompilerKind.S3C_NG)
    samples: dict[CompilerKind, list[int]] = {provider: [] for provider in providers}
    with tempfile.TemporaryDirectory(prefix="s3c-ng-perf-") as temporary:
        source_path = Path(temporary) / "app.s3"
        source_path.write_text(source, encoding="utf-8", newline="\n")
        for index in range(runs + 1):
            order = providers if index % 2 == 0 else tuple(reversed(providers))
            for provider in order:
                command = [
                    sys.executable,
                    "-m",
                    "bootstrap.s3.cli",
                    "check",
                    str(source_path),
                    "--compiler",
                    provider.value,
                ]
                if provider is CompilerKind.S3C_NG:
                    command.extend(("--s3c-ng-executable", str(executable)))
                started = time.perf_counter_ns()
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                elapsed = time.perf_counter_ns() - started
                if result.returncode != 0:
                    raise RuntimeError(
                        f"{provider.value} CLI check failed: {result.stderr.strip()}"
                    )
                if index > 0:
                    samples[provider].append(elapsed)

    python_median = statistics.median(samples[CompilerKind.PYTHON]) / 1_000_000
    native_median = statistics.median(samples[CompilerKind.S3C_NG]) / 1_000_000
    return {
        "name": "small-check-cli-startup-included",
        "runs": runs,
        "python_samples_ms": [round(value / 1_000_000, 3) for value in samples[CompilerKind.PYTHON]],
        "s3c_ng_samples_ms": [round(value / 1_000_000, 3) for value in samples[CompilerKind.S3C_NG]],
        "python_median_ms": round(python_median, 3),
        "s3c_ng_median_ms": round(native_median, 3),
        "s3c_ng_to_python_ratio": round(native_median / python_median, 3) if python_median else None,
    }


def _append_summary(report: dict[str, object]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "## S3C-NG provider performance characterization",
        "",
        "Characterization only; no fixed speedup threshold. Matching canonical IR and Assembly were required.",
        "",
        "| Workload | Python median (ms) | S3C-NG median (ms) | S3C-NG / Python |",
        "| --- | ---: | ---: | ---: |",
    ]
    rows = [*report["workloads"], report["cli_startup"]]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['python_median_ms']} | "
            f"{row['s3c_ng_median_ms']} | {row['s3c_ng_to_python_ratio']} |"
        )
    with Path(summary_path).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--executable",
        type=Path,
        default=os.environ.get("S3C_NG_BOOTSTRAP_EXECUTABLE"),
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        parser.error("provider characterization requires Linux x86-64")
    if args.executable is None or args.runs < 3:
        parser.error("provide --executable and at least three paired runs")

    executable = args.executable.expanduser().resolve()
    require_s3c_ng_executable(executable)
    manifest_path = executable.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    repository = Path(__file__).resolve().parents[1]
    import resource

    workloads = [
        _measure_workload(workload, executable, args.runs)
        for workload in _workloads(repository)
    ]
    cli_startup = _measure_cli_startup(executable, args.runs)
    report: dict[str, object] = {
        "schema": "s3c-ng-provider-performance-v1",
        "classification": "CHARACTERIZATION_ONLY",
        "threshold_policy": "NO_FIXED_SPEEDUP_THRESHOLD; review pathological slowdown, memory explosion, or unusable startup",
        "runs_per_provider": args.runs,
        "warmups_per_provider": 1,
        "optimization": "O0",
        "measurement_scope": "provider wall time includes source compilation, native process startup where applicable, transport, decode, verification, shared optimization, and Assembly generation; excludes native toolchain build/link",
        "target": manifest.get("target"),
        "artifact_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "source_commit": manifest.get("source_commit"),
        "source_graph_sha256": manifest.get("source_graph_sha256"),
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "max_child_peak_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "rss_scope": "process and maximum observed child peak across the complete characterization; not attributed per provider",
        "workloads": workloads,
        "cli_startup": cli_startup,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    _append_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
