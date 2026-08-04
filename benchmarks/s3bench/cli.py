"""Command-line interface for s3bench 1.0."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Sequence

from .adapters import create_adapter_registry, detect_toolchains
from .core import (
    AdapterUnavailable,
    BenchmarkError,
    BenchmarkHarness,
    DEFAULT_SAMPLES,
    DEFAULT_TARGET_SAMPLE_NS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_WARMUPS,
    Case,
    compare_results,
    failed_result,
    load_manifest,
    unavailable_result,
    write_json,
)
from .report import render_performance_report

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "benchmarks" / "manifests" / "s3bench-1.0.0.json"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Versioned correctness-first benchmark harness for S3",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--benchmark", action="append")
    parser.add_argument("--category", action="append")
    parser.add_argument("--implementation", action="append")
    parser.add_argument("--mode", action="append")
    parser.add_argument("--optimization", action="append")
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--loops", type=int)
    parser.add_argument("--target-sample-duration-ns", type=int, default=DEFAULT_TARGET_SAMPLE_NS)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--metadata-file", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--historical-baseline", type=Path)
    parser.add_argument("--comparison-baseline", type=Path)
    parser.add_argument("--reference-implementation", default="c")
    parser.add_argument("--runner-type", choices=["local", "shared-ci", "controlled-linux"], default="local")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    _, cases = load_manifest(args.manifest.resolve())
    selected = _select_cases(cases, args)
    if args.list or args.dry_run:
        _print_discovery(selected, as_json=args.list)
        return 0
    if not selected:
        raise SystemExit("no benchmark cases matched the requested filters")
    if args.verify_only and args.build_only:
        raise SystemExit("--verify-only and --build-only are mutually exclusive")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    _validate_metadata_file(args.metadata_file)
    if args.historical_baseline:
        _load_historical_baseline(args.historical_baseline)
    comparison_document = _load_comparison_baseline(args.comparison_baseline)

    toolchains = detect_toolchains()
    harness = BenchmarkHarness(create_adapter_registry(toolchains), repository_root=REPOSITORY_ROOT)
    warmups = 1 if args.smoke else args.warmups
    samples = 2 if args.smoke else args.samples
    loops = 1 if args.smoke else args.loops
    target_ns = 1_000_000 if args.smoke else args.target_sample_duration_ns
    results: list[dict[str, object]] = []

    if args.build_dir:
        args.build_dir.mkdir(parents=True, exist_ok=True)
        return _run_with_build_dir(
            harness, selected, results, args.build_dir, args, warmups, samples, loops, target_ns,
            comparison_document,
        )
    with tempfile.TemporaryDirectory(prefix="s3bench-") as temporary:
        return _run_with_build_dir(
            harness, selected, results, Path(temporary), args, warmups, samples, loops, target_ns,
            comparison_document,
        )


def _run_with_build_dir(
    harness: BenchmarkHarness,
    cases: Sequence[Case],
    results: list[dict[str, object]],
    build_root: Path,
    args: argparse.Namespace,
    warmups: int,
    samples: int,
    loops: int | None,
    target_ns: int,
    comparison_document: list[dict[str, object]],
) -> int:
    failed = False
    for case in cases:
        case_dir = build_root / _case_directory(case)
        try:
            result = harness.run_case(
                case,
                build_dir=case_dir,
                warmups=warmups,
                samples=samples,
                loops=loops,
                target_sample_ns=target_ns,
                verify_only=args.verify_only,
                build_only=args.build_only,
            )
            result["runner_type"] = args.runner_type
            results.append(result)
        except AdapterUnavailable as error:
            results.append(
                unavailable_result(
                    case,
                    repository_root=REPOSITORY_ROOT,
                    reason=str(error),
                    runner_type=args.runner_type,
                )
            )
        except BenchmarkError as error:
            failed = True
            results.append(
                failed_result(
                    case,
                    repository_root=REPOSITORY_ROOT,
                    reason=f"functional failure: {error}",
                    artifact=getattr(error, "artifact", None),
                    observed_checksum=getattr(error, "observed_checksum", None),
                    runner_type=args.runner_type,
                )
            )
            if args.fail_fast:
                break

    _classify_current_results(results, comparison_document)
    if args.output_json:
        write_json(args.output_json, results)
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(
            render_performance_report(
                results,
                raw_result_path=args.output_json.name if args.output_json else "unavailable",
            ),
            encoding="utf-8",
            newline="\n",
        )
    comparisons = compare_results(
        results,
        reference_implementation=args.reference_implementation,
    )
    print(json.dumps({"results": results, "comparisons": comparisons}, indent=2, sort_keys=True, allow_nan=False))
    return 1 if failed else 0


def _select_cases(cases: Sequence[Case], args: argparse.Namespace) -> tuple[Case, ...]:
    def values(items: list[str] | None) -> set[str] | None:
        if not items:
            return None
        return {value for item in items for value in item.split(",") if value}

    return BenchmarkHarness({}, repository_root=REPOSITORY_ROOT).discover(
        cases,
        benchmark_ids=values(args.benchmark),
        categories=values(args.category),
        implementations=values(args.implementation),
        execution_modes=values(args.mode),
        optimization_modes=values(args.optimization),
    )


def _print_discovery(cases: Sequence[Case], *, as_json: bool) -> None:
    rows = [
        {
            "benchmark_id": case.benchmark_id,
            "implementation": case.implementation,
            "execution_mode": case.execution_mode,
            "optimization_mode": case.optimization_mode,
        }
        for case in cases
    ]
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        for row in rows:
            print(" | ".join(str(value) for value in row.values()))


def _validate_metadata_file(path: Path | None) -> None:
    if path is None:
        return
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise SystemExit("metadata file must contain a JSON object")
    forbidden = {"username", "hostname", "home_directory", "environment", "ip", "token"}
    if forbidden.intersection(document):
        raise SystemExit("metadata file contains forbidden private keys")


def _load_historical_baseline(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("baseline_format_version") != "1.0.0":
        raise SystemExit("unsupported historical baseline")
    return {
        "path": path.name,
        "classification": "NOT_COMPARABLE",
        "reason": "0.8 E2 lacks workload versions, raw timing protocol, and environment metadata",
    }


def _load_comparison_baseline(path: Path | None) -> list[dict[str, object]]:
    if path is None:
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1.0.0" or not isinstance(document.get("results"), list):
        raise SystemExit("comparison baseline is not an s3bench 1.0.0 document")
    return list(document["results"])


def _classify_current_results(
    results: list[dict[str, object]],
    baseline: Sequence[dict[str, object]],
) -> None:
    baseline_keys = {
        (
            item.get("benchmark_id"), item.get("workload_version"), item.get("input_id"),
            item.get("implementation"), item.get("execution_mode"), item.get("optimization_mode"),
        )
        for item in baseline
    }
    for result in results:
        if result.get("status") != "measured":
            result["comparability_classification"] = "NOT_COMPARABLE"
            continue
        if result.get("suite") == "portable" and result.get("benchmark_id") == "runtime.text.scan.v1" and result.get("implementation") == "s3":
            result["comparability_classification"] = "NOT_COMPARABLE"
            result["notes"].append("S3 static text is compile-time folded and has a different runtime timed region")
            continue
        key = (
            result.get("benchmark_id"), result.get("workload_version"), result.get("input_id"),
            result.get("implementation"), result.get("execution_mode"), result.get("optimization_mode"),
        )
        result["comparability_classification"] = "COMPARABLE" if (
            result.get("suite") == "portable" or key in baseline_keys
        ) else "PARTIALLY_COMPARABLE"


def _case_directory(case: Case) -> str:
    return "-".join(
        value.replace(".", "-").replace("=", "-")
        for value in case.identity
    )


if __name__ == "__main__":
    raise SystemExit(main())
