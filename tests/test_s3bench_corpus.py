"""CREATED - NOT EXECUTED UNTIL MILESTONE 1.19 IMPLEMENTATION COMPLETION."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from bootstrap.s3.pipeline import run_source
from benchmarks.s3bench import load_manifest
from benchmarks.s3bench.cli import _load_historical_baseline

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
        assert str(run_source(source, optimization="O0")) == expected
        assert str(run_source(source, optimization="O1")) == expected


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
