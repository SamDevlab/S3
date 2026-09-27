"""Create a deterministic paired-timing summary linked to immutable raw data."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import s3_15_native_workload_benchmark as benchmark  # noqa: E402


DEFAULT_RAW = (
    ROOT
    / "reports/s3-1.10-memory-intelligence-value-locality/evidence"
    / "EXP-S3-110-LOAD-001-native.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "reports/s3-1.10-memory-intelligence-value-locality/evidence"
    / "EXP-S3-110-LOAD-001-analysis.json"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(raw_path: Path) -> dict[str, object]:
    raw_bytes = raw_path.read_bytes()
    raw = json.loads(raw_bytes)
    experiment_id = raw.get("experiment_id")
    if experiment_id not in {
        "EXP-S3-110-LOAD-001",
        "EXP-S3-110-LOAD-HOT-001",
        "EXP-S3-110-LOAD-SSA-001",
    }:
        raise ValueError("raw result has unexpected experiment identity")
    rows = raw.get("workloads")
    if not isinstance(rows, dict) or not rows:
        raise ValueError("raw result has no workload timing rows")
    summaries: dict[str, object] = {}
    for workload_id, row in sorted(rows.items()):
        timing = row.get("timing")
        if not isinstance(timing, dict):
            raise ValueError(f"{workload_id}: timing object is missing")
        baseline = timing.get("baseline_ns_per_call")
        candidate = timing.get("candidate_ns_per_call")
        if not isinstance(baseline, list) or not isinstance(candidate, list):
            raise ValueError(f"{workload_id}: paired samples are missing")
        if len(baseline) != 21 or len(candidate) != 21:
            raise ValueError(f"{workload_id}: expected exactly 21 paired samples")
        summaries[workload_id] = benchmark._paired_ratio_summary(
            baseline, candidate, 3110
        )
    return {
        "schema_version": "1.0.0",
        "experiment_id": experiment_id,
        "analysis_kind": "POST_HOC_PAIRED_BOOTSTRAP_SUMMARY",
        "raw_result_path": str(raw_path.relative_to(ROOT)),
        "raw_result_sha256": _sha256(raw_bytes),
        "method": {
            "function": "tools.s3_15_native_workload_benchmark._paired_ratio_summary",
            "ratio": "paired baseline ns/candidate ns",
            "confidence_interval": "95% percentile bootstrap of median paired ratios",
            "resamples": 10000,
            "seed": 3110,
            "material_threshold": 0.05,
        },
        "workloads": summaries,
        "interpretation": "Per-workload characterization only; does not establish a general native speedup or hardware-level cause.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = _run(args.raw.resolve())
    encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={_sha256(encoded)}")
    for workload_id, row in result["workloads"].items():
        print(
            f"{workload_id}: ratio={row['baseline_over_candidate_median_ratio']:.6f} "
            f"CI={row['paired_bootstrap_95_percentile_interval']} "
            f"classification={row['classification']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
