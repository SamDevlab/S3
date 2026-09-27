"""Experimental logical block profiling for pinned S3 native workloads.

The probe instruments generated native block entries with a balanced
pushfq/inc/popfq sequence. It reports logical block visits and a static-native
structural weight; it is not a retired-instruction, timing, or PMU profiler.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64.emitter import X8664Emitter, mangle_block
from bootstrap.s3.backends.x86_64.instruction_budget import InstructionBudgetMode
from bootstrap.s3.backends.x86_64.native_policy import NativeCodegenPolicy
from bootstrap.s3.codegen_report import build_codegen_report
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_ffi_assembly

from tools import s3_15_native_workload_benchmark as benchmark

MAX_FRAMES = 1024
MAX_INSTRUCTIONS = 1_000_000_000
SCHEMA_VERSION = "1.0.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def instrument_block_entries(
    assembly: str, labels: list[str]
) -> tuple[str, dict[str, str]]:
    """Add one flag-preserving counter at each requested block label."""
    if not isinstance(assembly, str) or not isinstance(labels, list):
        raise TypeError("assembly must be text and labels must be a list")
    if len(set(labels)) != len(labels) or any(not label.startswith(".L_s3_") for label in labels):
        raise ValueError("block labels must be unique S3 local labels")

    counters = {label: f".L__s3_profile_count_{index:04d}" for index, label in enumerate(labels)}
    readers = {label: f"__s3_profile_read_{index:04d}" for index, label in enumerate(labels)}
    pending = set(labels)
    output: list[str] = []
    for line in assembly.splitlines():
        output.append(line)
        label = line.strip()[:-1] if line.strip().endswith(":") else None
        if label not in counters:
            continue
        output.extend(
            (
                "    pushfq",
                f"    inc qword ptr [rip + {counters[label]}]",
                "    popfq",
            )
        )
        pending.discard(label)
    if pending:
        raise ValueError(f"requested block labels are absent: {sorted(pending)}")

    output.extend(("", ".section .bss", ".p2align 3"))
    for symbol in counters.values():
        output.extend(
            (
                f".local {symbol}",
                f".type {symbol}, @object",
                f".size {symbol}, 8",
                f"{symbol}:",
                "    .zero 8",
            )
        )
    output.append(".section .text")
    for counter, reader in zip(counters.values(), readers.values(), strict=True):
        output.extend(
            (
                f".globl {reader}",
                f".type {reader}, @function",
                f"{reader}:",
                f"    mov rax, qword ptr [rip + {counter}]",
                "    ret",
                f".size {reader}, .-{reader}",
            )
        )
    return "\n".join(output) + "\n", readers


def _program_and_profile_assembly(source: str) -> tuple[object, str, dict[str, object]]:
    compiled = compile_source(source, optimization=OptimizationLevel.O1)
    _, program = compiled.require_ordinary_artifacts()
    emitter = X8664Emitter(
        program,
        max_frames=MAX_FRAMES,
        max_instructions=MAX_INSTRUCTIONS,
        register_allocation=True,
        instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
    )
    assembly, origins = emitter.emit_with_origins()
    ordinary_assembly = generate_ffi_assembly(
        program,
        max_frames=MAX_FRAMES,
        max_instructions=MAX_INSTRUCTIONS,
        native_policy=NativeCodegenPolicy.BASELINE,
        instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
    )
    if assembly != ordinary_assembly:
        raise RuntimeError("origin collection changed ordinary FFI assembly bytes")
    codegen = build_codegen_report(
        program,
        assembly,
        native_origins=origins,
        source_sha256=_sha256(source.encode()),
        optimization=OptimizationLevel.O1.value,
        max_frames=MAX_FRAMES,
        max_instructions=MAX_INSTRUCTIONS,
    )
    return program, assembly, codegen


def _compile_and_run(
    library_path: Path,
    workload: dict[str, object],
    workload_id: str,
    *,
    expected: dict[str, float],
) -> tuple[list[float], str, int]:
    count = len(benchmark.OUTPUT_KEYS[workload_id])
    output = (ctypes.c_double * count)()
    library = ctypes.CDLL(str(library_path))
    call = benchmark._make_call(library, workload, output)
    status = call()
    if status != 0:
        raise RuntimeError(f"{workload_id} native correctness call returned {status}")
    values = list(output)
    benchmark._check_output(values, expected, workload_id)
    canonical = benchmark._json_bytes([round(value, 10) for value in values])
    return values, _sha256(canonical), status


def _compiler_source_hashes() -> dict[str, str]:
    paths = (
        "bootstrap/s3/optimizer.py",
        "bootstrap/s3/memory_effects.py",
        "bootstrap/s3/backends/x86_64/backend.py",
        "bootstrap/s3/backends/x86_64/emitter.py",
        "bootstrap/s3/backends/x86_64/allocation.py",
    )
    changed = _git("diff", "--name-only", "HEAD", "--", "bootstrap/s3")
    if changed:
        raise RuntimeError(f"compiler source differs from campaign HEAD: {changed}")
    return {
        path: _sha256(subprocess.run(
            ["git", "show", f"HEAD:{path}"], cwd=ROOT, check=True, capture_output=True
        ).stdout)
        for path in paths
    }


def profile_workloads(output_dir: Path, selected: set[str] | None = None) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("native dynamic profiling requires Linux x86-64")
    started = datetime.now(timezone.utc).isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, references = benchmark._load_inputs()
    manifest_by_id = {row["workload_id"]: row for row in manifest["workloads"]}
    workload_rows = {row["workload_id"]: row for row in references["workloads"]}
    selected_ids = sorted(selected or workload_rows.keys())
    unknown = sorted(set(selected_ids) - set(workload_rows))
    if unknown:
        raise ValueError(f"unknown workload IDs: {unknown}")

    toolchain = NativeToolchain.detect()
    results: dict[str, object] = {}
    artifact_hashes: dict[str, str] = {}
    for workload_id in selected_ids:
        workload = workload_rows[workload_id]
        spec = manifest_by_id[workload_id]
        if workload["dataset_sha256"] != spec["dataset_sha256"]:
            raise ValueError(f"{workload_id} dataset identity mismatch")
        source_path = ROOT / "benchmarks" / spec["s3_source"]
        source = source_path.read_text(encoding="utf-8")
        program, assembly, codegen = _program_and_profile_assembly(source)
        blocks = [
            (function.name, block.label, mangle_block(function.name, block.label))
            for function in program.functions
            if not function.external
            for block in function.blocks
        ]
        instrumented, counters = instrument_block_entries(
            assembly, [native_label for _, _, native_label in blocks]
        )
        baseline_path = output_dir / f"{workload_id}.baseline.so"
        instrumented_path = output_dir / f"{workload_id}.profiled.so"
        assembly_path = output_dir / f"{workload_id}.profiled.s"
        toolchain.build_shared(assembly, baseline_path)
        toolchain.build_shared(instrumented, instrumented_path, keep_assembly=assembly_path)

        baseline_values, baseline_hash, baseline_status = _compile_and_run(
            baseline_path, workload, workload_id, expected=workload["expected_output"]
        )
        profiled_values, profiled_hash, profiled_status = _compile_and_run(
            instrumented_path, workload, workload_id, expected=workload["expected_output"]
        )
        if baseline_status != profiled_status or baseline_hash != profiled_hash:
            raise RuntimeError(f"{workload_id} instrumented result differs from baseline")

        report_functions = {row["name"]: row for row in codegen["functions"]}
        visits: list[dict[str, object]] = []
        total_weight = 0
        dynamic_s3_opcodes: dict[str, int] = {}
        dynamic_native_categories: dict[str, int] = {}
        dynamic_origin_categories: dict[str, int] = {}
        for function_name, block_name, native_label in blocks:
            symbol = counters[native_label]
            reader = getattr(ctypes.CDLL(str(instrumented_path)), symbol)
            reader.argtypes = []
            reader.restype = ctypes.c_uint64
            executions = int(reader())
            block_report = next(
                row for row in report_functions[function_name]["blocks"] if row["name"] == block_name
            )
            static_native = block_report["native_assembly"]["machine_instruction_count"]
            weighted = executions * static_native
            total_weight += weighted
            for opcode, count in block_report["assembly_opcode_counts"].items():
                dynamic_s3_opcodes[opcode] = dynamic_s3_opcodes.get(opcode, 0) + executions * count
            for category, count in block_report["native_machine_opcode_categories"].items():
                dynamic_native_categories[category] = dynamic_native_categories.get(category, 0) + executions * count
            mapped = sum(block_report["native_origin_category_counts"].values())
            for category, count in block_report["native_origin_category_counts"].items():
                dynamic_origin_categories[category] = dynamic_origin_categories.get(category, 0) + executions * count
            dynamic_origin_categories["UNMAPPED"] = dynamic_origin_categories.get("UNMAPPED", 0) + executions * max(0, static_native - mapped)
            visits.append({
                "function": function_name,
                "block": block_name,
                "logical_block_executions": executions,
                "assembly_instruction_count": block_report["assembly_instruction_count"],
                "native_instruction_count_static": static_native,
                "estimated_structural_weight": weighted,
                "mapped_native_origin_instructions_static": mapped,
                "unmapped_native_instructions_static": max(0, static_native - mapped),
                "native_origin_categories_static": block_report["native_origin_category_counts"],
                "native_machine_categories_static": block_report["native_machine_opcode_categories"],
            })
        visits.sort(key=lambda row: (-int(row["estimated_structural_weight"]), str(row["function"]), str(row["block"])))
        function_static = sum(
            row["native_assembly"]["machine_instruction_count"]
            for row in codegen["functions"] if not row["external"]
        )
        block_static = sum(
            block["native_assembly"]["machine_instruction_count"]
            for row in codegen["functions"] if not row["external"]
            for block in row["blocks"]
        )
        key = f"{workload_id}.profiled.s"
        artifact_hashes[key] = _sha256(assembly_path.read_bytes())
        baseline_object_key = f"{workload_id}.baseline.so"
        profiled_object_key = f"{workload_id}.profiled.so"
        artifact_hashes[baseline_object_key] = _sha256(baseline_path.read_bytes())
        artifact_hashes[profiled_object_key] = _sha256(instrumented_path.read_bytes())
        results[workload_id] = {
            "dataset_id": workload["dataset_id"],
            "dataset_sha256": workload["dataset_sha256"],
            "source_path": source_path.relative_to(ROOT).as_posix(),
            "source_sha256": _sha256(source.encode()),
            "correctness": "PASS_BASELINE_AND_INSTRUMENTED_OUTPUTS_MATCH_REFERENCE_AND_EACH_OTHER",
            "baseline_output_sha256": baseline_hash,
            "instrumented_output_sha256": profiled_hash,
            "baseline_native_assembly_sha256": _sha256(assembly.encode()),
            "instrumented_native_assembly_sha256": artifact_hashes[key],
            "codegen_report_sha256": _sha256(_json_bytes(codegen)),
            "baseline_shared_object_sha256": artifact_hashes[baseline_object_key],
            "instrumented_shared_object_sha256": artifact_hashes[profiled_object_key],
            "instrumentation": "pushfq; inc qword ptr [rip+counter]; popfq at each S3 Assembly block entry",
            "timing_performed": False,
            "pmu_used": False,
            "logical_block_executions": sum(int(row["logical_block_executions"]) for row in visits),
            "estimated_uninstrumented_native_structural_weight": total_weight,
            "weighted_native_machine_syntax_categories": dict(sorted(dynamic_native_categories.items())),
            "weighted_native_origin_categories": dict(sorted(dynamic_origin_categories.items())),
            "logical_dynamic_s3_opcode_counts": dict(sorted(dynamic_s3_opcodes.items())),
            "uncovered_function_native_instructions_per_call": function_static - block_static,
            "profile_scope_note": "Weights include only S3 Assembly basic-block regions. Function prologues/epilogues and runtime-helper execution are excluded; static block weight is not a retired-instruction count because native lowering may branch within an Assembly block.",
            "hot_blocks": visits[:20],
        }

    result = {
        "schema_version": SCHEMA_VERSION,
        "report_kind": "S3_LOGICAL_DYNAMIC_BLOCK_PROFILE_EXPERIMENTAL",
        "measurement_kind": "LOGICAL_DYNAMIC_COUNTS_AND_STATIC_NATIVE_STRUCTURAL_WEIGHT",
        "started_at_utc": started,
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_provenance": {
            "git_head": _git("rev-parse", "HEAD"),
            "git_tree": _git("rev-parse", "HEAD^{tree}"),
            "worktree_dirty": bool(_git("status", "--porcelain")),
            "compiler_source_sha256": _compiler_source_hashes(),
            "profiling_tool_sha256": _sha256(Path(__file__).read_bytes()),
        },
        "configuration": {
            "optimization": "O1",
            "native_policy": "baseline",
            "instruction_budget_mode": "per-instruction",
            "max_frames": MAX_FRAMES,
            "max_instructions": MAX_INSTRUCTIONS,
            "target": "linux-x86_64",
            "compiler": toolchain.compiler,
            "compiler_version": subprocess.run([toolchain.compiler, "--version"], check=True, capture_output=True, text=True).stdout.splitlines()[0],
        },
        "results": results,
        "artifacts": artifact_hashes,
        "interpretation": "Logical block visits are dynamically counted in a correctness-checked instrumented native build. Structural weights multiply those visits by static uninstrumented native code size per Assembly block; they are not hardware instruction counts, cycles, or runtime estimates.",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workload", action="append", dest="workloads")
    args = parser.parse_args()
    result = profile_workloads(args.output.parent, set(args.workloads) if args.workloads else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_json_bytes(result))
    print(json.dumps({
        "output": str(args.output),
        "sha256": _sha256(args.output.read_bytes()),
        "workloads": {key: value["correctness"] for key, value in result["results"].items()},
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
