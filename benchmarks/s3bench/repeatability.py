"""Deterministic repeatability analysis for persisted s3bench runs."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Mapping

KEY_FIELDS = (
    "benchmark_id",
    "input_id",
    "measurement_scope",
    "implementation",
    "execution_mode",
    "optimization_mode",
    "phase",
)
STABLE_MAX_AMPLITUDE_PERCENT = 10.0
STABLE_MAX_MEDIAN_CV_PERCENT = 10.0
USABLE_MAX_AMPLITUDE_PERCENT = 20.0
USABLE_MAX_MEDIAN_CV_PERCENT = 20.0
NUMERIC_REL_TOLERANCE = 1e-9
NUMERIC_ABS_TOLERANCE = 1e-6


class RepeatabilityError(ValueError):
    """The persisted run set violates the repeatability contract."""


@dataclass
class _PublicationState:
    destination: Path
    prepared: Path | None = None
    backup: Path | None = None
    had_original: bool = False
    original_in_backup: bool = False
    published: bool = False


def publish_reports(
    json_text: str,
    markdown_text: str,
    json_path: Path,
    markdown_path: Path,
) -> list[str]:
    """Publish the two report files with rollback across both replacements."""
    json_destination = _canonical_output_path(json_path)
    markdown_destination = _canonical_output_path(markdown_path)
    if _same_output(json_destination, markdown_destination):
        raise RepeatabilityError(
            "--output-json and --output-markdown resolve to the same destination"
        )

    json_destination.parent.mkdir(parents=True, exist_ok=True)
    markdown_destination.parent.mkdir(parents=True, exist_ok=True)
    states = [
        _PublicationState(json_destination),
        _PublicationState(markdown_destination),
    ]
    try:
        states[0].prepared = _write_temporary(json_destination, json_text, ".json")
        states[1].prepared = _write_temporary(markdown_destination, markdown_text, ".md")

        for state in states:
            if state.destination.exists():
                state.had_original = True
                _reserve_backup(state)
                if state.backup is None:
                    raise ValueError(f"missing backup placeholder for {state.destination}")
                os.replace(state.destination, state.backup)
                state.original_in_backup = True

        for state in states:
            if state.prepared is None:
                raise ValueError(f"missing prepared report for {state.destination}")
            os.replace(state.prepared, state.destination)
            state.prepared = None
            state.published = True
    except (OSError, ValueError) as error:
        for state in reversed(states):
            if not state.published:
                continue
            try:
                state.destination.unlink(missing_ok=True)
                state.published = False
            except OSError:
                pass
        restoration_failures: list[tuple[Path, Path, OSError]] = []
        for state in states:
            if not state.original_in_backup or state.backup is None:
                continue
            try:
                os.replace(state.backup, state.destination)
            except OSError as restoration_error:
                restoration_failures.append(
                    (state.destination, state.backup, restoration_error)
                )
            else:
                state.original_in_backup = False
        safe_cleanup = [
            path
            for state in states
            for path in (state.prepared, state.backup)
            if path is not None and not (
                path == state.backup and state.original_in_backup
            )
        ]
        residual = _cleanup_paths(safe_cleanup)
        residual = _cleanup_paths(residual)
        message = f"could not publish both reports: {error}"
        for destination, backup, restoration_error in restoration_failures:
            message += (
                f"; rollback restoration failed for destination {destination}: "
                f"original preserved at {backup}: {restoration_error}"
            )
        if residual:
            message += "; could not remove: " + ", ".join(str(path) for path in residual)
        raise RepeatabilityError(message) from error
    else:
        residual = _cleanup_paths([
            state.backup
            for state in states
            if state.original_in_backup and state.backup is not None
        ])
        residual = _cleanup_paths(residual)
        return [f"could not remove backup: {path}" for path in residual]


def _canonical_output_path(path: Path) -> Path:
    return Path(os.path.normcase(os.path.normpath(str(path.resolve(strict=False)))))


def _same_output(first: Path, second: Path) -> bool:
    if first == second:
        return True
    try:
        return first.exists() and second.exists() and os.path.samefile(first, second)
    except OSError:
        return False


def _write_temporary(destination: Path, content: str, suffix: str) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=suffix, dir=destination.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return temporary


def _reserve_backup(state: _PublicationState) -> None:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{state.destination.name}.backup.",
        suffix="",
        dir=state.destination.parent,
    )
    state.backup = Path(name)
    os.close(descriptor)


def _cleanup_paths(paths: list[Path]) -> list[Path]:
    residual: list[Path] = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            residual.append(path)
    return residual


@dataclass(frozen=True)
class _Run:
    benchmark_dir: str
    run_dir: str
    document: dict[str, Any]


def analyze_root(root: Path, *, expected_runs: int = 3) -> dict[str, Any]:
    """Analyze a benchmark archive without executing any benchmark."""
    if expected_runs <= 0:
        raise RepeatabilityError("expected_runs must be positive")
    benchmark_root = _resolve_benchmark_root(root)
    runs = _load_runs(benchmark_root, expected_runs)
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for run in runs:
        results = run.document["results"]
        comparisons = run.document["comparisons"]
        result_map = _unique_map(results, "result", run)
        comparison_map = _unique_map(comparisons, "comparison", run)
        result_keys = set(result_map)
        comparison_keys = set(comparison_map)
        if result_keys != comparison_keys:
            missing_comparisons = sorted(result_keys - comparison_keys)
            missing_results = sorted(comparison_keys - result_keys)
            raise RepeatabilityError(
                f"result/comparison mismatch in {run.run_dir}: "
                f"missing_comparisons={missing_comparisons!r}, "
                f"missing_results={missing_results!r}"
            )
        for key in sorted(result_keys):
            result = result_map[key]
            comparison = comparison_map[key]
            _validate_row(result, comparison, run.run_dir)
            grouped.setdefault(key, []).append(
                {
                    "result": result,
                    "comparison": comparison,
                    "run": run.run_dir,
                    "source_document": run.document,
                }
            )

    measurements = [_measurement(key, rows) for key, rows in sorted(grouped.items())]
    for measurement in measurements:
        if len(measurement["runs"]) != expected_runs:
            raise RepeatabilityError(
                f"incomplete run set for {measurement['key']}: "
                f"expected {expected_runs}, got {len(measurement['runs'])}"
            )
    o1_o0 = _optimization_comparisons(measurements)
    counts = {
        "benchmarks": len({key[0] for key in grouped}),
        "runs": expected_runs,
        "results": len(measurements),
        "stable": sum(item["classification"] == "STABLE" for item in measurements),
        "usable": sum(item["classification"] == "USABLE" for item in measurements),
        "unstable": sum(item["classification"] == "UNSTABLE" for item in measurements),
        "conclusive": sum(item["classification"] == "CONCLUSIVE" for item in o1_o0),
        "inconclusive": sum(item["classification"] == "INCONCLUSIVE" for item in o1_o0),
    }
    return {
        "metadata": {
            "schema_version": "1.0.0",
            "expected_runs": expected_runs,
            "source_root": benchmark_root.name or ".",
            "classification_thresholds": {
                "stable_max_amplitude_percent": STABLE_MAX_AMPLITUDE_PERCENT,
                "stable_max_median_cv_percent": STABLE_MAX_MEDIAN_CV_PERCENT,
                "usable_max_amplitude_percent": USABLE_MAX_AMPLITUDE_PERCENT,
                "usable_max_median_cv_percent": USABLE_MAX_MEDIAN_CV_PERCENT,
            },
        },
        "summary": counts,
        "measurements": measurements,
        "comparisons": o1_o0,
        "warnings": _warnings(measurements, o1_o0),
    }


def write_analysis(document: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def render_analysis_markdown(document: Mapping[str, Any]) -> str:
    metadata = document["metadata"]
    summary = document["summary"]
    lines = [
        "# s3bench Repeatability Analysis",
        "",
        "Kernel measurements use time per loop (`median_ns_per_loop`). Process measurements use the complete process time per sample, also represented canonically as `median_ns_per_loop` with `loops_per_sample == 1`.",
        "Different measurement scopes must never be compared directly.",
        "",
        "## Summary",
        "",
        f"- Benchmarks: {summary['benchmarks']}",
        f"- Runs per key: {summary['runs']}",
        f"- Measurement keys: {summary['results']}",
        f"- Stable: {summary['stable']}; usable: {summary['usable']}; unstable: {summary['unstable']}",
        f"- O1 versus O0: {summary['conclusive']} conclusive; {summary['inconclusive']} inconclusive",
        "",
        "## Statistical limits",
        "",
        "| Classification | Amplitude | Median CV |",
        "| --- | ---: | ---: |",
        f"| STABLE | <= {metadata['classification_thresholds']['stable_max_amplitude_percent']}% | <= {metadata['classification_thresholds']['stable_max_median_cv_percent']}% |",
        f"| USABLE | <= {metadata['classification_thresholds']['usable_max_amplitude_percent']}% | <= {metadata['classification_thresholds']['usable_max_median_cv_percent']}% |",
        "| UNSTABLE | otherwise | otherwise |",
        "",
        "## Results by benchmark",
        "",
        _measurement_table(document["measurements"]),
        "",
        "## Kernel",
        "",
        _measurement_table([item for item in document["measurements"] if item["measurement_scope"] == "kernel"]),
        "",
        "## Process",
        "",
        _measurement_table([item for item in document["measurements"] if item["measurement_scope"] == "process"]),
        "",
        "## O1 versus O0",
        "",
        _comparison_table(document["comparisons"]),
        "",
        "## Conclusive comparisons",
        "",
        _comparison_table([item for item in document["comparisons"] if item["classification"] == "CONCLUSIVE"]),
        "",
        "## Inconclusive comparisons",
        "",
        _comparison_table([item for item in document["comparisons"] if item["classification"] == "INCONCLUSIVE"]),
        "",
        "## Unstable results",
        "",
        _measurement_table([item for item in document["measurements"] if item["classification"] == "UNSTABLE"]),
        "",
        "## Methodological warnings",
        "",
    ]
    warnings = document.get("warnings", [])
    lines.extend(f"- {warning}" for warning in warnings or ["None."])
    return "\n".join(lines) + "\n"


def _resolve_benchmark_root(root: Path) -> Path:
    candidate = root.resolve()
    nested = candidate / "benchmarks"
    if nested.is_dir():
        candidate = nested
    if not candidate.is_dir():
        raise RepeatabilityError(f"benchmark root does not exist: {root}")
    return candidate


def _load_runs(root: Path, expected_runs: int) -> list[_Run]:
    benchmark_dirs = sorted(path for path in root.iterdir() if path.is_dir())
    if not benchmark_dirs:
        raise RepeatabilityError("benchmark root contains no benchmark directories")
    runs: list[_Run] = []
    for benchmark_dir in benchmark_dirs:
        marker_path = benchmark_dir / "benchmark-id.txt"
        expected_id = _read_benchmark_marker(marker_path) if marker_path.exists() else None
        directory_ids: set[str] = set()
        run_dirs = sorted(path for path in benchmark_dir.iterdir() if path.is_dir() and path.name.startswith("run-"))
        if len(run_dirs) != expected_runs:
            raise RepeatabilityError(
                f"{benchmark_dir.name}: expected {expected_runs} runs, got {len(run_dirs)}"
            )
        for run_dir in run_dirs:
            results_path = run_dir / "results.json"
            stdout_path = run_dir / "results.stdout"
            stderr_path = run_dir / "results.stderr"
            if not results_path.is_file():
                raise RepeatabilityError(f"missing results.json: {results_path}")
            if stderr_path.is_file() and stderr_path.read_text(encoding="utf-8") != "":
                raise RepeatabilityError(f"stderr is not empty: {stderr_path}")
            try:
                document = json.loads(results_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RepeatabilityError(f"invalid JSON: {results_path}: {error}") from error
            if not isinstance(document, dict):
                raise RepeatabilityError(f"run document must be an object: {results_path}")
            if not isinstance(document.get("results"), list) or not document["results"]:
                raise RepeatabilityError(f"document has no results: {results_path}")
            if not isinstance(document.get("comparisons"), list) or not document["comparisons"]:
                raise RepeatabilityError(f"document has no comparisons: {results_path}")
            if stdout_path.is_file():
                try:
                    stdout_document = json.loads(stdout_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    raise RepeatabilityError(f"invalid stdout JSON: {stdout_path}: {error}") from error
                if stdout_document != document:
                    raise RepeatabilityError(f"JSON differs from stdout: {run_dir}")
            document = _canonical_document(document)
            document_id = _document_benchmark_id(document, run_dir)
            if expected_id is not None and document_id != expected_id:
                raise RepeatabilityError(
                    f"benchmark-id.txt disagrees with content in {run_dir}: "
                    f"expected {expected_id!r}, got {document_id!r}"
                )
            directory_ids.add(document_id)
            runs.append(_Run(benchmark_dir.name, run_dir.name, document))
        if expected_id is None and len(directory_ids) != 1:
            raise RepeatabilityError(
                f"benchmark IDs differ across runs in {benchmark_dir.name}: {sorted(directory_ids)!r}"
            )
    return runs


def _read_benchmark_marker(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RepeatabilityError(f"could not read benchmark marker: {path}") from error
    if not value or any(character.isspace() for character in value):
        raise RepeatabilityError(f"benchmark-id.txt must contain exactly one non-empty ID: {path}")
    return value


def _document_benchmark_id(document: Mapping[str, Any], run_dir: Path) -> str:
    result_ids = {
        row.get("benchmark_id")
        for row in document["results"]
        if isinstance(row, dict) and row.get("benchmark_id")
    }
    comparison_ids = {
        row.get("benchmark_id")
        for row in document["comparisons"]
        if isinstance(row, dict) and row.get("benchmark_id")
    }
    if len(result_ids) != 1 or len(comparison_ids) != 1 or result_ids != comparison_ids:
        raise RepeatabilityError(f"benchmark IDs disagree in {run_dir}")
    return str(next(iter(result_ids)))


def _canonical_document(document: dict[str, Any]) -> dict[str, Any]:
    """Preserve source fields while making row arrays order-independent."""
    canonical = dict(document)
    canonical["results"] = sorted(document["results"], key=_key)
    canonical["comparisons"] = sorted(document["comparisons"], key=_key)
    return canonical


def _safe_id(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(value)).strip("-")


def _unique_map(rows: list[Any], kind: str, run: _Run) -> dict[tuple[str, ...], dict[str, Any]]:
    mapping: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RepeatabilityError(f"{kind} must be an object in {run.run_dir}")
        key = _key(row)
        if key in mapping:
            raise RepeatabilityError(f"duplicate {kind} key in {run.run_dir}: {key}")
        mapping[key] = row
    return mapping


def _key(row: Mapping[str, Any]) -> tuple[str, ...]:
    missing = [field for field in KEY_FIELDS if field not in row]
    if missing:
        raise RepeatabilityError(f"missing join fields: {', '.join(missing)}")
    return tuple(str(row[field]) for field in KEY_FIELDS)


def _validate_row(result: Mapping[str, Any], comparison: Mapping[str, Any], run_dir: str) -> None:
    if result.get("status") != "measured":
        raise RepeatabilityError(f"result status is not measured in {run_dir}")
    if result.get("correctness_status") != "verified":
        raise RepeatabilityError(f"result correctness is not verified in {run_dir}")
    if result.get("observed_checksum") != result.get("expected_checksum"):
        raise RepeatabilityError(f"checksum mismatch in {run_dir}")
    scope = result.get("measurement_scope")
    median_ns = _number(result.get("median_ns"), "result.median_ns")
    loops = result.get("loops_per_sample")
    per_loop = _number(comparison.get("median_ns_per_loop"), "comparison.median_ns_per_loop")
    if scope == "kernel":
        if not isinstance(loops, int) or isinstance(loops, bool) or loops <= 0:
            raise RepeatabilityError(f"kernel loops_per_sample must be positive in {run_dir}")
        calculated = median_ns / loops
        if not math.isclose(calculated, per_loop, rel_tol=NUMERIC_REL_TOLERANCE, abs_tol=NUMERIC_ABS_TOLERANCE):
            raise RepeatabilityError(f"kernel per-loop mismatch in {run_dir}")
    elif scope == "process":
        if loops != 1:
            raise RepeatabilityError(f"process loops_per_sample must equal 1 in {run_dir}")
        if not math.isclose(median_ns, per_loop, rel_tol=NUMERIC_REL_TOLERANCE, abs_tol=NUMERIC_ABS_TOLERANCE):
            raise RepeatabilityError(f"process median mismatch in {run_dir}")
    else:
        raise RepeatabilityError(f"unknown measurement_scope in {run_dir}: {scope!r}")
    _number(result.get("coefficient_of_variation"), "result.coefficient_of_variation")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RepeatabilityError(f"{field} must be a finite number")
    return float(value)


def _measurement(key: tuple[str, ...], rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_loop = [row["comparison"]["median_ns_per_loop"] for row in rows]
    cvs = [row["result"]["coefficient_of_variation"] for row in rows]
    between_median = median(per_loop)
    amplitude = (max(per_loop) - min(per_loop)) / between_median * 100 if between_median else 0.0
    median_cv = median(cvs) * 100
    if amplitude <= STABLE_MAX_AMPLITUDE_PERCENT and median_cv <= STABLE_MAX_MEDIAN_CV_PERCENT:
        classification = "STABLE"
    elif amplitude <= USABLE_MAX_AMPLITUDE_PERCENT and median_cv <= USABLE_MAX_MEDIAN_CV_PERCENT:
        classification = "USABLE"
    else:
        classification = "UNSTABLE"
    return {
        "key": list(key),
        "benchmark_id": key[0],
        "input_id": key[1],
        "measurement_scope": key[2],
        "implementation": key[3],
        "execution_mode": key[4],
        "optimization_mode": key[5],
        "phase": key[6],
        "median_ns_per_loop": median(per_loop),
        "amplitude_percent": amplitude,
        "median_cv_percent": median_cv,
        "classification": classification,
        "runs": [
            {
                "run": row["run"],
                "result": row["result"],
                "comparison": row["comparison"],
                "source_document": row["source_document"],
            }
            for row in sorted(rows, key=lambda row: row["run"])
        ],
    }


def _optimization_comparisons(measurements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], dict[str, dict[str, Any]]] = {}
    for measurement in measurements:
        if measurement["implementation"] != "s3":
            continue
        if measurement["optimization_mode"] not in {"O0", "O1"}:
            continue
        group_key = (
            measurement["benchmark_id"], measurement["input_id"], measurement["measurement_scope"],
            measurement["execution_mode"], measurement["phase"],
        )
        groups.setdefault(group_key, {})[measurement["optimization_mode"]] = measurement
    output = []
    for key, modes in sorted(groups.items()):
        if "O0" not in modes or "O1" not in modes:
            continue
        o0, o1 = modes["O0"], modes["O1"]
        ratio = o1["median_ns_per_loop"] / o0["median_ns_per_loop"]
        change = (ratio - 1) * 100
        conclusive = (
            o0["classification"] != "UNSTABLE"
            and o1["classification"] != "UNSTABLE"
            and abs(change) > max(o0["amplitude_percent"], o1["amplitude_percent"])
        )
        output.append({
            "benchmark_id": key[0],
            "input_id": key[1],
            "measurement_scope": key[2],
            "execution_mode": key[3],
            "phase": key[4],
            "implementation": "s3",
            "optimization_modes": ["O0", "O1"],
            "o0_median_ns_per_loop": o0["median_ns_per_loop"],
            "o1_median_ns_per_loop": o1["median_ns_per_loop"],
            "ratio": ratio,
            "change_percent": change,
            "classification": "CONCLUSIVE" if conclusive else "INCONCLUSIVE",
        })
    return output


def _warnings(measurements: list[dict[str, Any]], comparisons: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if any(item["measurement_scope"] == "kernel" for item in measurements):
        warnings.append("Kernel statistics use median_ns_per_loop, never raw median_ns.")
    if any(item["measurement_scope"] == "process" for item in measurements):
        warnings.append("Process statistics represent complete process time per sample, not kernel time.")
    if any(item["classification"] == "INCONCLUSIVE" for item in comparisons):
        warnings.append("Inconclusive O1/O0 changes are not described as regressions or improvements.")
    return warnings


def _measurement_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Benchmark | Implementation | Scope | Optimization | Median/loop ns | Amplitude % | Median CV % | Classification |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['benchmark_id']} | {row['implementation']} | {row['measurement_scope']} | "
            f"{row['optimization_mode']} | {row['median_ns_per_loop']:.6f} | "
            f"{row['amplitude_percent']:.6f} | {row['median_cv_percent']:.6f} | {row['classification']} |"
        )
    return "\n".join(lines) if len(lines) > 2 else "No measurements."


def _comparison_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Benchmark | Scope | O0 ns/loop | O1 ns/loop | Ratio | Change % | Classification |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['benchmark_id']} | {row['measurement_scope']} | {row['o0_median_ns_per_loop']:.6f} | "
            f"{row['o1_median_ns_per_loop']:.6f} | {row['ratio']:.6f} | {row['change_percent']:.6f} | {row['classification']} |"
        )
    return "\n".join(lines) if len(lines) > 2 else "No comparisons."
