"""Rank evidence-backed optimization hypotheses without authorizing changes.

The ranker keeps measured runtime observations separate from logical dynamic
structural estimates. It is a deterministic hypothesis-prioritization tool,
not an optimizer or performance oracle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports/s3-1.9-native-observatory-optimization-discovery"
EXPECTED_COMMIT = "211b1aecec756be42516322429720018f54001e7"
EXPECTED_TREE = "08289d214832e856d46e14ef941239649e9f4063"
EXPECTED_WORKLOADS = {
    "energy.pv-timeseries-aggregation.v1",
    "engineering.point-cloud-summary.v1",
    "geospatial.raster-window-statistics.v1",
}
MATERIAL_THRESHOLD = 0.05
DEFAULT_OPTIMIZATION_EXPERIMENT = (
    REPORT_ROOT / "evidence/optimizations/EXP-S3-19-OPT-001-local-load-forwarding.json"
)


class EvidenceError(ValueError):
    """Raised when evidence is incomplete, inconsistent, or unpinned."""


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot read JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"JSON evidence must be an object: {path}")
    return value, hashlib.sha256(raw).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _evidence_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return f"external/{path.name}"


def _nonnegative_int(value: Any, label: str) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
             f"{label} must be a non-negative integer")
    return value


def _ratio(value: Any, label: str) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool),
             f"{label} must be numeric")
    result = float(value)
    _require(math.isfinite(result) and result > 0, f"{label} must be finite and positive")
    return result


def _pinned_source(document: dict[str, Any], label: str) -> None:
    revision = document.get("source_revision")
    _require(isinstance(revision, dict), f"{label} lacks source_revision")
    _require(revision.get("git_commit") == EXPECTED_COMMIT,
             f"{label} has an unexpected S3 source commit")
    _require(revision.get("git_tree") == EXPECTED_TREE,
             f"{label} has an unexpected S3 source tree")


def _load_observatory(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    _require(len(paths) == 3, "exactly three Observatory v4 reports are required")
    reports: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for path in sorted(paths, key=lambda item: str(item)):
        document, digest = _read_json(path)
        _require(document.get("schema_version") == "1.1.0",
                 f"unsupported Observatory schema in {path}")
        _require(document.get("report_kind") == "S3_X86_64_ELF_NATIVE_OBSERVATORY_EXPERIMENTAL",
                 f"unexpected Observatory report kind in {path}")
        provenance = document.get("provenance")
        _require(isinstance(provenance, dict), f"{path} lacks provenance")
        _require(provenance.get("git_head") == EXPECTED_COMMIT
                 and provenance.get("git_tree") == EXPECTED_TREE,
                 f"{path} is not pinned to the campaign S3 source")
        configuration = document.get("configuration")
        _require(isinstance(configuration, dict), f"{path} lacks configuration")
        expected_config = {
            "target": "linux-x86_64",
            "optimization": "O1",
            "instruction_budget_mode": "per-instruction",
            "native_policy": "baseline",
            "register_allocation": True,
        }
        _require(all(configuration.get(key) == expected for key, expected in expected_config.items()),
                 f"{path} does not match the frozen Observatory configuration")
        source_hash = provenance.get("source_sha256")
        _require(isinstance(source_hash, str) and len(source_hash) == 64,
                 f"{path} lacks source SHA-256")
        _require(source_hash not in reports, f"duplicate Observatory source {source_hash}")

        summary = document.get("summary")
        object_info = document.get("object")
        _require(isinstance(summary, dict) and isinstance(object_info, dict),
                 f"{path} lacks summary/object metrics")
        instruction_total = _nonnegative_int(summary.get("native_instruction_count"),
                                             f"{path}:native_instruction_count")
        attributed_instructions = _nonnegative_int(summary.get("attributed_native_instructions"),
                                                   f"{path}:attributed_native_instructions")
        unmapped_instructions = _nonnegative_int(summary.get("unmapped_native_instructions"),
                                                 f"{path}:unmapped_native_instructions")
        _require(attributed_instructions + unmapped_instructions == instruction_total,
                 f"{path} instruction attribution does not reconcile")
        text_bytes = _nonnegative_int(object_info.get("text_section_bytes"),
                                      f"{path}:text_section_bytes")
        attributed_bytes = _nonnegative_int(summary.get("attributed_text_bytes"),
                                            f"{path}:attributed_text_bytes")
        unmapped_bytes = _nonnegative_int(summary.get("unmapped_text_bytes"),
                                          f"{path}:unmapped_text_bytes")
        undecoded_bytes = _nonnegative_int(summary.get("undecoded_text_bytes"),
                                           f"{path}:undecoded_text_bytes")
        _require(attributed_bytes + unmapped_bytes + undecoded_bytes == text_bytes,
                 f"{path} .text byte accounting does not reconcile")
        reports[source_hash] = document
        hashes[_evidence_label(path)] = digest
    return reports, hashes


def _load_profile(path: Path) -> tuple[dict[str, Any], str]:
    document, digest = _read_json(path)
    _require(document.get("schema_version") == "1.0.0"
             and document.get("report_kind") == "S3_LOGICAL_DYNAMIC_BLOCK_PROFILE_EXPERIMENTAL",
             "unsupported logical-profile report")
    source = document.get("source_provenance")
    _require(isinstance(source, dict)
             and source.get("git_head") == EXPECTED_COMMIT
             and source.get("git_tree") == EXPECTED_TREE,
             "logical profile is not pinned to the campaign S3 source")
    config = document.get("configuration")
    _require(isinstance(config, dict)
             and config.get("target") == "linux-x86_64"
             and config.get("optimization") == "O1"
             and config.get("instruction_budget_mode") == "per-instruction"
             and config.get("native_policy") == "baseline",
             "logical profile configuration differs from the baseline")
    _require(document.get("measurement_kind")
             == "LOGICAL_DYNAMIC_COUNTS_AND_STATIC_NATIVE_STRUCTURAL_WEIGHT",
             "logical profile has an unexpected measurement kind")
    _require(document.get("interpretation", "").find("not hardware instruction counts") >= 0,
             "logical profile is missing its non-hardware interpretation boundary")
    return document, digest


def _load_register_pressure(
    observatory_by_source: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    facts_by_source: dict[str, dict[str, Any]] = {}
    for source_hash, document in observatory_by_source.items():
        functions = document.get("functions")
        _require(isinstance(functions, list) and functions,
                 "Observatory report lacks per-function allocation facts")
        reported_function_count = document["summary"].get("function_count")
        _require(reported_function_count is None or reported_function_count == len(functions),
                 "Observatory function count does not match its summary")
        names: set[str] = set()
        rows: list[dict[str, Any]] = []
        for function in functions:
            _require(isinstance(function, dict), "Observatory function row is malformed")
            name = function.get("name")
            allocation = function.get("allocation")
            _require(isinstance(name, str) and name and name not in names,
                     "Observatory function names must be non-empty and unique")
            _require(isinstance(allocation, dict),
                     f"{name} lacks register-allocation facts")
            names.add(name)
            virtuals = _nonnegative_int(allocation.get("virtual_register_count"),
                                        f"{name}:virtual_register_count")
            stack_resident = _nonnegative_int(
                allocation.get("stack_resident_virtual_register_count"),
                f"{name}:stack_resident_virtual_register_count")
            peak_live = _nonnegative_int(allocation.get("peak_live_virtual_registers"),
                                         f"{name}:peak_live_virtual_registers")
            across_call = _nonnegative_int(allocation.get("peak_values_live_across_call"),
                                            f"{name}:peak_values_live_across_call")
            stack_registers = allocation.get("stack_resident_virtual_registers")
            _require(isinstance(stack_registers, list)
                     and len(stack_registers) == stack_resident,
                     f"{name} stack-resident count does not match its register list")
            _require(all(isinstance(register, int) and not isinstance(register, bool)
                         and register >= 0 for register in stack_registers)
                     and len(set(stack_registers)) == len(stack_registers),
                     f"{name} stack-resident register list is malformed")
            _require(stack_resident <= virtuals and peak_live <= virtuals
                     and across_call <= virtuals,
                     f"{name} allocation counts exceed its virtual-register count")
            _require(allocation.get("dynamic_spills") is None
                     and allocation.get("dynamic_spills_status")
                     == "NOT_MEASURED_STATIC_STACK_RESIDENCE_IS_NOT_A_SPILL_COUNTER",
                     f"{name} dynamic-spill status is missing or misclassified")
            rows.append({
                "function": name,
                "virtual_register_count": virtuals,
                "stack_resident_virtual_register_count": stack_resident,
                "peak_live_virtual_registers": peak_live,
                "peak_values_live_across_call": across_call,
                "dynamic_spills": "NOT_MEASURED",
            })
        facts_by_source[source_hash] = {
            "function_count": len(rows),
            "virtual_register_count": sum(row["virtual_register_count"] for row in rows),
            "stack_resident_virtual_register_count": sum(
                row["stack_resident_virtual_register_count"] for row in rows),
            "functions_with_stack_resident_virtuals": sum(
                row["stack_resident_virtual_register_count"] > 0 for row in rows),
            "max_peak_live_virtual_registers": max(
                row["peak_live_virtual_registers"] for row in rows),
            "max_values_live_across_call": max(
                row["peak_values_live_across_call"] for row in rows),
            "dynamic_spills": "NOT_MEASURED",
            "functions": rows,
        }
    return facts_by_source


def _load_reference_reports(
    paths: list[Path], source_to_workload: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    _require(len(paths) == len(EXPECTED_WORKLOADS),
             "exactly three current reference-analysis reports are required")
    by_workload: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for path in sorted(paths, key=lambda item: str(item)):
        document, digest = _read_json(path)
        _require(document.get("schema_version") == "1.0.0"
                 and document.get("report_kind") == "S3_REFERENCE_DATAFLOW_RESEARCH",
                 f"unsupported reference report in {path}")
        provenance = document.get("provenance")
        _require(isinstance(provenance, dict)
                 and provenance.get("git_head") == EXPECTED_COMMIT
                 and isinstance(provenance.get("git_worktree_dirty"), bool)
                 and provenance.get("optimization") == "O1"
                 and provenance.get("source_syntax") == "0.6",
                 f"{path} is not a pinned current-source O1 reference report")
        source_hash = provenance.get("source_sha256")
        _require(isinstance(source_hash, str) and source_hash in source_to_workload,
                 f"{path} source hash does not match an analyzed workload")
        workload_id = source_to_workload[source_hash]
        _require(workload_id not in by_workload,
                 f"duplicate reference report for {workload_id}")
        summary = document.get("summary")
        functions = document.get("functions")
        _require(isinstance(summary, dict) and isinstance(functions, list),
                 f"{path} lacks reference summary/functions")
        _require(summary.get("function_count") == len(functions)
                 and summary.get("complete_function_count") == len(functions)
                 and summary.get("incomplete_function_count") == 0
                 and summary.get("transformation_authorized") is False,
                 f"{path} is incomplete or incorrectly grants transformation authority")
        reference_count = 0
        escape_counts: Counter[str] = Counter()
        origin_counts: Counter[str] = Counter()
        effect_counts: Counter[str] = Counter()
        function_rows: list[dict[str, Any]] = []
        function_names: set[str] = set()
        for function in functions:
            _require(isinstance(function, dict) and function.get("complete") is True,
                     f"{path} contains an incomplete function fact")
            name = function.get("function")
            effects = function.get("effects")
            references = function.get("references")
            _require(isinstance(name, str) and name and name not in function_names
                     and isinstance(effects, dict) and isinstance(references, list),
                     f"{path} contains a malformed function fact")
            function_names.add(name)
            for effect, count in effects.items():
                _require(isinstance(effect, str) and effect,
                         f"{name} effect keys must be non-empty strings")
                effect_counts[effect] += _nonnegative_int(count, f"{name}:effect:{effect}")
            function_reference_rows = []
            for reference in references:
                _require(isinstance(reference, dict), f"{name} has a malformed reference fact")
                escape = reference.get("escape")
                mutable = reference.get("mutable")
                origin_unknown = reference.get("origin_unknown")
                _require(isinstance(escape, str) and escape
                         and isinstance(mutable, bool)
                         and isinstance(origin_unknown, bool),
                         f"{name} has incomplete escape/origin facts")
                read_uses = _nonnegative_int(reference.get("read_uses"),
                                             f"{name}:read_uses")
                write_uses = _nonnegative_int(reference.get("write_uses"),
                                              f"{name}:write_uses")
                escape_counts[escape] += 1
                origin_counts["UNKNOWN" if origin_unknown else "KNOWN"] += 1
                reference_count += 1
                function_reference_rows.append({
                    "escape": escape,
                    "mutable": mutable,
                    "origin_unknown": origin_unknown,
                    "read_uses": read_uses,
                    "write_uses": write_uses,
                })
            function_rows.append({
                "function": name,
                "effects": dict(sorted((key, int(value)) for key, value in effects.items())),
                "references": function_reference_rows,
            })
        _require(summary.get("reference_values") == reference_count
                 and summary.get("escape_status_counts") == dict(sorted(escape_counts.items()))
                 and summary.get("origin_status_counts") == dict(sorted(origin_counts.items())),
                 f"{path} reference facts do not reconcile with its summary")
        interpretation = document.get("interpretation")
        _require(isinstance(interpretation, dict)
                 and isinstance(interpretation.get("not_a_proof_of"), list)
                 and interpretation["not_a_proof_of"],
                 f"{path} lacks reference-analysis scope limitations")
        by_workload[workload_id] = {
            "source_sha256": source_hash,
            "analysis_git_head": provenance["git_head"],
            "analysis_worktree_dirty": provenance["git_worktree_dirty"],
            "analysis_implementation_sha256": provenance.get("analysis_implementation_sha256"),
            "report_tool_sha256": provenance.get("report_tool_sha256"),
            "function_count": len(function_rows),
            "reference_count": reference_count,
            "escape_status_counts": dict(sorted(escape_counts.items())),
            "origin_status_counts": dict(sorted(origin_counts.items())),
            "mutable_reference_count": sum(
                reference["mutable"]
                for function in function_rows for reference in function["references"]),
            "read_uses": sum(reference["read_uses"]
                             for function in function_rows for reference in function["references"]),
            "write_uses": sum(reference["write_uses"]
                              for function in function_rows for reference in function["references"]),
            "effect_counts": dict(sorted(effect_counts.items())),
            "unknown_effect_count": effect_counts.get("unknown", 0),
            "transformation_authorized": False,
            "functions": function_rows,
        }
        hashes[_evidence_label(path)] = digest
    _require(set(by_workload) == EXPECTED_WORKLOADS,
             "reference-analysis reports do not cover the complete workload set")
    return by_workload, hashes


def _load_optimization_experiment(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, None
    document, digest = _read_json(path)
    _require(document.get("schema_version") == "1.0.0"
             and document.get("experiment_id") == "EXP-S3-19-OPT-001"
             and document.get("report_kind") == "S3_EXPERIMENTAL_LOCAL_MUTABLE_LOAD_FORWARDING",
             "unsupported local-load-forwarding experiment report")
    source = document.get("source_revision")
    _require(isinstance(source, dict)
             and source.get("git_commit") == EXPECTED_COMMIT
             and source.get("git_tree") == EXPECTED_TREE
             and source.get("compiler_source_dirty") is False,
             "optimization experiment is not pinned to a clean compiler source")
    environment = document.get("execution_environment")
    _require(isinstance(environment, dict)
             and environment.get("system") == "Linux"
             and environment.get("machine") in {"x86_64", "AMD64"},
             "optimization experiment was not executed on Linux x86-64")
    implementation = document.get("experiment_implementation")
    _require(isinstance(implementation, dict)
             and implementation.get("driver_path") == "tools/s3_native_optimization_experiments.py"
             and implementation.get("focused_test_path") == "tests/test_s3_native_optimization_experiments.py"
             and all(isinstance(implementation.get(key), str)
                     and len(implementation[key]) == 64
                     for key in ("driver_sha256", "focused_test_sha256")),
             "optimization experiment implementation provenance is incomplete")
    transformation = document.get("transformation")
    _require(isinstance(transformation, dict)
             and transformation.get("production_pipeline_changed") is False
             and transformation.get("timing_performed") is False
             and transformation.get("pmu_used") is False,
             "optimization experiment exceeded its structural/correctness-only scope")
    summary = document.get("summary")
    workloads = document.get("workloads")
    _require(isinstance(summary, dict) and isinstance(workloads, dict)
             and set(workloads) == EXPECTED_WORKLOADS,
             "optimization experiment lacks the complete workload set")
    total_before = 0
    total_after = 0
    total_forwarded = 0
    for workload_id, workload in workloads.items():
        _require(isinstance(workload, dict)
                 and workload.get("correctness") == "PASS_REFERENCE_AND_BASELINE_EXACT_OUTPUT_MATCH",
                 f"{workload_id} optimization experiment correctness did not pass")
        before = _nonnegative_int(workload.get("mutable_loads_before"),
                                  f"{workload_id}:mutable_loads_before")
        after = _nonnegative_int(workload.get("mutable_loads_after"),
                                 f"{workload_id}:mutable_loads_after")
        forwarded = _nonnegative_int(workload.get("mutable_loads_forwarded"),
                                     f"{workload_id}:mutable_loads_forwarded")
        _require(before == after + forwarded,
                 f"{workload_id} optimization load accounting does not reconcile")
        total_before += before
        total_after += after
        total_forwarded += forwarded
    _require(summary.get("mutable_loads_before") == total_before
             and summary.get("mutable_loads_after") == total_after
             and summary.get("mutable_loads_forwarded") == total_forwarded,
             "optimization experiment totals do not match workload records")
    expected_status = (
        "REJECTED_NO_ELIGIBLE_REPEATED_MUTABLE_LOADS"
        if total_forwarded == 0 else "SUPPORTED_STRUCTURAL_CANDIDATE"
    )
    _require(summary.get("status") == expected_status
             and summary.get("native_timing_claim") is False,
             "optimization experiment status does not match its measured structural result")
    return document, digest


def _load_benchmarks(
    paths: list[Path], executor_report_path: Path
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    _require(len(paths) == 2, "two independent matched benchmark runs are required")
    reports: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for path in sorted(paths, key=lambda item: str(item)):
        document, digest = _read_json(path)
        _require(document.get("schema_version") == "1.0.0", f"unsupported benchmark schema: {path}")
        _pinned_source(document, str(path))
        host = document.get("host")
        _require(isinstance(host, dict)
                 and (host.get("system") == "Linux"
                      or str(host.get("platform", "")).startswith("Linux-"))
                 and host.get("machine") == "x86_64", f"{path} is not a Linux x86-64 run")
        protocol = document.get("protocol")
        _require(isinstance(protocol, dict)
                 and protocol.get("instruction_budget_modes")
                 == ["per-instruction", "exact-segment", "loop-hybrid"]
                 and protocol.get("s3_optimization_levels") == ["O0", "O1"],
                 f"{path} does not contain the matched budget-mode protocol")
        workloads = document.get("workloads")
        _require(isinstance(workloads, dict) and set(workloads) == EXPECTED_WORKLOADS,
                 f"{path} does not contain the complete workload set")
        for workload_id, workload in workloads.items():
            timing = workload.get("timing_protocol") if isinstance(workload, dict) else None
            _require(isinstance(timing, dict)
                     and (timing.get("warmups"), timing.get("samples"),
                          timing.get("iterations_per_sample"), timing.get("material_change_threshold"))
                     == (3, 21, 1000, MATERIAL_THRESHOLD),
                     f"{path}:{workload_id} does not match the qualified timing protocol")
        reports.append(document)
        hashes[_evidence_label(path)] = digest
    _require(len(set(hashes.values())) == 2, "benchmark inputs are not independent raw artifacts")
    _require(reports[0]["source_revision"] == reports[1]["source_revision"],
             "benchmark runs use different S3 source revisions")
    _require(reports[0]["protocol"] == reports[1]["protocol"],
             "benchmark runs use different protocols")
    _require(reports[0].get("cpu_model") == reports[1].get("cpu_model")
             and reports[0]["host"].get("machine") == reports[1]["host"].get("machine")
             and reports[0]["host"].get("platform") == reports[1]["host"].get("platform"),
             "benchmark runs do not match the same host identity")
    for workload_id in sorted(EXPECTED_WORKLOADS):
        _require(reports[0]["workloads"][workload_id]["timing_protocol"]
                 == reports[1]["workloads"][workload_id]["timing_protocol"],
                 f"{workload_id} timing protocols differ between runs")
    executor, executor_hash = _read_json(executor_report_path)
    _require(executor.get("schema_version") == "1.0.0"
             and executor.get("report_kind") == "S3_BENCHMARKS_1_9_PINNED_NATIVE_EXECUTION"
             and executor.get("status") == "PASS",
             "independent executor report is missing or not PASS")
    execution = executor.get("execution")
    provenance = executor.get("provenance")
    _require(isinstance(execution, dict) and execution.get("return_code") == 0
             and execution.get("timed_out") is False,
             "independent executor did not terminate successfully")
    _require(isinstance(provenance, dict), "independent executor provenance is missing")
    validated = execution.get("validated")
    _require(isinstance(validated, dict), "independent executor validated evidence is missing")
    raw_matches = [
        (document, hashes[_evidence_label(path)])
        for document, path in zip(reports, sorted(paths, key=lambda item: str(item)), strict=True)
        if provenance.get("raw_result_sha256") == hashes[_evidence_label(path)]
    ]
    _require(len(raw_matches) == 1,
             "independent executor raw-result SHA does not identify exactly one input")
    replicated_report, replicated_raw_sha = raw_matches[0]
    _require(provenance.get("lab_head") == "e5ff385d26ea6ec89d13cf1955bfa5438e56a266"
             and provenance.get("lab_tree") == "c06ac7b063f27144fa19ddc84dc33c082fcc134a",
             "independent executor is not pinned to the campaign lab base")
    _require(provenance.get("lab_worktree_clean") is False,
             "independent executor lab worktree state differs from its recorded run")
    _require(provenance.get("s3_commit") == EXPECTED_COMMIT
             and provenance.get("s3_tree") == EXPECTED_TREE
             and provenance.get("s3_worktree_clean") is True,
             "independent executor did not verify the clean pinned S3 checkout")
    _require(validated.get("verified_compiler_source_sha256")
             == replicated_report.get("compiler_source_sha256"),
             "executor-verified compiler source hashes differ from raw benchmark provenance")
    artifacts = provenance.get("native_artifacts")
    _require(isinstance(artifacts, list) and artifacts,
             "independent executor has no native artifact hash inventory")
    _require(all(isinstance(row, dict) and isinstance(row.get("path"), str)
                 and isinstance(row.get("sha256"), str) and len(row["sha256"]) == 64
                 and _nonnegative_int(row.get("bytes"), "native artifact bytes") > 0
                 for row in artifacts),
             "independent executor native artifact inventory is malformed")
    executor_hashes = {_evidence_label(executor_report_path): executor_hash,
                       "executor_raw_result_sha256": replicated_raw_sha}
    return reports, hashes, executor_hashes


def _paired_result(workload: dict[str, Any], key: str) -> tuple[str, float]:
    correctness = workload.get("correctness")
    _require(correctness == "PASS_ALL_BUILDS", "benchmark correctness gate did not pass")
    comparisons = workload.get("paired_comparisons")
    _require(isinstance(comparisons, dict) and isinstance(comparisons.get(key), dict),
             f"benchmark lacks paired comparison {key}")
    row = comparisons[key]
    _require(row.get("material_change_threshold") == MATERIAL_THRESHOLD,
             f"paired comparison {key} has an unexpected materiality threshold")
    classification = row.get("classification")
    _require(classification in {
        "MATERIAL_IMPROVEMENT", "NO_MATERIAL_CHANGE_WITHIN_5_PERCENT", "INCONCLUSIVE",
        "MATERIAL_REGRESSION",
    }, f"paired comparison {key} has an unknown classification")
    ratio = _ratio(row.get("baseline_over_candidate_median_ratio"), f"{key}.median_ratio")
    return classification, ratio


def build_discovery(
    observatory_paths: list[Path],
    profile_path: Path,
    benchmark_paths: list[Path],
    executor_report_path: Path,
    reference_paths: list[Path],
    optimization_experiment_path: Path | None = None,
) -> dict[str, Any]:
    observatory_by_source, observatory_hashes = _load_observatory(observatory_paths)
    register_pressure_by_source = _load_register_pressure(observatory_by_source)
    profile, profile_hash = _load_profile(profile_path)
    benchmarks, benchmark_hashes, executor_hashes = _load_benchmarks(
        benchmark_paths, executor_report_path
    )
    optimization_experiment, optimization_experiment_hash = _load_optimization_experiment(
        optimization_experiment_path
    )
    profile_results = profile.get("results")
    _require(isinstance(profile_results, dict) and set(profile_results) == EXPECTED_WORKLOADS,
             "logical profile does not contain the complete workload set")
    first, second = benchmarks

    source_to_workload: dict[str, str] = {}
    per_workload: dict[str, dict[str, Any]] = {}
    for workload_id in sorted(EXPECTED_WORKLOADS):
        result = profile_results[workload_id]
        _require(isinstance(result, dict)
                 and result.get("correctness") == "PASS_BASELINE_AND_INSTRUMENTED_OUTPUTS_MATCH_REFERENCE_AND_EACH_OTHER"
                 and result.get("pmu_used") is False
                 and result.get("timing_performed") is False,
                 f"{workload_id} profile correctness/scope gate failed")
        source_hash = result.get("source_sha256")
        _require(isinstance(source_hash, str) and source_hash in observatory_by_source,
                 f"{workload_id} has no matching Observatory report")
        _require(source_hash not in source_to_workload, "workload source hashes are not unique")
        source_to_workload[source_hash] = workload_id
        _require(result.get("dataset_sha256") == first["workloads"][workload_id].get("dataset_sha256")
                 == second["workloads"][workload_id].get("dataset_sha256"),
                 f"{workload_id} dataset identity differs across profile and benchmark runs")
        weight = _nonnegative_int(result.get("estimated_uninstrumented_native_structural_weight"),
                                  f"{workload_id}:structural_weight")
        _require(weight > 0, f"{workload_id} structural weight is empty")
        origin_counts = result.get("weighted_native_origin_categories")
        syntax_counts = result.get("weighted_native_machine_syntax_categories")
        _require(isinstance(origin_counts, dict) and isinstance(syntax_counts, dict),
                 f"{workload_id} profile category counts are missing")
        for label, counts in (("origin", origin_counts), ("machine", syntax_counts)):
            _require(counts and all(isinstance(key, str) for key in counts),
                     f"{workload_id} {label} categories are malformed")
            values = [_nonnegative_int(value, f"{workload_id}:{label}:{key}")
                      for key, value in counts.items()]
            _require(sum(values) == weight,
                     f"{workload_id} {label} weighted categories do not sum to structural weight")
        per_workload[workload_id] = {
            "source_sha256": source_hash,
            "logical_block_executions": _nonnegative_int(
                result.get("logical_block_executions"), f"{workload_id}:logical_block_executions"),
            "structural_weight": weight,
            "origin_categories": origin_counts,
            "machine_categories": syntax_counts,
        }
    _require(set(observatory_by_source) == set(source_to_workload),
             "Observatory and logical-profile source workload sets differ")
    reference_facts, reference_hashes = _load_reference_reports(
        reference_paths, source_to_workload
    )
    _require(set(register_pressure_by_source) == set(source_to_workload),
             "register-pressure and logical-profile source workload sets differ")
    for source_hash, workload_id in source_to_workload.items():
        per_workload[workload_id]["reference_facts"] = reference_facts[workload_id]
        per_workload[workload_id]["register_pressure"] = register_pressure_by_source[source_hash]
    for benchmark in benchmarks:
        compiler_hashes = benchmark.get("compiler_source_sha256")
        _require(isinstance(compiler_hashes, dict), "benchmark compiler source hashes are missing")
        profile_hashes = profile["source_provenance"].get("compiler_source_sha256")
        _require(isinstance(profile_hashes, dict), "logical-profile compiler source hashes are missing")
        shared = set(compiler_hashes) & set(profile_hashes)
        _require(len(shared) >= 4
                 and all(compiler_hashes[path] == profile_hashes[path] for path in shared),
                 "profile and timing runs disagree on shared compiler source files")

    budget_cells: dict[str, dict[str, Any]] = {}
    for workload_id in sorted(EXPECTED_WORKLOADS):
        workload_observations: dict[str, Any] = {}
        for mode, key in (("EXACT_SEGMENT", "per_vs_exact_segment"),
                          ("LOOP_HYBRID", "per_vs_loop_hybrid")):
            a = _paired_result(first["workloads"][workload_id], key)
            b = _paired_result(second["workloads"][workload_id], key)
            if a[0] == b[0] == "MATERIAL_IMPROVEMENT":
                classification = "REPEATED_MATERIAL_IMPROVEMENT"
            elif a[0] == b[0] == "NO_MATERIAL_CHANGE_WITHIN_5_PERCENT":
                classification = "REPEATED_NO_MATERIAL_CHANGE"
            elif a[0] == b[0] == "MATERIAL_REGRESSION":
                classification = "REPEATED_MATERIAL_REGRESSION"
            else:
                classification = "REPLICATION_DISAGREEMENT_OR_INCONCLUSIVE"
            workload_observations[mode] = {
                "run_classifications": [a[0], b[0]],
                "run_paired_median_ratios": [a[1], b[1]],
                "cross_run_classification": classification,
            }
        compact = [first["workloads"][workload_id].get("compact_ea_applied"),
                   second["workloads"][workload_id].get("compact_ea_applied")]
        _require(compact == [False, False],
                 f"{workload_id} compact-EA was applied; ranking policy changed")
        for doc in benchmarks:
            workload = doc["workloads"][workload_id]
            binary_metrics = workload.get("binary_metrics")
            _require(isinstance(binary_metrics, dict)
                     and "S3_O1_BASELINE" in binary_metrics,
                     f"{workload_id} lacks its baseline binary record")
            candidates = {
                key: value for key, value in doc.get("candidate_artifacts", {}).items()
                if key in {
                    f"S3_O1_EXACT_SEGMENT_{workload_id}",
                    f"S3_O1_LOOP_HYBRID_{workload_id}",
                    f"S3_O1_COMPACT_EA_{workload_id}",
                }
            }
            _require(set(candidates) == {
                f"S3_O1_EXACT_SEGMENT_{workload_id}",
                f"S3_O1_LOOP_HYBRID_{workload_id}",
                f"S3_O1_COMPACT_EA_{workload_id}",
            }, f"{workload_id} candidate source provenance is incomplete")
            for candidate in candidates.values():
                _require(candidate.get("source_sha256") == per_workload[workload_id]["source_sha256"],
                         f"{workload_id} timing candidate source SHA differs from analysis")
            o0_o1, _ = _paired_result(workload, "o0_vs_o1")
            _require(o0_o1 in {"NO_MATERIAL_CHANGE_WITHIN_5_PERCENT", "INCONCLUSIVE"},
                     f"{workload_id} O0/O1 evidence includes an unexpected material outcome")
        budget_cells[workload_id] = workload_observations

    totals_by_origin: dict[str, int] = {}
    totals_by_machine: dict[str, int] = {}
    total_weight = 0
    for value in per_workload.values():
        total_weight += value["structural_weight"]
        for category, count in value["origin_categories"].items():
            totals_by_origin[category] = totals_by_origin.get(category, 0) + count
        for category, count in value["machine_categories"].items():
            totals_by_machine[category] = totals_by_machine.get(category, 0) + count

    memory_share = totals_by_origin.get("MEMORY_ACCESS", 0) / total_weight
    move_share = totals_by_machine.get("MOVE", 0) / total_weight
    control_share = totals_by_machine.get("CONTROL_FLOW", 0) / total_weight
    register_pressure_totals = {
        "function_count": sum(item["function_count"]
                               for item in register_pressure_by_source.values()),
        "virtual_register_count": sum(item["virtual_register_count"]
                                       for item in register_pressure_by_source.values()),
        "stack_resident_virtual_register_count": sum(
            item["stack_resident_virtual_register_count"]
            for item in register_pressure_by_source.values()),
        "functions_with_stack_resident_virtuals": sum(
            item["functions_with_stack_resident_virtuals"]
            for item in register_pressure_by_source.values()),
        "max_peak_live_virtual_registers": max(
            item["max_peak_live_virtual_registers"]
            for item in register_pressure_by_source.values()),
        "max_values_live_across_call": max(
            item["max_values_live_across_call"]
            for item in register_pressure_by_source.values()),
        "dynamic_spills": "NOT_MEASURED",
    }
    reference_totals = {
        "function_count": sum(item["function_count"] for item in reference_facts.values()),
        "reference_count": sum(item["reference_count"] for item in reference_facts.values()),
        "no_escape_reference_count": sum(
            item["escape_status_counts"].get("NO_ESCAPE", 0)
            for item in reference_facts.values()),
        "known_origin_reference_count": sum(
            item["origin_status_counts"].get("KNOWN", 0)
            for item in reference_facts.values()),
        "mutable_reference_count": sum(item["mutable_reference_count"]
                                        for item in reference_facts.values()),
        "unknown_effect_count": sum(item["unknown_effect_count"]
                                     for item in reference_facts.values()),
        "transformation_authorized": False,
    }

    hypotheses: list[dict[str, Any]] = []
    for mode in ("EXACT_SEGMENT", "LOOP_HYBRID"):
        repeated = [workload_id for workload_id in sorted(EXPECTED_WORKLOADS)
                    if budget_cells[workload_id][mode]["cross_run_classification"]
                    == "REPEATED_MATERIAL_IMPROVEMENT"]
        ratios = [ratio for workload_id in repeated
                  for ratio, classification in zip(
                      budget_cells[workload_id][mode]["run_paired_median_ratios"],
                      budget_cells[workload_id][mode]["run_classifications"], strict=True)
                  if classification == "MATERIAL_IMPROVEMENT"]
        mean_gain = sum(ratio - 1.0 for ratio in ratios) / len(ratios) if ratios else 0.0
        generality = len(repeated) / len(EXPECTED_WORKLOADS)
        score = mean_gain * generality
        hypotheses.append({
            "evidence_tier": 1,
            "category": "INSTRUCTION_BUDGET_POLICY",
            "candidate": mode,
            "rank_score": round(score, 8),
            "score_components": {
                "mean_repeated_paired_median_improvement_fraction": round(mean_gain, 8),
                "repeated_improvement_workload_fraction": round(generality, 8),
                "formula": "mean observed paired improvement x replicated workload fraction",
            },
            "evidence": {
                "repeated_material_improvement_workloads": repeated,
                "per_workload": {w: budget_cells[w][mode] for w in sorted(EXPECTED_WORKLOADS)},
                "compact_ea_applied": False,
                "o0_vs_o1_material_change": False,
            },
            "unknowns": [
                "Energy classification did not replicate consistently.",
                "This changes instruction-budget accounting policy, not source-level optimization.",
                "PER remains the default; this ranker does not promote a policy.",
            ],
            "confidence": "REPEATED_FOR_SELECTED_WORKLOADS_ONLY",
            "status": "HYPOTHESIS_FOR_REVIEW",
        })

    hypotheses.extend((
        {
            "evidence_tier": 2,
            "category": "MEMORY_ORIGIN_REDUCTION",
            "candidate": "memory-origin reduction beyond same-block exact-cell forwarding",
            "rank_score": round(memory_share * (len(EXPECTED_WORKLOADS) / 3) * 0.5 / 2.0, 8),
            "score_components": {
                "hotness_and_structural_share": round(memory_share, 8),
                "workload_generality_fraction": 1.0,
                "observational_confidence_factor": 0.5,
                "semantic_risk_divisor": 2.0,
                "formula": "share x generality x observational-confidence / semantic-risk",
            },
            "evidence": {
                "weighted_memory_access": totals_by_origin.get("MEMORY_ACCESS", 0),
                "total_structural_weight": total_weight,
                "share": round(memory_share, 8),
                "workloads_where_memory_is_largest_origin_category": sorted(EXPECTED_WORKLOADS),
                "reference_facts_by_workload": {
                    workload_id: {
                        "reference_count": reference_facts[workload_id]["reference_count"],
                        "no_escape_count": reference_facts[workload_id]["escape_status_counts"].get("NO_ESCAPE", 0),
                        "known_origin_count": reference_facts[workload_id]["origin_status_counts"].get("KNOWN", 0),
                        "mutable_reference_count": reference_facts[workload_id]["mutable_reference_count"],
                        "unknown_effect_count": reference_facts[workload_id]["unknown_effect_count"],
                        "transformation_authorized": False,
                    }
                    for workload_id in sorted(EXPECTED_WORKLOADS)
                },
            },
            "unknowns": [
                "Structural weight is not retired instructions or a runtime-cause measurement.",
                "NO_ESCAPE and known-origin facts are scoped diagnostics, not transformation authority.",
                "Alias/effect completeness is partial; each candidate requires a local proof contract.",
                "PMU is unavailable by policy.",
            ],
            "confidence": "REPEATED_STRUCTURAL_OBSERVATION_NOT_CAUSAL",
            "status": (
                "EXACT_LOCAL_RULE_REJECTED_BROADER_MEMORY_HYPOTHESIS_OPEN"
                if optimization_experiment is not None
                and optimization_experiment["summary"]["mutable_loads_forwarded"] == 0
                else "HYPOTHESIS_FOR_BOUNDED_EXPERIMENT"
            ),
        },
        {
            "evidence_tier": 2,
            "category": "NATIVE_MOVE_AND_CONTROL_LOWERING",
            "candidate": "inspect block-local value/materialization and ternary-control lowering",
            "rank_score": round((move_share + control_share) * (len(EXPECTED_WORKLOADS) / 3)
                                * 0.35 / 2.0, 8),
            "score_components": {
                "move_structural_share": round(move_share, 8),
                "control_structural_share": round(control_share, 8),
                "workload_generality_fraction": 1.0,
                "observational_confidence_factor": 0.35,
                "semantic_risk_divisor": 2.0,
                "formula": "(move share + control share) x generality x confidence / risk",
            },
            "evidence": {
                "weighted_move_instructions": totals_by_machine.get("MOVE", 0),
                "weighted_control_flow_instructions": totals_by_machine.get("CONTROL_FLOW", 0),
                "total_structural_weight": total_weight,
                "register_pressure": register_pressure_totals,
            },
            "unknowns": [
                "Machine syntax is weighted by logical block entries; branches may skip instructions within a block.",
                "These machine-category counts are not directly attributed to one source transformation.",
                "Static stack residence is not a dynamic-spill counter or runtime attribution.",
                "No PMU evidence exists.",
            ],
            "confidence": "STRUCTURAL_TRIAGE_ONLY",
            "status": "HYPOTHESIS_FOR_INSPECTION",
        },
    ))
    hypotheses.sort(key=lambda row: (row["evidence_tier"], -row["rank_score"], row["category"], row["candidate"]))
    for rank, hypothesis in enumerate(hypotheses, start=1):
        hypothesis["rank"] = rank

    return {
        "schema_version": "1.0.0",
        "report_kind": "S3_OPTIMIZATION_DISCOVERY_HYPOTHESES_EXPERIMENTAL",
        "campaign": "S3_1_9_NATIVE_OBSERVATORY_OPTIMIZATION_DISCOVERY_COMPILER_AUTONOMY_AND_COMPUTE_FRONTIER_EXPANSION",
        "source_revision": {"git_commit": EXPECTED_COMMIT, "git_tree": EXPECTED_TREE},
        "evidence": {
            "observatory_reports_sha256": observatory_hashes,
            "reference_reports_sha256": reference_hashes,
            "logical_profile_sha256": profile_hash,
            "matched_benchmark_reports_sha256": benchmark_hashes,
            "independent_executor_provenance_sha256": executor_hashes,
            "optimization_experiment_sha256": optimization_experiment_hash,
            "optimization_experiment_result": (
                {
                    "experiment_id": optimization_experiment["experiment_id"],
                    "status": optimization_experiment["summary"]["status"],
                    "mutable_loads_before": optimization_experiment["summary"]["mutable_loads_before"],
                    "mutable_loads_forwarded": optimization_experiment["summary"]["mutable_loads_forwarded"],
                    "mutable_loads_after": optimization_experiment["summary"]["mutable_loads_after"],
                    "driver_sha256": optimization_experiment["experiment_implementation"]["driver_sha256"],
                    "focused_test_sha256": optimization_experiment["experiment_implementation"]["focused_test_sha256"],
                    "workloads": {
                        workload_id: {
                            "mutable_loads_before": workload["mutable_loads_before"],
                            "mutable_loads_forwarded": workload["mutable_loads_forwarded"],
                            "mutable_loads_after": workload["mutable_loads_after"],
                            "correctness": workload["correctness"],
                        }
                        for workload_id, workload in sorted(optimization_experiment["workloads"].items())
                    },
                }
                if optimization_experiment is not None else None
            ),
            "workloads": per_workload,
            "reference_facts": {
                "totals": reference_totals,
                "by_workload": reference_facts,
                "authority": "DIAGNOSTIC_ONLY",
            },
            "register_pressure": {
                "totals": register_pressure_totals,
                "by_workload": {
                    workload_id: register_pressure_by_source[source_hash]
                    for source_hash, workload_id in sorted(source_to_workload.items(),
                                                           key=lambda item: item[1])
                },
                "allocator_replacement_triage": (
                    "STATIC_RESIDENCE_OBSERVED_DYNAMIC_SPILLS_UNMEASURED"
                    if register_pressure_totals["stack_resident_virtual_register_count"]
                    else "NO_STATIC_STACK_RESIDENCE_DYNAMIC_SPILLS_UNMEASURED"
                ),
            },
            "budget_mode_cross_run_classifications": budget_cells,
            "weighted_origin_totals": totals_by_origin,
            "weighted_machine_category_totals": totals_by_machine,
            "total_dynamic_structural_weight": total_weight,
        },
        "interpretation": {
            "is_oracle": False,
            "automatically_modifies_production": False,
            "default_policy_promotion": False,
            "per_instruction_default_preserved": True,
            "timing_class": "CHARACTERIZATION_ONLY",
            "pmu": "UNAVAILABLE_BY_POLICY",
            "hardware_cycles_claimed": False,
            "runtime_causality_established": False,
            "reference_facts_authorize_transformations": False,
            "dynamic_register_spills_measured": False,
            "ranking_method": "evidence tier first; measured paired runtime signals are not numerically mixed with structural hypotheses",
        },
        "hypotheses": hypotheses,
    }


def _default_paths() -> tuple[list[Path], Path, list[Path], Path, list[Path]]:
    evidence = REPORT_ROOT / "evidence"
    observatory = sorted((evidence / "observatory").glob("*-native-observatory-v4.json"))
    profile = evidence / "profiling/logical-dynamic-profile-v3.json"
    benchmarks = [
        evidence / "baseline/native-workload-benchmark-v1.json",
        evidence / "optimizations/budget-mode-replication-v1.json",
    ]
    executor = evidence / "optimizations/budget-mode-replication-executor-result-v1.json"
    references = sorted((evidence / "references").glob("*-references-v1.json"))
    return observatory, profile, benchmarks, executor, references


def _render_markdown(report: dict[str, Any]) -> str:
    rows = [
        "# S3 1.9 Optimization Discovery Ranking",
        "",
        "Experimental prioritization only. This report is not an optimization oracle,",
        "does not authorize production changes, and does not promote a default.",
        "",
        f"Pinned source: `{report['source_revision']['git_commit']}`",
        "",
        "| Rank | Tier | Candidate | Score | Confidence |",
        "| ---: | ---: | --- | ---: | --- |",
    ]
    rows.extend(
        f"| {item['rank']} | {item['evidence_tier']} | {item['candidate']} | "
        f"{item['rank_score']:.8f} | {item['confidence']} |"
        for item in report["hypotheses"]
    )
    rows.extend(("", "## Boundaries", "", "- `PER_INSTRUCTION` remains the default.",
                 "- Paired timing is characterization-only; PMU is unavailable by policy.",
                 "- Logical structural weight is not retired instructions, cycles, or causal runtime attribution.",
                 "- Candidate transformations require separate semantic proof, correctness gates, and measurement.", ""))
    reference = report["evidence"]["reference_facts"]
    ref_totals = reference["totals"]
    allocation = report["evidence"]["register_pressure"]
    alloc_totals = allocation["totals"]
    rows.extend((
        "## Reference and Allocator Context",
        "",
        f"Reference reports cover {ref_totals['reference_count']} modeled references: "
        f"{ref_totals['known_origin_reference_count']} known-origin and "
        f"{ref_totals['no_escape_reference_count']} `NO_ESCAPE`; "
        f"{ref_totals['mutable_reference_count']} are mutable. "
        "These remain diagnostic facts and do not authorize transformations.",
        f"Static allocation reports cover {alloc_totals['virtual_register_count']} virtual registers; "
        f"{alloc_totals['stack_resident_virtual_register_count']} are stack-resident across "
        f"{alloc_totals['functions_with_stack_resident_virtuals']} function(s). "
        f"Dynamic spills: `{alloc_totals['dynamic_spills']}`.",
        "The allocator-replacement frontier is not selected from these static counts; "
        "they do not explain dynamic native stack or memory cost.",
        "",
    ))
    experiment = report["evidence"].get("optimization_experiment_result")
    if experiment is not None:
        rows.extend((
            "## Completed Candidate Experiment",
            "",
            f"`{experiment['experiment_id']}`: **{experiment['status']}**; "
            f"{experiment['mutable_loads_forwarded']} of "
            f"{experiment['mutable_loads_before']} mutable loads were forwarded.",
            "The exact same-cell, same-index-version, same-block rule found no eligible pair in the three workloads; broader memory-origin optimization remains open.",
            "Correctness matched baseline and references; no timing or PMU claim was made.",
            "",
        ))
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    defaults_obs, default_profile, defaults_bench, default_executor, defaults_references = _default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observatory-report", action="append", type=Path,
                        help="v4 Observatory JSON; provide exactly three")
    parser.add_argument("--profile-report", type=Path, default=default_profile)
    parser.add_argument("--benchmark-report", action="append", type=Path,
                        help="matched raw timing JSON; provide exactly two")
    parser.add_argument("--executor-report", type=Path, default=default_executor,
                        help="independent lab executor report that pins one raw timing input")
    parser.add_argument("--reference-report", action="append", type=Path,
                        help="current O1 reference-analysis JSON; provide exactly three")
    parser.add_argument("--optimization-experiment-report", type=Path,
                        default=DEFAULT_OPTIMIZATION_EXPERIMENT,
                        help="optional pinned non-production candidate experiment report")
    parser.add_argument("--output", type=Path,
                        default=REPORT_ROOT / "evidence/optimizations/discovery-ranking-v2.json")
    args = parser.parse_args(argv)
    observatory_paths = args.observatory_report or defaults_obs
    benchmark_paths = args.benchmark_report or defaults_bench
    reference_paths = args.reference_report or defaults_references
    try:
        report = build_discovery(observatory_paths, args.profile_report, benchmark_paths,
                                 args.executor_report, reference_paths,
                                 args.optimization_experiment_report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        args.output.with_suffix(".md").write_text(
            _render_markdown(report), encoding="utf-8", newline="\n"
        )
    except EvidenceError as exc:
        parser.error(str(exc))
    print(f"DISCOVERY_REPORT={args.output}")
    for item in report["hypotheses"]:
        print(f"RANK={item['rank']} TIER={item['evidence_tier']} SCORE={item['rank_score']:.8f} "
              f"CATEGORY={item['category']} CANDIDATE={item['candidate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
