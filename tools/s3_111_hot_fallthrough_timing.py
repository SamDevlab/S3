"""Paired timing characterization of the pinned hot-fallthrough binary pair."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import s3_15_native_workload_benchmark as benchmark

DEFAULT_ITERATIONS = 1_000
DEFAULT_WARMUPS = 3
DEFAULT_SAMPLES = 21
RESAMPLES = 10_000
BOOTSTRAP_SEED = 111_101


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def paired_summary(
    baseline: list[float], candidate: list[float], *, seed: int = BOOTSTRAP_SEED
) -> dict[str, Any]:
    if len(baseline) != len(candidate) or len(baseline) < 3:
        raise ValueError("paired timing requires equal sample counts >= 3")
    ratios = [before / after for before, after in zip(baseline, candidate, strict=True)]
    rng = random.Random(seed)
    bootstrap = sorted(
        statistics.median(rng.choices(ratios, k=len(ratios)))
        for _ in range(RESAMPLES)
    )
    lower = bootstrap[int(0.025 * RESAMPLES)]
    upper = bootstrap[int(0.975 * RESAMPLES) - 1]
    if lower > 1.05:
        classification = "MATERIAL_IMPROVEMENT"
    elif upper < 0.95:
        classification = "MATERIAL_REGRESSION"
    elif lower >= 0.95 and upper <= 1.05:
        classification = "NO_MATERIAL_CHANGE_WITHIN_5_PERCENT"
    else:
        classification = "INCONCLUSIVE"
    return {
        "baseline_over_candidate_median_ratio": statistics.median(ratios),
        "paired_bootstrap_95_percentile_interval": [lower, upper],
        "resamples": RESAMPLES,
        "seed": seed,
        "material_change_threshold": 0.05,
        "classification": classification,
    }


def _verify_binary(path: Path, descriptor: object) -> dict[str, Any]:
    if not isinstance(descriptor, dict):
        raise ValueError("binary descriptor is missing")
    name, size, digest = descriptor.get("file_name"), descriptor.get("bytes"), descriptor.get("sha256")
    if not isinstance(name, str) or Path(name).name != name or name != path.name:
        raise ValueError("binary filename differs from the pinned descriptor")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("binary size is invalid")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("binary SHA-256 is invalid")
    if path.is_symlink() or not path.is_file():
        raise ValueError("binary must be a regular file")
    data = path.read_bytes()
    if len(data) != size or _sha256(data) != digest:
        raise ValueError("binary bytes differ from the experiment descriptor")
    return {"file_name": name, "bytes": size, "sha256": digest}


def characterize(
    *,
    source_root: Path,
    experiment_path: Path,
    binary_root: Path,
    iterations: int = DEFAULT_ITERATIONS,
    warmups: int = DEFAULT_WARMUPS,
    samples: int = DEFAULT_SAMPLES,
) -> dict[str, Any]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("hot-fallthrough timing requires Linux x86-64")
    if iterations < 1 or warmups < 1 or samples < 3:
        raise ValueError("iterations/warmups must be positive and samples must be >= 3")
    source_root = source_root.resolve()
    experiment_bytes = experiment_path.read_bytes()
    experiment = json.loads(experiment_bytes)
    if experiment.get("experiment_id") != "EXP-S3-111-HOT-FALLTHROUGH-001":
        raise ValueError("experiment identity is not the pinned hot-fallthrough candidate")
    control = experiment.get("control")
    if not isinstance(control, dict):
        raise ValueError("experiment control metadata is missing")
    source_commit = _git(source_root, "rev-parse", "HEAD")
    source_tree = _git(source_root, "rev-parse", "HEAD^{tree}")
    if (source_commit, source_tree) != (control.get("s3_commit"), control.get("s3_tree")):
        raise ValueError("S3 source identity differs from candidate evidence")
    if _git(source_root, "status", "--porcelain", "--", "bootstrap/s3"):
        raise ValueError("tracked compiler source differs from the pinned control")

    workload = experiment.get("workload")
    artifact_rows = experiment.get("artifacts")
    if not isinstance(workload, dict) or not isinstance(artifact_rows, dict):
        raise ValueError("candidate workload or artifacts are missing")
    workload_id = workload.get("workload_id")
    if not isinstance(workload_id, str):
        raise ValueError("candidate workload identity is invalid")
    baseline_path = binary_root / str(artifact_rows.get("baseline", {}).get("file_name"))
    candidate_path = binary_root / str(artifact_rows.get("candidate", {}).get("file_name"))
    baseline_artifact = _verify_binary(baseline_path, artifact_rows.get("baseline"))
    candidate_artifact = _verify_binary(candidate_path, artifact_rows.get("candidate"))

    _, references = benchmark._load_inputs()
    reference = next(
        row for row in references["workloads"] if row["workload_id"] == workload_id
    )
    libraries = {
        "baseline": ctypes.CDLL(str(baseline_path)),
        "candidate": ctypes.CDLL(str(candidate_path)),
    }
    calls: dict[str, Any] = {}
    outputs: dict[str, list[float]] = {}
    output_hashes: dict[str, str] = {}
    expected_hash_key = {
        "baseline": "baseline_output_sha256",
        "candidate": "candidate_output_sha256",
    }
    for name, library in libraries.items():
        output = (ctypes.c_double * len(benchmark.OUTPUT_KEYS[workload_id]))()
        call = benchmark._make_call(library, reference, output)
        status = call()
        values = list(output)
        if status != 0:
            raise RuntimeError(f"{name} correctness invocation returned {status}")
        benchmark._check_output(values, reference["expected_output"], workload_id)
        digest = _sha256(benchmark._json_bytes([round(value, 10) for value in values]))
        if digest != workload.get(expected_hash_key[name]):
            raise ValueError(f"{name} output differs from pinned experiment evidence")
        calls[name] = call
        outputs[name] = values
        output_hashes[name] = digest
    if outputs["baseline"] != outputs["candidate"]:
        raise ValueError("baseline and candidate outputs are not exactly equal")

    for index in range(warmups):
        order = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
        for name in order:
            if calls[name]() != 0:
                raise RuntimeError(f"{name} failed during warmup")

    timings: dict[str, list[float]] = {"baseline": [], "candidate": []}
    paired_order: list[list[str]] = []
    for index in range(samples):
        order = ["baseline", "candidate"] if index % 2 == 0 else ["candidate", "baseline"]
        paired_order.append(order)
        for name in order:
            timings[name].append(benchmark._measure(calls[name], iterations))

    summary = paired_summary(timings["baseline"], timings["candidate"])
    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-111-HOT-FALLTHROUGH-TIMING-001",
        "candidate_experiment_id": experiment["experiment_id"],
        "workload_id": workload_id,
        "status": "PASS",
        "classification": "CHARACTERIZATION_ONLY_NO_PROMOTION",
        "provenance": {
            "s3_commit": source_commit,
            "s3_tree": source_tree,
            "tracked_compiler_source_clean": True,
            "candidate_experiment_sha256": _sha256(experiment_bytes),
            "timing_tool_sha256": _sha256(Path(__file__).read_bytes()),
            "target": "Linux x86-64",
            "measurement": "S3 benchmark _measure; same workload/reference; paired order alternates",
            "hardware_counters": "NOT_USED",
            "pmu": "NOT_PROBED_BY_THIS_EXPERIMENT",
        },
        "protocol": {
            "warmups_per_artifact": warmups,
            "paired_samples": samples,
            "iterations_per_sample": iterations,
            "paired_order": paired_order,
            "timing_class": "CHARACTERIZATION_ONLY",
            "native_speedup_claim": False,
        },
        "correctness": {
            "baseline_reference": "PASS",
            "candidate_reference": "PASS",
            "outputs_exactly_equal": True,
            "baseline_output_sha256": output_hashes["baseline"],
            "candidate_output_sha256": output_hashes["candidate"],
        },
        "artifacts": {"baseline": baseline_artifact, "candidate": candidate_artifact},
        "timing": {
            "baseline_ns_per_call": timings["baseline"],
            "candidate_ns_per_call": timings["candidate"],
            "baseline_median_ns_per_call": statistics.median(timings["baseline"]),
            "candidate_median_ns_per_call": statistics.median(timings["candidate"]),
            "paired_baseline_over_candidate": summary,
        },
        "interpretation": "One hot unconditional jump was removed structurally. This single workload characterization does not establish a general runtime benefit or causality.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--binary-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = characterize(
        source_root=args.source_root,
        experiment_path=args.experiment,
        binary_root=args.binary_root,
    )
    encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    summary = result["timing"]["paired_baseline_over_candidate"]
    print(
        f"OUTPUT={args.output}\nTIMING={summary['classification']} "
        f"RATIO={summary['baseline_over_candidate_median_ratio']:.6f} "
        f"CI95={summary['paired_bootstrap_95_percentile_interval']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
