"""Research-only point-cloud address recurrence experiment; never production-wired."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_ffi_assembly
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.codegen_report import build_codegen_report
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from tools import s3_15_native_workload_benchmark as benchmark

WORKLOAD_ID = "engineering.point-cloud-summary.v1"
SOURCE_PATH = ROOT / "benchmarks/workloads/real_world/point_cloud_summary.s3"
FUNCTION = "point_cloud_summary"
SOURCE_SHA256 = "59e752e91159ece4e3a813bc8586f338544ddac52e4b5e755a219d85779238e9"
MAX_INSTRUCTIONS = 1_000_000_000
SEED = 111_007


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalized_source(source: str) -> str:
    return source.replace("\r\n", "\n")


def rewrite_point_cloud(source: str) -> str:
    """Replace exactly the two guarded 3*point conversions with tryte recurrences."""
    source = _normalized_source(source)
    if _sha(source.encode("utf-8")) != SOURCE_SHA256:
        raise ValueError("point-cloud source identity mismatch; refusing experimental rewrite")

    patterns = (
        (
            "mut point: i64 = 0\n"
            "                            while point < bounded_point_count:\n"
            "                                mut base: tryte = to_tryte(point * 3)",
            "mut point: i64 = 0\n"
            "                            mut base: tryte = 0\n"
            "                            while point < bounded_point_count:",
        ),
        (
            "point = 0\n"
            "                            while point < bounded_point_count:\n"
            "                                mut base: tryte = to_tryte(point * 3)",
            "point = 0\n"
            "                            base = 0\n"
            "                            while point < bounded_point_count:",
        ),
    )
    for old, new in patterns:
        if source.count(old) != 1:
            raise ValueError("expected one exact loop preheader/body pattern")
        source = source.replace(old, new, 1)

    update = "                                point = point + 1"
    if source.count(update) != 2:
        raise ValueError("expected exactly two point induction updates")
    source = source.replace(update, update + "\n                                base = base + 3")
    if "to_tryte(point * 3)" in source or source.count("base = base + 3") != 2:
        raise ValueError("address recurrence rewrite did not close both loop sites")
    return source


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _compile(source: str, output: Path) -> tuple[Path, dict[str, object]]:
    compilation = compile_source(source, OptimizationLevel.O1)
    _, program = compilation.require_ordinary_artifacts()
    assembly = generate_ffi_assembly(program, max_instructions=MAX_INSTRUCTIONS)
    toolchain = NativeToolchain.detect()
    toolchain.build_shared(assembly, output, keep_assembly=output.with_suffix(".s"))
    report = build_codegen_report(
        program,
        assembly,
        source_sha256=_sha(source.encode("utf-8")),
        optimization="O1",
        max_frames=1024,
        max_instructions=MAX_INSTRUCTIONS,
    )
    function_row = next(row for row in report["functions"] if row["name"] == FUNCTION)
    function = next(item for item in program.functions if item.name == FUNCTION)
    return output, {
        "assembly_sha256": _sha(assembly.encode("utf-8")),
        "assembly_instruction_count": function_row["assembly_instruction_count"],
        "assembly_opcode_counts": dict(sorted(
            __import__("collections").Counter(
                instruction.opcode.value
                for block in function.blocks
                for instruction in block.instructions
            ).items()
        )),
        "frame_bytes": function_row["frame_bytes"],
        "allocation": function_row["allocation"],
        "binary": benchmark._binary_metrics(output, FUNCTION),
    }


def _boundary_outputs(library_path: Path) -> dict[str, dict[str, object]]:
    import ctypes

    library = ctypes.CDLL(str(library_path))
    kernel = library.point_cloud_summary
    kernel.argtypes = [
        ctypes.POINTER(ctypes.c_double), ctypes.c_int64, ctypes.c_int64,
        ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
    ]
    kernel.restype = ctypes.c_int64
    results: dict[str, dict[str, object]] = {}
    for point_count in (0, 1, 64, 121, 122):
        length = point_count * 3
        coordinates_data = [float(index % 13 - 6) / 8 for index in range(length)]
        coordinates = (ctypes.c_double * max(1, length))(*coordinates_data or [0.0])
        output = (ctypes.c_double * 10)(*([9876.5] * 10))
        status = kernel(coordinates, length, point_count, output, 10)
        results[str(point_count)] = {"status": status, "output": list(output)}

    # The valid domain with a deliberately mismatched slice length must reject before reads.
    coordinates = (ctypes.c_double * 2)(1.0, 2.0)
    output = (ctypes.c_double * 10)(*([9876.5] * 10))
    status = kernel(coordinates, 2, 1, output, 10)
    results["length_mismatch"] = {"status": status, "output": list(output)}
    return results


def run(output: Path, build_dir: Path, *, iterations: int, warmups: int, samples: int) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("native address-strength experiment requires Linux x86-64")
    if iterations < 1 or warmups < 1 or samples < 3:
        raise ValueError("iterations/warmups must be positive and samples must be >= 3")
    source_bytes = SOURCE_PATH.read_bytes().replace(b"\r\n", b"\n")
    source = source_bytes.decode("utf-8")
    if _sha(source_bytes) != SOURCE_SHA256:
        raise ValueError("point-cloud workload SHA does not match the pinned control")
    candidate_source = rewrite_point_cloud(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    baseline_path, baseline_codegen = _compile(source, build_dir / "point-cloud-baseline.so")
    candidate_path, candidate_codegen = _compile(candidate_source, build_dir / "point-cloud-address-recurrence.so")

    manifest, references = benchmark._load_inputs()
    workload = next(item for item in references["workloads"] if item["workload_id"] == WORKLOAD_ID)
    manifest_workload = next(item for item in manifest["workloads"] if item["workload_id"] == WORKLOAD_ID)
    if manifest_workload["s3_source"] != "workloads/real_world/point_cloud_summary.s3":
        raise ValueError("benchmark manifest source path disagrees with pinned workload")
    output_rows: dict[str, dict[str, object]] = {}
    calls = {}
    for label, binary in (("baseline", baseline_path), ("candidate", candidate_path)):
        library = __import__("ctypes").CDLL(str(binary))
        values = (__import__("ctypes").c_double * len(benchmark.OUTPUT_KEYS[WORKLOAD_ID]))()
        call = benchmark._make_call(library, workload, values)
        status = call()
        if status != 0:
            raise RuntimeError(f"{label}: native workload returned {status}")
        actual = list(values)
        benchmark._check_output(actual, workload["expected_output"], WORKLOAD_ID)
        output_rows[label] = {
            "status": status,
            "values": actual,
            "output_sha256": _sha(benchmark._json_bytes([round(value, 10) for value in actual])),
        }
        calls[label] = call

    boundary = {
        label: _boundary_outputs(path)
        for label, path in (("baseline", baseline_path), ("candidate", candidate_path))
    }
    if boundary["baseline"] != boundary["candidate"]:
        raise RuntimeError("native boundary-case outputs differ")
    if output_rows["baseline"]["output_sha256"] != output_rows["candidate"]["output_sha256"]:
        raise RuntimeError("native benchmark output hashes differ")

    for _ in range(warmups):
        for label in ("baseline", "candidate"):
            if calls[label]() != 0:
                raise RuntimeError(f"{label}: nonzero status during warmup")
    timing_values = {"baseline": [], "candidate": []}
    paired_order = []
    for index in range(samples):
        order = ["baseline", "candidate"] if index % 2 == 0 else ["candidate", "baseline"]
        paired_order.append(order)
        for label in order:
            timing_values[label].append(benchmark._measure(calls[label], iterations))

    ratio = benchmark._paired_ratio_summary(timing_values["baseline"], timing_values["candidate"], SEED)
    native = {
        "text_section_bytes": baseline_codegen["binary"]["text_section_bytes"],
        "static_machine_instructions": baseline_codegen["binary"]["static_machine_instructions"],
        "static_memory_references": baseline_codegen["binary"]["static_memory_references"],
        "static_stack_references": baseline_codegen["binary"]["static_stack_references"],
        "static_branches": baseline_codegen["binary"]["static_branches"],
        "stack_frame_bytes": baseline_codegen["binary"]["stack_frame_bytes"],
    }
    candidate_native = {
        key: candidate_codegen["binary"][source_key]
        for key, source_key in (
            ("text_section_bytes", "text_section_bytes"),
            ("static_machine_instructions", "static_machine_instructions"),
            ("static_memory_references", "static_memory_references"),
            ("static_stack_references", "static_stack_references"),
            ("static_branches", "static_branches"),
            ("stack_frame_bytes", "stack_frame_bytes"),
        )
    }
    report: dict[str, object] = {
        "schema": "s3-1.11-address-strength-reduction-v1",
        "experiment_id": "EXP-S3-111-ADDR-RECURRENCE-001",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_tool_sha256": _sha(Path(__file__).read_bytes()),
        "source": {
            "git_commit": _git("rev-parse", "HEAD"),
            "git_tree": _git("rev-parse", "HEAD^{tree}"),
            "workload_path": SOURCE_PATH.relative_to(ROOT).as_posix(),
            "workload_sha256": SOURCE_SHA256,
            "candidate_source_sha256": _sha(candidate_source.encode("utf-8")),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "worktree_status": _git("status", "--porcelain"),
        },
        "hypothesis": "carry a proven tryte coordinate base by +3 across each point-cloud loop instead of recomputing point*3 and converting on each iteration",
        "proof_scope": {
            "point_count_domain": [1, 121],
            "coordinate_length_relation": "len(coordinates) == 3 * point_count",
            "base_sequence": "base(point) == 3 * point for point=0..point_count-1",
            "candidate_post_last_increment_max": 363,
            "tryte_domain": [-364, 364],
            "runtime_bounds_checks_changed": False,
            "source_workload_changed": False,
            "production_pipeline_changed": False,
        },
        "correctness": {
            "reference_output": "PASS_BOTH",
            "baseline_candidate_output_hash_equal": True,
            "boundary_cases": boundary,
            "boundary_outputs_equal": True,
            "native_status_equal": True,
        },
        "codegen": {
            "baseline": baseline_codegen,
            "candidate": candidate_codegen,
            "native_metric_delta": {
                key: candidate_native[key] - native[key] for key in native
            },
        },
        "timing": {
            "protocol": {
                "same_process_native_c_abi": True,
                "setup_and_build_excluded": True,
                "iterations_per_sample": iterations,
                "warmups": warmups,
                "samples": samples,
                "paired_order": paired_order,
                "seed": SEED,
                "material_threshold": benchmark.MATERIAL_CHANGE,
                "clock": "time.perf_counter_ns",
            },
            "baseline": benchmark._summary(timing_values["baseline"]),
            "candidate": benchmark._summary(timing_values["candidate"]),
            "baseline_over_candidate": ratio,
            "claim_class": "CHARACTERIZATION_ONLY",
            "pmu": "NOT_MEASURED",
        },
        "decision": "NO_PROMOTION",
        "limitations": [
            "The experiment covers only the exact pinned point-cloud workload source.",
            "The proof relies on the previously validated count/length guards and unit induction bounds.",
            "Structural and timing observations do not establish a general optimizer or vectorization authority.",
        ],
        "candidate_diff": "".join(difflib.unified_diff(
            source.splitlines(keepends=True), candidate_source.splitlines(keepends=True),
            fromfile="baseline.s3", tofile="candidate.s3",
        )),
    }
    output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=benchmark.DEFAULT_ITERATIONS)
    parser.add_argument("--warmups", type=int, default=benchmark.DEFAULT_WARMUPS)
    parser.add_argument("--samples", type=int, default=benchmark.DEFAULT_SAMPLES)
    args = parser.parse_args()
    report = run(
        args.output, args.build_dir,
        iterations=args.iterations, warmups=args.warmups, samples=args.samples,
    )
    print(json.dumps({
        "experiment_id": report["experiment_id"],
        "correctness": report["correctness"],
        "native_metric_delta": report["codegen"]["native_metric_delta"],
        "timing_class": report["timing"]["baseline_over_candidate"]["classification"],
        "report": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
