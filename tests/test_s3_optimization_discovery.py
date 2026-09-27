from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.s3_optimization_discovery import (
    EXPECTED_COMMIT,
    EXPECTED_TREE,
    EXPECTED_WORKLOADS,
    EvidenceError,
    build_discovery,
    main,
    _render_markdown,
)


SOURCE_HASHES = {
    "energy.pv-timeseries-aggregation.v1": "a" * 64,
    "engineering.point-cloud-summary.v1": "b" * 64,
    "geospatial.raster-window-statistics.v1": "c" * 64,
}


def _write(path: Path, document: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    return path


def _inputs(tmp_path: Path) -> tuple[list[Path], Path, list[Path], Path, list[Path]]:
    observatory_paths: list[Path] = []
    for workload_id in sorted(EXPECTED_WORKLOADS):
        document = {
            "schema_version": "1.1.0",
            "report_kind": "S3_X86_64_ELF_NATIVE_OBSERVATORY_EXPERIMENTAL",
            "configuration": {
                "target": "linux-x86_64", "optimization": "O1",
                "instruction_budget_mode": "per-instruction", "native_policy": "baseline",
                "register_allocation": True,
            },
            "provenance": {
                "git_head": EXPECTED_COMMIT, "git_tree": EXPECTED_TREE,
                "source_sha256": SOURCE_HASHES[workload_id],
            },
            "summary": {
                "function_count": 1,
                "native_instruction_count": 10,
                "attributed_native_instructions": 7,
                "unmapped_native_instructions": 3,
                "attributed_text_bytes": 70,
                "unmapped_text_bytes": 30,
                "undecoded_text_bytes": 0,
            },
            "object": {"text_section_bytes": 100},
            "functions": [{
                "name": "fixture_function",
                "allocation": {
                    "virtual_register_count": 5,
                    "stack_resident_virtual_register_count": 1,
                    "stack_resident_virtual_registers": [4],
                    "peak_live_virtual_registers": 3,
                    "peak_values_live_across_call": 1,
                    "dynamic_spills": None,
                    "dynamic_spills_status": "NOT_MEASURED_STATIC_STACK_RESIDENCE_IS_NOT_A_SPILL_COUNTER",
                },
            }],
        }
        observatory_paths.append(_write(tmp_path / "obs" / f"{len(observatory_paths)}.json", document))

    profile_results = {}
    for workload_id in sorted(EXPECTED_WORKLOADS):
        profile_results[workload_id] = {
            "correctness": "PASS_BASELINE_AND_INSTRUMENTED_OUTPUTS_MATCH_REFERENCE_AND_EACH_OTHER",
            "pmu_used": False,
            "timing_performed": False,
            "source_sha256": SOURCE_HASHES[workload_id],
            "dataset_sha256": "d" * 64,
            "estimated_uninstrumented_native_structural_weight": 100,
            "logical_block_executions": 5,
            "weighted_native_origin_categories": {"MEMORY_ACCESS": 60, "USER_COMPUTE": 25, "CONTROL_FLOW": 15},
            "weighted_native_machine_syntax_categories": {"MOVE": 40, "CONTROL_FLOW": 35, "STACK": 25},
        }
    profile = {
        "schema_version": "1.0.0",
        "report_kind": "S3_LOGICAL_DYNAMIC_BLOCK_PROFILE_EXPERIMENTAL",
        "measurement_kind": "LOGICAL_DYNAMIC_COUNTS_AND_STATIC_NATIVE_STRUCTURAL_WEIGHT",
        "interpretation": "These are not hardware instruction counts, cycles, or runtime estimates.",
        "source_provenance": {"git_head": EXPECTED_COMMIT, "git_tree": EXPECTED_TREE},
        "configuration": {
            "target": "linux-x86_64", "optimization": "O1",
            "instruction_budget_mode": "per-instruction", "native_policy": "baseline",
        },
        "results": profile_results,
    }
    profile_path = _write(tmp_path / "profile.json", profile)

    benchmark_paths: list[Path] = []
    for run in range(2):
        candidate_artifacts = {}
        workloads = {}
        for workload_id in sorted(EXPECTED_WORKLOADS):
            for mode in ("EXACT_SEGMENT", "LOOP_HYBRID", "COMPACT_EA"):
                candidate_artifacts[f"S3_O1_{mode}_{workload_id}"] = {
                    "source_sha256": SOURCE_HASHES[workload_id]
                }
            exact_class = "MATERIAL_IMPROVEMENT" if workload_id != "energy.pv-timeseries-aggregation.v1" else "INCONCLUSIVE"
            hybrid_class = "MATERIAL_IMPROVEMENT" if workload_id == "engineering.point-cloud-summary.v1" else "INCONCLUSIVE"
            workloads[workload_id] = {
                "correctness": "PASS_ALL_BUILDS",
                "compact_ea_applied": False,
                "dataset_sha256": "d" * 64,
                "timing_protocol": {
                    "warmups": 3, "samples": 21, "iterations_per_sample": 1000,
                    "material_change_threshold": 0.05,
                },
                "binary_metrics": {"S3_O1_BASELINE": {"text_section_bytes": 100}},
                "paired_comparisons": {
                    "per_vs_exact_segment": {
                        "material_change_threshold": 0.05,
                        "classification": exact_class,
                        "baseline_over_candidate_median_ratio": 1.1 if exact_class == "MATERIAL_IMPROVEMENT" else 1.0,
                    },
                    "per_vs_loop_hybrid": {
                        "material_change_threshold": 0.05,
                        "classification": hybrid_class,
                        "baseline_over_candidate_median_ratio": 1.08 if hybrid_class == "MATERIAL_IMPROVEMENT" else 1.0,
                    },
                    "o0_vs_o1": {
                        "material_change_threshold": 0.05,
                        "classification": "NO_MATERIAL_CHANGE_WITHIN_5_PERCENT",
                        "baseline_over_candidate_median_ratio": 1.0,
                    },
                },
            }
        document = {
            "schema_version": "1.0.0",
            "run_id": f"replica-{run}",
            "source_revision": {"git_commit": EXPECTED_COMMIT, "git_tree": EXPECTED_TREE, "worktree_clean": True},
            "host": {"system": "Linux", "machine": "x86_64", "platform": "Linux-test-x86_64"},
            "cpu_model": "test-cpu",
            "compiler_source_sha256": {"backend.py": "1" * 64, "emitter.py": "2" * 64,
                                        "optimizer.py": "3" * 64, "memory_effects.py": "4" * 64},
            "protocol": {
                "instruction_budget_modes": ["per-instruction", "exact-segment", "loop-hybrid"],
                "s3_optimization_levels": ["O0", "O1"],
                "warmups": 3, "samples": 21, "iterations_per_sample": 1000,
                "material_change_threshold": 0.05,
            },
            "candidate_artifacts": candidate_artifacts,
            "workloads": workloads,
        }
        benchmark_paths.append(_write(tmp_path / f"bench-{run}.json", document))
    compiler_hashes = {"backend.py": "1" * 64, "emitter.py": "2" * 64,
                       "optimizer.py": "3" * 64, "memory_effects.py": "4" * 64}
    _write_profile = json.loads(profile_path.read_text())
    _write_profile["source_provenance"]["compiler_source_sha256"] = compiler_hashes
    _write(profile_path, _write_profile)

    reference_paths: list[Path] = []
    for workload_id in sorted(EXPECTED_WORKLOADS):
        reference = {
            "schema_version": "1.0.0",
            "report_kind": "S3_REFERENCE_DATAFLOW_RESEARCH",
            "provenance": {
                "git_head": EXPECTED_COMMIT,
                "git_worktree_dirty": False,
                "source_sha256": SOURCE_HASHES[workload_id],
                "analysis_implementation_sha256": "6" * 64,
                "report_tool_sha256": "7" * 64,
                "optimization": "O1",
                "source_syntax": "0.6",
            },
            "summary": {
                "function_count": 1,
                "complete_function_count": 1,
                "incomplete_function_count": 0,
                "reference_values": 1,
                "origin_status_counts": {"KNOWN": 1},
                "escape_status_counts": {"NO_ESCAPE": 1},
                "transformation_authorized": False,
            },
            "interpretation": {"not_a_proof_of": ["optimizer_safety"]},
            "functions": [{
                "function": "fixture_function",
                "complete": True,
                "effects": {"none": 0, "read": 1, "read_write": 0, "unknown": 0, "write": 0},
                "references": [{
                    "escape": "NO_ESCAPE",
                    "mutable": True,
                    "origin_unknown": False,
                    "read_uses": 1,
                    "write_uses": 0,
                }],
            }],
        }
        reference_paths.append(_write(tmp_path / "references" / f"{workload_id}.json", reference))

    raw_digest = hashlib.sha256(benchmark_paths[1].read_bytes()).hexdigest()
    executor = {
        "schema_version": "1.0.0",
        "report_kind": "S3_BENCHMARKS_1_9_PINNED_NATIVE_EXECUTION",
        "status": "PASS",
        "execution": {
            "return_code": 0, "timed_out": False,
            "validated": {
                "verified_compiler_source_sha256": compiler_hashes,
            },
        },
        "provenance": {
            "lab_head": "e5ff385d26ea6ec89d13cf1955bfa5438e56a266",
            "lab_tree": "c06ac7b063f27144fa19ddc84dc33c082fcc134a",
            "lab_worktree_clean": False,
            "raw_result_sha256": raw_digest,
            "s3_commit": EXPECTED_COMMIT, "s3_tree": EXPECTED_TREE,
            "s3_worktree_clean": True,
            "native_artifacts": [{"path": "fixture.so", "sha256": "5" * 64, "bytes": 1}],
        },
    }
    executor_path = _write(tmp_path / "executor.json", executor)
    return observatory_paths, profile_path, benchmark_paths, executor_path, reference_paths


def _optimization_experiment(tmp_path: Path) -> Path:
    workloads = {
        workload_id: {
            "correctness": "PASS_REFERENCE_AND_BASELINE_EXACT_OUTPUT_MATCH",
            "mutable_loads_before": 10,
            "mutable_loads_forwarded": 0,
            "mutable_loads_after": 10,
        }
        for workload_id in EXPECTED_WORKLOADS
    }
    return _write(tmp_path / "optimization-experiment.json", {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-19-OPT-001",
        "report_kind": "S3_EXPERIMENTAL_LOCAL_MUTABLE_LOAD_FORWARDING",
        "execution_environment": {"system": "Linux", "machine": "x86_64"},
        "experiment_implementation": {
            "driver_path": "tools/s3_native_optimization_experiments.py",
            "driver_sha256": "1" * 64,
            "focused_test_path": "tests/test_s3_native_optimization_experiments.py",
            "focused_test_sha256": "2" * 64,
        },
        "source_revision": {
            "git_commit": EXPECTED_COMMIT,
            "git_tree": EXPECTED_TREE,
            "compiler_source_dirty": False,
        },
        "transformation": {
            "production_pipeline_changed": False,
            "timing_performed": False,
            "pmu_used": False,
        },
        "summary": {
            "mutable_loads_before": 30,
            "mutable_loads_forwarded": 0,
            "mutable_loads_after": 30,
            "native_timing_claim": False,
            "status": "REJECTED_NO_ELIGIBLE_REPEATED_MUTABLE_LOADS",
        },
        "workloads": workloads,
    })


def test_discovery_ranks_measured_replicated_signals_before_structural_hypotheses(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)

    report = build_discovery(observatory, profile, benchmarks, executor, references)

    assert report["interpretation"]["is_oracle"] is False
    assert report["interpretation"]["per_instruction_default_preserved"] is True
    assert [item["category"] for item in report["hypotheses"][:2]] == [
        "INSTRUCTION_BUDGET_POLICY", "INSTRUCTION_BUDGET_POLICY"
    ]
    assert report["hypotheses"][0]["candidate"] == "EXACT_SEGMENT"
    assert report["hypotheses"][0]["evidence"]["repeated_material_improvement_workloads"] == [
        "engineering.point-cloud-summary.v1", "geospatial.raster-window-statistics.v1"
    ]
    assert report["hypotheses"][2]["category"] == "MEMORY_ORIGIN_REDUCTION"
    assert report["evidence"]["total_dynamic_structural_weight"] == 300
    assert report["evidence"]["reference_facts"]["totals"] == {
        "function_count": 3,
        "reference_count": 3,
        "no_escape_reference_count": 3,
        "known_origin_reference_count": 3,
        "mutable_reference_count": 3,
        "unknown_effect_count": 0,
        "transformation_authorized": False,
    }
    assert report["evidence"]["register_pressure"]["totals"]["virtual_register_count"] == 15
    assert report["evidence"]["register_pressure"]["totals"]["stack_resident_virtual_register_count"] == 3
    assert report["interpretation"]["reference_facts_authorize_transformations"] is False
    memory = report["hypotheses"][2]
    assert memory["evidence"]["reference_facts_by_workload"]
    assert any("not transformation authority" in item for item in memory["unknowns"])
    markdown = _render_markdown(report)
    assert "3 `NO_ESCAPE`" in markdown
    assert "do not authorize transformations" in markdown
    assert "Dynamic spills: `NOT_MEASURED`" in markdown


def test_reference_facts_are_diagnostic_and_fail_closed_on_source_mismatch(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    changed = json.loads(references[0].read_text())
    changed["provenance"]["source_sha256"] = "f" * 64
    _write(references[0], changed)

    with pytest.raises(EvidenceError, match="source hash does not match"):
        build_discovery(observatory, profile, benchmarks, executor, references)


def test_discovery_rejects_reference_report_that_grants_transformation_authority(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    changed = json.loads(references[0].read_text())
    changed["summary"]["transformation_authorized"] = True
    _write(references[0], changed)

    with pytest.raises(EvidenceError, match="incorrectly grants transformation authority"):
        build_discovery(observatory, profile, benchmarks, executor, references)


def test_discovery_rejects_unmeasured_register_spills_reclassified_as_zero(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    changed = json.loads(observatory[0].read_text())
    changed["functions"][0]["allocation"]["dynamic_spills"] = 0
    _write(observatory[0], changed)

    with pytest.raises(EvidenceError, match="dynamic-spill status"):
        build_discovery(observatory, profile, benchmarks, executor, references)


def test_discovery_rejects_malformed_allocator_register_identity(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    changed = json.loads(observatory[0].read_text())
    changed["functions"][0]["allocation"]["stack_resident_virtual_registers"] = [True]
    _write(observatory[0], changed)

    with pytest.raises(EvidenceError, match="register list is malformed"):
        build_discovery(observatory, profile, benchmarks, executor, references)


def test_discovery_cli_writes_lf_deterministic_artifacts(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    experiment = _optimization_experiment(tmp_path)
    output = tmp_path / "ranking.json"
    argv = [
        *[arg for path in observatory for arg in ("--observatory-report", str(path))],
        "--profile-report", str(profile),
        *[arg for path in benchmarks for arg in ("--benchmark-report", str(path))],
        "--executor-report", str(executor),
        *[arg for path in references for arg in ("--reference-report", str(path))],
        "--optimization-experiment-report", str(experiment),
        "--output", str(output),
    ]

    assert main(argv) == 0
    markdown = output.with_suffix(".md")
    assert b"\r\n" not in output.read_bytes()
    assert b"\r\n" not in markdown.read_bytes()
    assert json.loads(output.read_text(encoding="utf-8"))["interpretation"]["is_oracle"] is False


def test_discovery_fails_closed_on_source_identity_mismatch(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    changed = json.loads(profile.read_text())
    changed["source_provenance"]["git_tree"] = "0" * 40
    _write(profile, changed)

    with pytest.raises(EvidenceError, match="not pinned"):
        build_discovery(observatory, profile, benchmarks, executor, references)


def test_discovery_fails_closed_when_dynamic_category_totals_do_not_reconcile(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    changed = json.loads(profile.read_text())
    workload = sorted(EXPECTED_WORKLOADS)[0]
    changed["results"][workload]["weighted_native_origin_categories"]["MEMORY_ACCESS"] += 1
    _write(profile, changed)

    with pytest.raises(EvidenceError, match="do not sum"):
        build_discovery(observatory, profile, benchmarks, executor, references)


def test_discovery_fails_closed_when_benchmark_replicates_are_not_independent(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)

    with pytest.raises(EvidenceError, match="not independent"):
        build_discovery(observatory, profile, [benchmarks[0], benchmarks[0]], executor, references)


def test_discovery_fails_closed_when_correctness_gate_did_not_pass(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    changed = json.loads(benchmarks[0].read_text())
    changed["workloads"][sorted(EXPECTED_WORKLOADS)[0]]["correctness"] = "FAIL"
    _write(benchmarks[0], changed)

    with pytest.raises(EvidenceError, match="correctness gate"):
        build_discovery(observatory, profile, benchmarks, executor, references)


def test_discovery_records_a_fully_reconciled_rejected_candidate_experiment(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    experiment = _optimization_experiment(tmp_path)

    report = build_discovery(observatory, profile, benchmarks, executor, references, experiment)

    evidence = report["evidence"]["optimization_experiment_result"]
    assert evidence["status"] == "REJECTED_NO_ELIGIBLE_REPEATED_MUTABLE_LOADS"
    assert evidence["mutable_loads_before"] == 30
    assert evidence["mutable_loads_forwarded"] == 0
    assert report["hypotheses"][2]["status"] == (
        "EXACT_LOCAL_RULE_REJECTED_BROADER_MEMORY_HYPOTHESIS_OPEN"
    )


def test_discovery_fails_closed_on_unreconciled_optimization_experiment(tmp_path: Path) -> None:
    observatory, profile, benchmarks, executor, references = _inputs(tmp_path)
    experiment = _optimization_experiment(tmp_path)
    changed = json.loads(experiment.read_text())
    changed["summary"]["mutable_loads_before"] = 31
    _write(experiment, changed)

    with pytest.raises(EvidenceError, match="totals do not match"):
        build_discovery(observatory, profile, benchmarks, executor, references, experiment)
