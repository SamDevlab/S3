"""Test research-only omission of allocator-proven same-color TMOV bodies."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.assembly import AssemblyInstruction, AssemblyOpcode, AssemblyProgram
from bootstrap.s3.assembly_verifier import AssemblyVerifier
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
from bootstrap.s3.backends.x86_64.layout import FrameLayout
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from tools import s3_15_native_workload_benchmark as benchmark
from tools import s3_111_value_cost_experiments as value_cost
from tools.s3_memory_availability_experiment import forward_available_stores


class SameColorCopyEmitter(X8664Emitter):
    """Keep logical budget/init work while omitting proven physical no-op copies."""

    def _emit_instruction(
        self,
        function,
        block_name: str,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
        *,
        include_budget: bool = True,
    ) -> list[str]:
        if (
            self.register_allocation
            and instruction.opcode is AssemblyOpcode.TMOV
            and len(instruction.registers) == 2
            and self.current_plan is not None
        ):
            destination, source = instruction.registers
            destination_physical = self.current_plan.physical_register(destination)
            source_physical = self.current_plan.physical_register(source)
            if (
                destination != source
                and destination_physical is not None
                and destination_physical == source_physical
            ):
                instrumentation = (
                    self._instruction_instrumentation(function, block_name, instruction)
                    if include_budget
                    else []
                )
                return [
                    *instrumentation,
                    *self._check_register_initialized(layout, source),
                    *self._write_register(layout, destination, source_physical),
                ]
        return super()._emit_instruction(
            function,
            block_name,
            layout,
            instruction,
            include_budget=include_budget,
        )


def emit_same_color_candidate(program: AssemblyProgram, *, max_instructions: int) -> tuple[str, tuple[dict[str, object], ...]]:
    AssemblyVerifier().validate(program, entry="main")
    emitter = SameColorCopyEmitter(
        program,
        max_frames=1024,
        max_instructions=max_instructions,
        register_allocation=True,
        instruction_budget_mode="per-instruction",
    )
    return emitter.emit_with_origins()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(output_dir: Path, *, root: Path) -> dict[str, Any]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("same-color copy experiment requires Linux x86-64")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, references = benchmark._load_inputs()
    manifest_by_id = {row["workload_id"]: row for row in manifest["workloads"]}
    workloads: list[dict[str, Any]] = []

    for reference in sorted(references["workloads"], key=lambda row: row["workload_id"]):
        workload_id = reference["workload_id"]
        source_path = root / "benchmarks" / manifest_by_id[workload_id]["s3_source"]
        source_bytes = source_path.read_bytes().replace(b"\r\n", b"\n")
        if b"\r" in source_bytes:
            raise ValueError(f"{workload_id}: noncanonical CR bytes")
        source_sha = _sha(source_bytes)
        if source_sha != reference.get("source_sha256", source_sha):
            raise ValueError(f"{workload_id}: source identity mismatch")

        compilation = compile_source(source_bytes.decode("utf-8"), OptimizationLevel.O1)
        module, _baseline_program = compilation.require_ordinary_artifacts()
        store_module, eligible = forward_available_stores(module)
        store_program = value_cost.generate_assembly(store_module)
        symbol = value_cost.WORKLOAD_SYMBOLS[workload_id]
        function = next(item for item in store_program.functions if item.name == symbol)
        allocation = analyze_allocation(function, reserved_registers=frozenset({"r15"}))
        native_candidate, origins = emit_same_color_candidate(
            store_program, max_instructions=value_cost.MAX_INSTRUCTIONS
        )
        baseline_native = value_cost.generate_ffi_assembly(
            store_program, max_instructions=value_cost.MAX_INSTRUCTIONS
        )

        baseline_path = output_dir / f"{workload_id}-store-to-load.so"
        candidate_path = output_dir / f"{workload_id}-same-color-copy.so"
        toolchain = value_cost.NativeToolchain.detect()
        toolchain.build_shared(baseline_native, baseline_path, keep_assembly=baseline_path.with_suffix(".s"))
        toolchain.build_shared(native_candidate, candidate_path, keep_assembly=candidate_path.with_suffix(".s"))

        libraries = {"store_to_load": ctypes.CDLL(str(baseline_path)), "same_color_copy": ctypes.CDLL(str(candidate_path))}
        calls = {}
        output_rows = {}
        for label, library in libraries.items():
            output = (ctypes.c_double * len(benchmark.OUTPUT_KEYS[workload_id]))()
            call = benchmark._make_call(library, reference, output)
            status = call()
            if status != 0:
                raise RuntimeError(f"{workload_id} {label}: native status {status}")
            values = list(output)
            benchmark._check_output(values, reference["expected_output"], workload_id)
            digest = _sha(benchmark._json_bytes([round(value, 10) for value in values]))
            output_rows[label] = {"values": values, "output_sha256": digest}
            calls[label] = call
        if output_rows["store_to_load"]["output_sha256"] != output_rows["same_color_copy"]["output_sha256"]:
            raise RuntimeError(f"{workload_id}: same-color candidate changed output")

        for _ in range(benchmark.DEFAULT_WARMUPS):
            calls["store_to_load"]()
            calls["same_color_copy"]()
        samples: dict[str, list[float]] = {"store_to_load": [], "same_color_copy": []}
        order = ["store_to_load", "same_color_copy"]
        for index in range(benchmark.DEFAULT_SAMPLES):
            if index % 2:
                order.reverse()
            for label in order:
                samples[label].append(benchmark._measure(calls[label], benchmark.DEFAULT_ITERATIONS))

        move_sites = []
        for block in function.blocks:
            for index, instruction in enumerate(block.instructions):
                if instruction.opcode is not AssemblyOpcode.TMOV or len(instruction.registers) != 2:
                    continue
                destination, source = instruction.registers
                destination_physical = allocation.physical_register(destination)
                source_physical = allocation.physical_register(source)
                if destination != source and destination_physical is not None and destination_physical == source_physical:
                    move_sites.append({"block": block.label, "instruction_index": index})

        timing = benchmark._paired_ratio_summary(
            samples["store_to_load"], samples["same_color_copy"], seed=111130 + len(workloads)
        )
        baseline_binary = benchmark._binary_metrics(baseline_path, symbol)
        candidate_binary = benchmark._binary_metrics(candidate_path, symbol)
        workload_origins = [row for row in origins if row.get("function") == symbol]
        workloads.append(
            {
                "workload_id": workload_id,
                "source_sha256": source_sha,
                "store_to_load_eligible_sites": eligible,
                "same_color_tmov_sites": move_sites,
                "same_color_tmov_count": len(move_sites),
                "correctness": "PASS_REFERENCE_AND_EXACT_OUTPUT_EQUAL",
                "native_output": output_rows,
                "native_artifacts": {
                    "store_to_load": value_cost._artifact_facts(baseline_path),
                    "same_color_copy": value_cost._artifact_facts(candidate_path),
                },
                "native_binary_delta": {
                    key: candidate_binary[key] - baseline_binary[key]
                    for key in baseline_binary
                },
                "timing": {
                    "timing_class": "CHARACTERIZATION_ONLY",
                    "store_to_load": benchmark._summary(samples["store_to_load"]),
                    "same_color_copy": benchmark._summary(samples["same_color_copy"]),
                    "paired_store_to_load_over_candidate": timing,
                    "raw_samples_ns_per_call": samples,
                },
                "origin_rows_for_function": len(workload_origins),
                "budget_mode": "PER_INSTRUCTION; dec r15 retained for every Assembly instruction",
            }
        )

    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-111-MOVE-COALESCE-002",
        "classification": "RESEARCH_ONLY_SAME_COLOR_COPY_EMISSION_PROTOTYPE",
        "provenance": {
            "s3_commit": _git(root, "rev-parse", "HEAD"),
            "s3_tree": _git(root, "rev-parse", "HEAD^{tree}"),
            "compiler_source_dirty": bool(_git(root, "status", "--porcelain", "--", "bootstrap/s3")),
            "tool_sha256": _sha(Path(__file__).read_bytes()),
            "target": "Linux x86-64",
            "optimization": "O1 plus proof-gated STORE-to-LOAD candidate",
            "instruction_budget_mode": "PER_INSTRUCTION",
            "production_pipeline_changed": False,
            "pmu": "UNAVAILABLE_BY_POLICY_NOT_PROBED_AGAIN",
        },
        "protocol": {
            "warmups": benchmark.DEFAULT_WARMUPS,
            "samples": benchmark.DEFAULT_SAMPLES,
            "iterations_per_sample": benchmark.DEFAULT_ITERATIONS,
            "paired_order": "alternating store-to-load/candidate order",
            "native_speedup_claim": False,
        },
        "workloads": workloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output_dir, root=args.root.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"experiment_id": result["experiment_id"], "workloads": len(result["workloads"]), "report": str(args.report)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
