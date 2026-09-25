"""CREATED - NOT EXECUTED UNTIL MILESTONE 1.19 IMPLEMENTATION COMPLETION."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from bootstrap.s3.pipeline import run_source
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.stdlib import standard_library_sources
from benchmarks.s3bench import load_manifest
from benchmarks.s3bench.cli import _load_historical_baseline

import pytest

pytestmark = pytest.mark.s3_benchmark

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "manifests" / "s3bench-1.0.0.json"


def _document_and_cases():
    return load_manifest(MANIFEST)


def test_corpus_covers_required_runtime_and_compiler_categories():
    document, _ = _document_and_cases()
    categories = {workload["category"] for workload in document["workloads"]}
    assert {
        "runtime-scalar",
        "runtime-call",
        "runtime-array",
        "runtime-aggregate",
        "runtime-text",
        "frontend-tokenizer",
        "frontend-parser",
        "frontend-candidate",
        "compiler-pipeline",
        "scientific-compute",
    }.issubset(categories)


def test_each_workload_has_version_input_checksum_and_timed_region():
    document, _ = _document_and_cases()
    for workload in document["workloads"]:
        assert workload["benchmark_id"].endswith(".v1")
        assert workload["workload_version"] == "1.0.0"
        assert workload["expected_checksum"]
        assert workload["input"]["id"]
        assert workload["input"]["size"] >= 0
        assert workload["timed_region"]
        assert workload["implementations"]


def test_s3_sources_preserve_o0_o1_checksum_parity():
    _, cases = _document_and_cases()
    expected_by_source: dict[Path, str] = {}
    for case in cases:
        if case.adapter == "s3-emulator" and case.source is not None:
            expected_by_source[case.source] = case.expected_checksum
    for source_path, expected in expected_by_source.items():
        source = source_path.read_text(encoding="utf-8")
        if "from s3.v1.science import " in source:
            for optimization in ("O0", "O1"):
                sources = standard_library_sources(modules=("s3.v1.science",))
                sources["main.s3"] = source
                compilation = compile_sources(sources, optimization=optimization)
                assert str(execute_ir(compilation.ir)) == expected
        else:
            assert str(run_source(source, optimization="O0")) == expected
            assert str(run_source(source, optimization="O1")) == expected


def test_scientific_workload_declares_its_size_and_work_matrix():
    document, cases = _document_and_cases()
    expected = {
        "science.structural-comparison.v1": (8, 9),
        "science.statistics-matrix.v1": (20, 15),
        "science.similarity-distance.v1": (24, 8),
    }
    by_id = {
        item["benchmark_id"]: item
        for item in document["workloads"]
        if item["benchmark_id"] in expected
    }
    assert set(by_id) == set(expected)
    for benchmark_id, (kernel_calls, traversals) in expected.items():
        workload = by_id[benchmark_id]
        lengths = workload["input"]["vector_lengths"]
        assert lengths == [64, 256, 1024, 8192]
        assert workload["input"]["size"] == sum(lengths)
        assert workload["input"]["kernel_calls"] == kernel_calls
        assert workload["input"]["total_elements_processed"] == traversals * sum(lengths)
        assert any(
            case.adapter == "s3-native"
            for case in cases
            if case.benchmark_id == benchmark_id
        )


def test_budget_policy_manifest_uses_one_identical_scientific_workload():
    _, cases = load_manifest(
        ROOT / "benchmarks" / "manifests" / "s3bench-1.3-budget-policy.json"
    )
    assert len(cases) == 3
    assert {case.implementation for case in cases} == {
        "s3-per",
        "s3-exact",
        "s3-loop-hybrid",
    }
    assert {case.source for case in cases} == {
        ROOT / "benchmarks" / "workloads" / "scientific" / "structural_comparison.s3"
    }
    assert {case.optimization_mode for case in cases} == {"O1"}
    assert {case.expected_checksum for case in cases} == {"48684"}
    assert {case.input_id for case in cases} == {"coordinate-matrix-64-8192"}
    assert {case.input_size for case in cases} == {9536}
    assert {
        case.configuration["native_instruction_budget_mode"] for case in cases
    } == {"per-instruction", "exact-segment", "loop-hybrid"}
    assert {case.configuration["native_max_instructions"] for case in cases} == {
        50_000_000
    }


def test_python_reference_checksums_match_manifest():
    _, cases = _document_and_cases()
    for case in cases:
        if case.adapter != "python-reference" or case.source is None:
            continue
        completed = subprocess.run(
            [sys.executable, str(case.source), case.benchmark_id, "1"],
            capture_output=True,
            text=True,
            timeout=case.timeout_seconds,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == f"checksum={case.expected_checksum}"


def test_s3_modes_are_explicit_and_never_simulated():
    _, cases = _document_and_cases()
    s3_modes: dict[str, set[tuple[str, str]]] = {}
    for case in cases:
        if case.implementation == "s3":
            s3_modes.setdefault(case.benchmark_id, set()).add(
                (case.execution_mode, case.optimization_mode)
            )
    for modes in s3_modes.values():
        assert ("emulator", "O0") in modes
        assert ("emulator", "O1") in modes
        assert ("native", "O0") in modes
        assert ("native", "O1") in modes


def test_workload_sources_have_no_timing_random_network_or_output_calls():
    _, cases = _document_and_cases()
    source_paths = {case.source for case in cases if case.source and case.source.suffix == ".s3"}
    forbidden = ("perf_counter", "time(", "random", "socket", "print(", "write(")
    for source_path in source_paths:
        source = source_path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden)


def test_artifact_inputs_are_stable_and_bounded():
    assembly_root = ROOT / "benchmarks" / "workloads" / "assembly"
    valid = (assembly_root / "valid-multi-result.s3asm").read_text(encoding="utf-8")
    invalid = (assembly_root / "invalid-version.s3asm").read_text(encoding="utf-8")
    assert len(valid.encode("utf-8")) == 157
    assert len(invalid.encode("utf-8")) == 13
    assert len(valid) <= 364
    assert len(invalid) <= 364


def test_historical_e2_baseline_is_preserved_as_non_comparable():
    baseline = ROOT / "benchmarks" / "baseline-0.8-e2.json"
    classification = _load_historical_baseline(baseline)
    assert classification["path"] == "baseline-0.8-e2.json"
    assert classification["classification"] == "NOT_COMPARABLE"
    assert "workload versions" in classification["reason"]
