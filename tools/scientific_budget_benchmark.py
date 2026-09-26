"""Characterize native scientific kernels under both instruction budgets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bootstrap.s3.backends.x86_64 import (  # noqa: E402
    InstructionBudgetMode,
    NativeToolchain,
    X8664Backend,
)
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_sources  # noqa: E402
from bootstrap.s3.stdlib import standard_library_sources  # noqa: E402
from tools.benchmark_native_kernel_scope import classify_paired_speedup  # noqa: E402


VECTOR_LENGTH = 64
DEFAULT_REPEATS = 500
DEFAULT_WARMUPS = 2
DEFAULT_RUNS = 9
MAX_INSTRUCTIONS = 100_000_000


def _canonical_assembly_value(value: object) -> object:
    if isinstance(value, Enum):
        return {"enum": type(value).__qualname__, "value": value.value}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical_assembly_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, float):
        return {"float_hex": value.hex()}
    if isinstance(value, (tuple, list)):
        return [_canonical_assembly_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _canonical_assembly_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if value is None or type(value) in {bool, int, str}:
        return value
    raise TypeError(
        "unsupported AssemblyProgram fingerprint value: "
        f"{type(value)!r}"
    )


def _assembly_program_sha256(program: object) -> str:
    payload = json.dumps(
        _canonical_assembly_value(program),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _workload_source(kernel: str, repeats: int) -> tuple[str, float]:
    if kernel == "dot":
        expression = "dot(&left, &right).value"
        expected_per_call = 87_360.0
        imported = "from s3.v1.science import dot\n"
    elif kernel == "variance":
        expression = "variance(&left)"
        expected_per_call = 341.25
        imported = "from s3.v1.science import variance\n"
    elif kernel == "rmsd":
        expression = "rmsd(&left, &right).value"
        expected_per_call = 1.0
        imported = "from s3.v1.science import rmsd\n"
    else:
        raise ValueError(f"unsupported benchmark kernel: {kernel}")

    expected_total = expected_per_call * repeats
    source = (
        "module main\n"
        + imported
        + "fn main() -> i64:\n"
        + f"    mut left: f64_vector = f64_vector_new({VECTOR_LENGTH})\n"
        + f"    mut right: f64_vector = f64_vector_new({VECTOR_LENGTH})\n"
        + "    mut index: i64 = 0\n"
        + f"    while index < {VECTOR_LENGTH}:\n"
        + "        mut left_value: f64 = to_f64(index + 1)\n"
        + "        mut right_value: f64 = to_f64(index)\n"
        + "        discard f64_vector_push(&mut left, left_value)\n"
        + "        discard f64_vector_push(&mut right, right_value)\n"
        + "        index = index + 1\n"
        + "    mut iteration: i64 = 0\n"
        + "    mut total: f64 = 0.0\n"
        + f"    while iteration < {repeats}:\n"
        + f"        total = total + {expression}\n"
        + "        iteration = iteration + 1\n"
        + f"    match total == {expected_total!r}:\n"
        + "        -1:\n"
        + "            return 0\n"
        + "        0:\n"
        + "            return 1\n"
        + "        1:\n"
        + "            return 1\n"
    )
    return source, expected_total


def _section_sizes(executable: Path) -> dict[str, int]:
    size = subprocess.run(
        ["size", "-A", str(executable)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    sections: dict[str, int] = {}
    for line in size.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0].startswith("."):
            try:
                sections[fields[0]] = int(fields[1])
            except ValueError:
                continue
    if ".text" not in sections:
        raise RuntimeError(f"could not find .text section in {executable}")
    return sections


def _assert_frozen_source(source_head: str) -> None:
    actual_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    if actual_head != source_head:
        raise RuntimeError(
            f"source_head mismatch: requested {source_head}, actual {actual_head}"
        )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout
    if status:
        raise RuntimeError("native budget benchmark requires a clean frozen source tree")


def _run_once(toolchain: NativeToolchain, executable: Path) -> int:
    started = time.perf_counter_ns()
    completed = toolchain.run(executable, timeout=120.0)
    elapsed = time.perf_counter_ns() - started
    if completed.returncode != 0 or completed.stdout != "program returned: 0\n":
        raise RuntimeError(
            f"native correctness check failed for {executable}: "
            f"exit={completed.returncode}, stdout={completed.stdout!r}, "
            f"stderr={completed.stderr!r}"
        )
    return elapsed


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unavailable"


def run_benchmark(
    *,
    output: Path,
    source_head: str,
    repeats: int,
    warmups: int,
    runs: int,
) -> dict[str, object]:
    valid_sha = len(source_head) == 40 and all(
        character in "0123456789abcdef" for character in source_head.lower()
    )
    if not valid_sha:
        raise ValueError("source_head must be a full 40-character Git commit SHA")
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("native scientific benchmark requires Linux x86-64")
    if repeats < 1 or warmups < 0 or runs < 3:
        raise ValueError("repeats must be positive, warmups nonnegative, and runs >= 3")

    _assert_frozen_source(source_head)
    output.mkdir(parents=True, exist_ok=True)
    toolchain = NativeToolchain.detect()
    compiler_version = subprocess.run(
        [toolchain.compiler, "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.splitlines()[0]
    results: dict[str, object] = {
        "protocol": "same O1 AssemblyProgram; only instruction_budget_mode varies",
        "source_head": source_head,
        "source_tree_clean_at_start": True,
        "timing_scope": (
            "external wall-clock around one native process; each process executes "
            "repeated kernel calls"
        ),
        "optimization": "O1",
        "vector_length": VECTOR_LENGTH,
        "kernel_repeats_per_process": repeats,
        "warmups_per_mode_kernel": warmups,
        "paired_samples_per_mode_kernel": runs,
        "max_instructions": MAX_INSTRUCTIONS,
        "os": platform.platform(),
        "architecture": platform.machine(),
        "cpu_model": _cpu_model(),
        "python": platform.python_version(),
        "compiler": toolchain.compiler,
        "compiler_version": compiler_version,
        "kernels": {},
    }

    modes = (
        InstructionBudgetMode.PER_INSTRUCTION,
        InstructionBudgetMode.EXACT_SEGMENT,
        InstructionBudgetMode.LOOP_HYBRID,
    )
    for kernel in ("rmsd", "dot", "variance"):
        source, expected_total = _workload_source(kernel, repeats)
        sources = standard_library_sources(modules=("s3.v1.science",))
        sources["main.s3"] = source
        compilation = compile_sources(sources, optimization=OptimizationLevel.O1)
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        assembly_hash = _assembly_program_sha256(compilation.assembly)
        artifacts: dict[InstructionBudgetMode, Path] = {}
        mode_metadata: dict[str, dict[str, object]] = {}

        for mode in modes:
            mode_dir = output / kernel / mode.value
            mode_dir.mkdir(parents=True, exist_ok=True)
            executable = mode_dir / "kernel"
            native_assembly = X8664Backend(
                max_instructions=MAX_INSTRUCTIONS,
                instruction_budget_mode=mode,
            ).generate(compilation.assembly)
            toolchain.build(
                native_assembly,
                executable,
                keep_assembly=mode_dir / "kernel.s",
            )
            artifacts[mode] = executable
            sections = _section_sizes(executable)
            mode_metadata[mode.value] = {
                "native_assembly_sha256": hashlib.sha256(
                    native_assembly.encode("utf-8")
                ).hexdigest(),
                "native_assembly_bytes": len(native_assembly.encode("utf-8")),
                "elf_bytes": executable.stat().st_size,
                "text_bytes": sections[".text"],
                "rodata_bytes": sections.get(".rodata", 0),
                "other_section_bytes": sum(
                    value
                    for name, value in sections.items()
                    if name not in {".text", ".rodata"}
                ),
                "section_bytes": sections,
                "samples_ns": [],
            }
            _run_once(toolchain, executable)

        for _ in range(warmups):
            for mode in modes:
                _run_once(toolchain, artifacts[mode])

        for sample_index in range(runs):
            rotation = sample_index % len(modes)
            order = modes[rotation:] + modes[:rotation]
            for mode in order:
                elapsed = _run_once(toolchain, artifacts[mode])
                mode_metadata[mode.value]["samples_ns"].append(elapsed)

        per_samples = mode_metadata[InstructionBudgetMode.PER_INSTRUCTION.value]["samples_ns"]
        for sample_values in (
            mode_metadata[mode.value]["samples_ns"] for mode in modes
        ):
            ordered = sorted(sample_values)
            mean = statistics.fmean(ordered)
            sample_values_summary = {
                "median_ns": statistics.median(ordered),
                "minimum_ns": ordered[0],
                "maximum_ns": ordered[-1],
                "p95_ns": ordered[math.ceil(0.95 * len(ordered)) - 1],
                "coefficient_of_variation": (
                    statistics.stdev(ordered) / mean if mean else 0.0
                ),
            }
            key = next(
                mode.value
                for mode in modes
                if mode_metadata[mode.value]["samples_ns"] is sample_values
            )
            mode_metadata[key].update(sample_values_summary)

        per_text = int(mode_metadata[InstructionBudgetMode.PER_INSTRUCTION.value]["text_bytes"])
        exact_text = int(mode_metadata[InstructionBudgetMode.EXACT_SEGMENT.value]["text_bytes"])
        hybrid_text = int(mode_metadata[InstructionBudgetMode.LOOP_HYBRID.value]["text_bytes"])
        exact_samples = mode_metadata[InstructionBudgetMode.EXACT_SEGMENT.value]["samples_ns"]
        hybrid_samples = mode_metadata[InstructionBudgetMode.LOOP_HYBRID.value]["samples_ns"]
        kernel_result = {
            "source_sha256": source_hash,
            "assembly_program_sha256": assembly_hash,
            "expected_accumulated_result": expected_total,
            "correctness_both_modes": True,
            "modes": mode_metadata,
            "median_paired_speedup_exact_over_per": statistics.median(
                per / exact
                for per, exact in zip(per_samples, exact_samples, strict=True)
            ),
            "exact_vs_per_performance": classify_paired_speedup(
                per_samples, exact_samples
            ),
            "text_delta_exact_minus_per_bytes": exact_text - per_text,
            "text_delta_exact_minus_per_percent": (
                (exact_text - per_text) * 100.0 / per_text if per_text else None
            ),
            "median_paired_speedup_hybrid_over_per": statistics.median(
                per / hybrid
                for per, hybrid in zip(per_samples, hybrid_samples, strict=True)
            ),
            "hybrid_vs_per_performance": classify_paired_speedup(
                per_samples, hybrid_samples
            ),
            "text_delta_hybrid_minus_per_bytes": hybrid_text - per_text,
            "text_delta_hybrid_minus_per_percent": (
                (hybrid_text - per_text) * 100.0 / per_text if per_text else None
            ),
        }
        results["kernels"][kernel] = kernel_result

    encoded = json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output_file = output / "scientific-budget-benchmark.json"
    output_file.write_text(encoded, encoding="utf-8", newline="\n")
    return {"output": str(output_file), **results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    arguments = parser.parse_args()
    result = run_benchmark(
        output=arguments.output,
        source_head=arguments.source_head,
        repeats=arguments.repeats,
        warmups=arguments.warmups,
        runs=arguments.runs,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
