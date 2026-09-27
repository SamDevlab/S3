"""Bounded, non-production native optimization experiments for S3 1.9."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64 import (  # noqa: E402
    NativeToolchain,
    generate_ffi_assembly,
)
from bootstrap.s3.codegen import generate_assembly  # noqa: E402
from bootstrap.s3.initialization import analyze_initialization  # noqa: E402
from bootstrap.s3.ir import IRFunction, IRInstruction, IRModule, IROpcode  # noqa: E402
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402
from bootstrap.s3.verifier import verify_ir  # noqa: E402

from tools import s3_15_native_workload_benchmark as benchmark  # noqa: E402


PURE_OPCODES = frozenset({
    IROpcode.CONST,
    IROpcode.CONST_STR,
    IROpcode.MOVE,
    IROpcode.INVERT,
    IROpcode.ADD,
    IROpcode.NUMERIC_DIFFERENCE,
    IROpcode.MULTIPLY,
    IROpcode.DIVIDE,
    IROpcode.RELATE,
    IROpcode.CONVERT,
    IROpcode.MINIMUM,
    IROpcode.MAXIMUM,
    IROpcode.COMPARE,
})
EXPERIMENT_TEST = "tests/test_s3_native_optimization_experiments.py"


def forward_repeated_mutable_loads(function: IRFunction) -> tuple[IRFunction, int]:
    """Forward identical mutable-cell loads within a block, across pure ops.

    Register versions prevent reuse after either the index or cached result is
    redefined. All non-pure operations clear facts. This IR-level experiment
    avoids SSA round-tripping functions with observable memory.
    """
    mutable_memory = {item.index for item in function.memory_objects if item.mutable}
    register_types = {register.index: register.type for register in function.registers}
    versions: dict[int, int] = {}
    forwarded = 0
    updated_blocks = []

    def bump_results(instruction: IRInstruction) -> None:
        for register in instruction.results:
            versions[register] = versions.get(register, 0) + 1

    for block in function.blocks:
        available: dict[tuple[object, ...], tuple[int, int]] = {}
        instructions = []
        for instruction in block.instructions:
            eligible = (
                instruction.opcode is IROpcode.LOAD
                and instruction.memory in mutable_memory
                and len(instruction.results) == 1
                and len(instruction.operands) == 1
                and instruction.results[0] in register_types
            )
            if eligible:
                index = instruction.operands[0]
                index_version = versions.get(index, 0)
                result = instruction.results[0]
                key = (
                    instruction.memory,
                    index,
                    index_version,
                    instruction.initialization,
                    register_types[result],
                )
                prior = available.get(key)
                if (
                    prior is not None
                    and prior[0] != result
                    and versions.get(prior[0], 0) == prior[1]
                ):
                    replacement = replace(
                        instruction,
                        opcode=IROpcode.MOVE,
                        operands=(prior[0],),
                        immediate=None,
                        static_string=None,
                        callee=None,
                        targets=(),
                        memory=None,
                        initialization=False,
                        reference_target=None,
                        reference_mutable=False,
                        reference_is_slice=False,
                        slice_length_result=None,
                        reference_aggregate=None,
                        aggregate_field_paths=(),
                        aggregate_field_path=(),
                        bounds_proven=False,
                    )
                    instructions.append(replacement)
                    forwarded += 1
                    bump_results(instruction)
                    if (
                        versions.get(index, 0) == index_version
                        and versions.get(prior[0], 0) == prior[1]
                    ):
                        available[key] = (result, versions[result])
                    continue

                instructions.append(instruction)
                bump_results(instruction)
                if versions.get(index, 0) == index_version:
                    available[key] = (result, versions[result])
                continue

            instructions.append(instruction)
            bump_results(instruction)
            if instruction.opcode not in PURE_OPCODES:
                available.clear()

        updated_blocks.append(replace(block, instructions=tuple(instructions)))

    if forwarded == 0:
        return function, 0
    return replace(function, blocks=tuple(updated_blocks)), forwarded


def transform_module(module: IRModule) -> tuple[IRModule, dict[str, int]]:
    transformed = []
    counts: dict[str, int] = {}
    for function in module.functions:
        if function.external:
            transformed.append(function)
            counts[function.name] = 0
            continue
        candidate, forwarded = forward_repeated_mutable_loads(function)
        transformed.append(candidate)
        counts[function.name] = forwarded
    result = replace(module, functions=tuple(transformed))
    verify_ir(result)
    analyze_initialization(result)
    return result, counts


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def _module_load_count(module: IRModule) -> int:
    memory_by_function = {
        function.name: {item.index for item in function.memory_objects if item.mutable}
        for function in module.functions
    }
    return sum(
        1
        for function in module.functions
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.LOAD
        and instruction.memory in memory_by_function[function.name]
    )


def _compile_native(assembly_program: object, output: Path, assembly_path: Path) -> str:
    text = generate_ffi_assembly(assembly_program)  # type: ignore[arg-type]
    toolchain = NativeToolchain.detect()
    toolchain.build_shared(text, output, keep_assembly=assembly_path)
    return text


def _run_output(library_path: Path, workload: dict[str, Any], workload_id: str) -> tuple[list[float], str]:
    output = (ctypes.c_double * len(benchmark.OUTPUT_KEYS[workload_id]))()
    library = ctypes.CDLL(str(library_path))
    call = benchmark._make_call(library, workload, output)
    status = call()
    if status != 0:
        raise RuntimeError(f"{workload_id} returned native status {status}")
    values = list(output)
    benchmark._check_output(values, workload["expected_output"], workload_id)
    digest = _sha256(benchmark._json_bytes([round(value, 10) for value in values]))
    return values, digest


def run_experiment(output_dir: Path) -> dict[str, Any]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("native optimization experiment requires Linux x86-64")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, references = benchmark._load_inputs()
    workload_rows = {row["workload_id"]: row for row in references["workloads"]}
    manifest_rows = {row["workload_id"]: row for row in manifest["workloads"]}
    results: dict[str, Any] = {}
    baseline_loads = 0
    candidate_loads = 0
    forwarded_by_function: dict[str, int] = {}

    for workload_id in sorted(workload_rows):
        workload = workload_rows[workload_id]
        source_path = ROOT / "benchmarks" / manifest_rows[workload_id]["s3_source"]
        source = source_path.read_text(encoding="utf-8")
        source_sha = _sha256(source.encode("utf-8"))
        compiled = compile_source(source, optimization=OptimizationLevel.O1)
        baseline_ir, baseline_assembly = compiled.require_ordinary_artifacts()
        candidate_ir, local_counts = transform_module(baseline_ir)
        candidate_assembly = generate_assembly(candidate_ir)

        before = _module_load_count(baseline_ir)
        after = _module_load_count(candidate_ir)
        eliminated = sum(local_counts.values())
        if before - after != eliminated:
            raise RuntimeError(f"{workload_id} candidate load accounting does not reconcile")
        baseline_loads += before
        candidate_loads += after
        for function, count in local_counts.items():
            forwarded_by_function[f"{workload_id}:{function}"] = count

        baseline_path = output_dir / f"{workload_id}.baseline.so"
        candidate_path = output_dir / f"{workload_id}.local-load-forwarding.so"
        baseline_assembly_path = output_dir / f"{workload_id}.baseline.s"
        candidate_assembly_path = output_dir / f"{workload_id}.local-load-forwarding.s"
        baseline_native = _compile_native(baseline_assembly, baseline_path, baseline_assembly_path)
        candidate_native = _compile_native(candidate_assembly, candidate_path, candidate_assembly_path)
        baseline_values, baseline_output_sha = _run_output(baseline_path, workload, workload_id)
        candidate_values, candidate_output_sha = _run_output(candidate_path, workload, workload_id)
        if baseline_values != candidate_values or baseline_output_sha != candidate_output_sha:
            raise RuntimeError(f"{workload_id} candidate output differs from the O1 baseline")

        results[workload_id] = {
            "source_path": manifest_rows[workload_id]["s3_source"],
            "source_sha256": source_sha,
            "dataset_sha256": workload["dataset_sha256"],
            "correctness": "PASS_REFERENCE_AND_BASELINE_EXACT_OUTPUT_MATCH",
            "output_sha256": candidate_output_sha,
            "mutable_loads_before": before,
            "mutable_loads_forwarded": eliminated,
            "mutable_loads_after": after,
            "baseline_native_assembly_sha256": _sha256(baseline_native.encode()),
            "candidate_native_assembly_sha256": _sha256(candidate_native.encode()),
            "baseline_native_assembly_bytes": len(baseline_native.encode()),
            "candidate_native_assembly_bytes": len(candidate_native.encode()),
        }

    toolchain = NativeToolchain.detect()
    compiler_version = subprocess.run(
        [toolchain.compiler, "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-19-OPT-001",
        "report_kind": "S3_EXPERIMENTAL_LOCAL_MUTABLE_LOAD_FORWARDING",
        "execution_environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "native_compiler": toolchain.compiler,
            "native_compiler_version": compiler_version,
        },
        "experiment_implementation": {
            "driver_path": "tools/s3_native_optimization_experiments.py",
            "driver_sha256": _sha256(Path(__file__).read_bytes()),
            "focused_test_path": EXPERIMENT_TEST,
            "focused_test_sha256": _sha256((ROOT / EXPERIMENT_TEST).read_bytes()),
        },
        "source_revision": {
            "git_commit": _git("rev-parse", "HEAD"),
            "git_tree": _git("rev-parse", "HEAD^{tree}"),
            "compiler_source_sha256": {
                path: _sha256(subprocess.run(
                    ["git", "show", f"HEAD:{path}"], cwd=ROOT,
                    check=True, capture_output=True,
                ).stdout)
                for path in (
                    "bootstrap/s3/optimizer.py",
                    "bootstrap/s3/memory_effects.py",
                    "bootstrap/s3/ssa_optimizer/value_numbering.py",
                    "bootstrap/s3/ssa.py",
                )
            },
            "compiler_source_dirty": bool(_git("diff", "--name-only", "HEAD", "--", "bootstrap/s3")),
        },
        "transformation": {
            "precondition": "two mutable LOADs in one IR basic block use the same memory ID, unchanged index-register version, initialization flag, and result type",
            "barriers": "all non-pure instructions, index/result register redefinitions, and block boundaries",
            "rewrite": "second LOAD result becomes MOVE from first LOAD result",
            "production_pipeline_changed": False,
            "timing_performed": False,
            "pmu_used": False,
        },
        "summary": {
            "mutable_loads_before": baseline_loads,
            "mutable_loads_forwarded": baseline_loads - candidate_loads,
            "mutable_loads_after": candidate_loads,
            "forwarded_by_function": dict(sorted(forwarded_by_function.items())),
            "output_equivalence": "EXACT_FLOAT_OUTPUTS_AND_REFERENCE_TOLERANCES_PASS",
            "native_timing_claim": False,
            "status": "SUPPORTED_STRUCTURAL_CANDIDATE" if baseline_loads > candidate_loads
                     else "REJECTED_NO_ELIGIBLE_REPEATED_MUTABLE_LOADS",
        },
        "workloads": results,
    }


def main(argv: list[str] | None = None) -> int:
    default_output = ROOT / "reports/s3-1.9-native-observatory-optimization-discovery/evidence/optimizations"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=default_output)
    args = parser.parse_args(argv)
    report = run_experiment(args.output_dir / "local-load-forwarding-build")
    output_path = args.output_dir / "EXP-S3-19-OPT-001-local-load-forwarding.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(f"OPTIMIZATION_EXPERIMENT={report['summary']['status']}")
    print(f"MUTABLE_LOADS_BEFORE={report['summary']['mutable_loads_before']}")
    print(f"MUTABLE_LOADS_FORWARDED={report['summary']['mutable_loads_forwarded']}")
    print(f"MUTABLE_LOADS_AFTER={report['summary']['mutable_loads_after']}")
    print(f"REPORT={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
