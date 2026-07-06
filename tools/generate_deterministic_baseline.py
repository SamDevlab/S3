import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bootstrap.s3 import OptimizationLevel  # noqa: E402
from tools.benchmark import (  # noqa: E402
    BENCHMARK_FORMAT_VERSION,
    load_manifest,
    run_hosted_pipeline,
)

BASELINE_FORMAT_VERSION = "1.0.0"
IR_FIELDS = ("function_count", "block_count", "instruction_count")
S3_ASSEMBLY_FIELDS = (
    "function_count",
    "block_count",
    "opcode_count",
    "textual_size_bytes",
    "sha256",
)
EXECUTION_FIELDS = (
    "executed_s3_opcodes",
    "maximum_frame_depth_observed",
    "function_call_count",
)
OPTIMIZATION_LEVELS = (
    ("O0", OptimizationLevel.O0),
    ("O1", OptimizationLevel.O1),
)


def _select_fields(values, fields):
    return {field: values[field] for field in fields}


def generate_baseline():
    root = Path(__file__).resolve().parent.parent
    manifest_path = root / "benchmarks" / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: Manifest not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest(manifest_path)
    workloads = manifest.get("workloads", [])

    baseline = {
        "baseline_format_version": BASELINE_FORMAT_VERSION,
        "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
        "workloads": {},
    }

    # Use a stable order matching the manifest
    for w in workloads:
        w_id = w["id"]
        w_path = root / "benchmarks" / w["file"]

        if not w_path.exists():
            print(f"Error: Workload file not found at {w_path}", file=sys.stderr)
            sys.exit(1)

        src = w_path.read_text(encoding="utf-8")
        baseline["workloads"][w_id] = {}

        for opt_str, opt in OPTIMIZATION_LEVELS:
            ret, _, static_metrics, dynamic_metrics, _, _, _ = run_hosted_pipeline(
                src,
                opt,
                w["max_instructions"],
                w["max_frames"],
            )

            if ret != w["expected_return"]:
                raise ValueError(
                    f"Workload {w_id} {opt_str} returned {ret}, "
                    f"expected {w['expected_return']}"
                )

            opt_res = {
                "expected_return": w["expected_return"],
                "ir": _select_fields(static_metrics["ir"], IR_FIELDS),
                "s3_assembly": _select_fields(
                    static_metrics["s3_assembly"],
                    S3_ASSEMBLY_FIELDS,
                ),
                "execution": _select_fields(
                    dynamic_metrics["execution"],
                    EXECUTION_FIELDS,
                ),
            }
            baseline["workloads"][w_id][opt_str] = opt_res

    return baseline


def main():
    parser = argparse.ArgumentParser(
        description="Generate deterministic baseline for S3 benchmarks"
    )
    parser.add_argument("--output", help="Output JSON file path", required=True)
    args = parser.parse_args()

    baseline_data = generate_baseline()
    out_str = (
        json.dumps(
            baseline_data,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(out_str)

    print(f"Baseline successfully generated at {args.output}")


if __name__ == "__main__":
    main()
