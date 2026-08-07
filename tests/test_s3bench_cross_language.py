"""CREATED - NOT EXECUTED UNTIL MILESTONE 1.19 IMPLEMENTATION COMPLETION."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.s3bench import load_manifest
import benchmarks.s3bench.adapters as adapters
from benchmarks.s3bench.adapters import ExternalCompilerAdapter, Toolchain, detect_toolchains
from benchmarks.s3bench.core import BenchmarkError, Case, CommandResult, ManifestError
from benchmarks.s3bench.report import comparison_tables, normalized_rows, render_performance_report

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "manifests" / "s3bench-1.0.0.json"


def _portable_cases():
    _, cases = load_manifest(MANIFEST)
    return tuple(case for case in cases if case.suite == "portable")


def test_portable_manifest_has_input_and_checksum_parity_across_languages():
    grouped: dict[str, list] = {}
    for case in _portable_cases():
        grouped.setdefault(case.benchmark_id, []).append(case)
    for cases in grouped.values():
        assert {case.implementation for case in cases} == {
            "s3", "python-reference", "c", "rust", "zig"
        }
        assert len({case.input_id for case in cases}) == 1
        assert len({case.input_size for case in cases}) == 1
        assert len({case.expected_checksum for case in cases}) == 1


def test_external_optimization_flags_are_explicit_and_portable():
    for case in _portable_cases():
        if case.implementation not in {"c", "rust", "zig"}:
            continue
        flags = case.configuration["compiler_flags"][case.optimization_mode]
        assert flags
        assert "-march=native" not in flags
        assert "-O3" not in flags


def test_manifest_separates_build_and_runtime_timeouts(tmp_path):
    manifest = {
        "manifest_version": "1.0.0",
        "campaign": "test",
        "workloads": [{
            "benchmark_id": "timeout.v1",
            "workload_version": "1.0.0",
            "category": "runtime",
            "suite": "portable",
            "objective": "timeout scope",
            "input": {"id": "one", "size": 1},
            "expected_checksum": "1",
            "timed_region": "program",
            "implementations": [{
                "id": "rust",
                "adapter": "rust",
                "execution_mode": "native",
                "optimization_modes": ["opt-level=0"],
                "source": None,
                "timeout_seconds": 30,
                "build_timeout_seconds": 75,
            }],
        }],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    _, cases = load_manifest(path)

    assert cases[0].timeout_seconds == 30
    assert cases[0].build_timeout_seconds == 75


def test_manifest_uses_safe_build_timeout_default(tmp_path):
    manifest = {
        "manifest_version": "1.0.0",
        "campaign": "test",
        "workloads": [{
            "benchmark_id": "timeout.v1",
            "workload_version": "1.0.0",
            "category": "runtime",
            "suite": "portable",
            "objective": "timeout scope",
            "input": {"id": "one", "size": 1},
            "expected_checksum": "1",
            "timed_region": "program",
            "implementations": [{
                "id": "rust",
                "adapter": "rust",
                "execution_mode": "native",
                "optimization_modes": ["opt-level=0"],
                "source": None,
                "timeout_seconds": 30,
            }],
        }],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    _, cases = load_manifest(path)

    assert cases[0].timeout_seconds == 30
    assert cases[0].build_timeout_seconds == 60


@pytest.mark.parametrize("field", ["timeout_seconds", "build_timeout_seconds"])
def test_manifest_rejects_non_positive_timeout(tmp_path, field):
    manifest = {
        "manifest_version": "1.0.0",
        "campaign": "test",
        "workloads": [{
            "benchmark_id": "timeout.v1",
            "workload_version": "1.0.0",
            "category": "runtime",
            "suite": "portable",
            "objective": "timeout scope",
            "input": {"id": "one", "size": 1},
            "expected_checksum": "1",
            "timed_region": "program",
            "implementations": [{
                "id": "rust",
                "adapter": "rust",
                "execution_mode": "native",
                "optimization_modes": ["opt-level=0"],
                "source": None,
                "timeout_seconds": 30,
                field: 0,
            }],
        }],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError, match="invalid .*timeout"):
        load_manifest(path)


def test_external_adapter_separates_build_and_runtime_timeout(tmp_path, monkeypatch):
    calls = []
    source = tmp_path / "portable.rs"
    source.write_text("fn main() {}", encoding="utf-8")
    case = Case(
        campaign="test",
        benchmark_id="timeout.v1",
        workload_version="1.0.0",
        category="runtime",
        suite="portable",
        implementation="rust",
        adapter="rust",
        execution_mode="native",
        optimization_mode="opt-level=0",
        input_id="one",
        input_size=1,
        expected_checksum="1",
        timeout_seconds=30,
        build_timeout_seconds=75,
        timed_region="program",
        source=source,
        configuration={"compiler_flags": {"opt-level=0": []}},
    )

    def fake_run_command(arguments, *, cwd, timeout_seconds, **kwargs):
        calls.append((tuple(arguments), timeout_seconds))
        if "-o" in arguments:
            output = Path(arguments[arguments.index("-o") + 1])
            output.write_text("binary", encoding="utf-8")
        return CommandResult(
            tuple(arguments), "checksum=1\n", "", 0, False, False, 1
        )

    monkeypatch.setattr(adapters, "run_command", fake_run_command)
    toolchain = Toolchain("rustc", "rustc", "test", True, ("rustc", "--version"))
    adapter = ExternalCompilerAdapter("rust", toolchain)

    artifact = adapter.build(case, tmp_path / "build")
    observation = adapter.execute(case, artifact, 1, case.timeout_seconds)

    assert calls[0][1] == 75
    assert calls[1][1] == 30
    assert observation.checksum == "1"


def test_external_adapter_reports_build_timeout_without_disabling_it(tmp_path, monkeypatch):
    source = tmp_path / "portable.rs"
    source.write_text("fn main() {}", encoding="utf-8")
    case = Case(
        campaign="test", benchmark_id="timeout.v1", workload_version="1.0.0",
        category="runtime", suite="portable", implementation="rust", adapter="rust",
        execution_mode="native", optimization_mode="opt-level=0", input_id="one",
        input_size=1, expected_checksum="1", timeout_seconds=30,
        build_timeout_seconds=75, timed_region="program", source=source,
        configuration={"compiler_flags": {"opt-level=0": []}},
    )

    def timed_out_run_command(arguments, *, cwd, timeout_seconds, **kwargs):
        assert timeout_seconds == 75
        return CommandResult(tuple(arguments), "", "", None, True, False, 75_000_000_000)

    monkeypatch.setattr(adapters, "run_command", timed_out_run_command)
    toolchain = Toolchain("rustc", "rustc", "test", True, ("rustc", "--version"))

    with pytest.raises(BenchmarkError, match="Rust build timed out"):
        ExternalCompilerAdapter("rust", toolchain).build(case, tmp_path / "build")


def test_missing_toolchain_is_explicitly_unavailable(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda command: None)
    detected = detect_toolchains()
    assert all(not tool.available for tool in detected.values())
    assert detected["zig"].detection_command == ("zig", "version")


def test_available_external_toolchains_match_one_checksum(tmp_path):
    detected = detect_toolchains()
    candidates = {
        "c": detected["clang"] if detected["clang"].available else detected["gcc"],
        "rust": detected["rustc"],
        "zig": detected["zig"],
    }
    sample_cases = {
        case.implementation: case for case in _portable_cases()
        if case.benchmark_id == "runtime.scalar.accumulate.v1"
        and case.optimization_mode in {"O0", "opt-level=0", "Debug"}
    }
    for language, toolchain in candidates.items():
        if not toolchain.available:
            continue
        case = sample_cases[language]
        adapter = ExternalCompilerAdapter(language, toolchain)
        artifact = adapter.build(case, tmp_path / language)
        observation = adapter.execute(case, artifact, 1, case.timeout_seconds)
        assert observation.exit_code == 0
        assert observation.checksum == case.expected_checksum


def test_tables_separate_native_interpreted_and_s3_specific():
    rows = [
        _result("portable.v1", "s3", "native", "O0", "portable"),
        _result("portable.v1", "c", "native", "O2", "portable"),
        _result("portable.v1", "s3", "emulator", "O1", "portable"),
        _result("portable.v1", "python-reference", "interpreted", "reference", "portable"),
        _result("internal.v1", "s3", "emulator", "O1", "s3-specific"),
    ]
    tables = comparison_tables(rows)
    assert [row["implementation"] for row in tables["unoptimized"]] == ["s3"]
    assert [row["implementation"] for row in tables["optimized"]] == ["c"]
    assert [row["implementation"] for row in tables["emulated"]] == ["s3"]
    assert [row["implementation"] for row in tables["interpreted"]] == ["python-reference"]
    assert [row["benchmark_id"] for row in tables["s3_specific"]] == ["internal.v1"]


def test_normalization_uses_c_o2_and_never_converts_missing_to_zero():
    rows = [
        _result("portable.v1", "c", "native", "O2", "portable", median=100, loops=10),
        _result("portable.v1", "s3", "native", "O1", "portable", median=250, loops=5),
        _result("missing.v1", "s3", "native", "O1", "portable", median=None),
    ]
    normalized = normalized_rows(rows)
    indexed = {(row["benchmark_id"], row["implementation"]): row for row in normalized}
    assert indexed[("portable.v1", "c")]["normalized_ratio"] == 1.0
    assert indexed[("portable.v1", "s3")]["normalized_ratio"] == 5.0
    assert indexed[("portable.v1", "c")]["median_ns_per_loop"] == 10.0
    assert indexed[("portable.v1", "s3")]["median_ns_per_loop"] == 50.0
    assert indexed[("missing.v1", "s3")]["normalized_ratio"] is None


def test_report_order_is_deterministic_and_renders_reproduction():
    measured = _result("b.v1", "c", "native", "O2", "portable", median=10)
    failed = _result("a.v1", "zig", "native", "ReleaseFast", "portable", median=None)
    failed["status"] = "failed"
    first = render_performance_report([measured, failed], raw_result_path="raw.json")
    second = render_performance_report([failed, measured], raw_result_path="raw.json")
    assert first == second
    assert "raw.json" in first
    assert "python tools/s3bench.py --verify-only" in first
    assert "No claim without a compatible reviewed baseline" in first


def test_report_recommendation_uses_s3_results_not_interpreted_reference():
    rows = [
        _result(
            "python.slow.v1",
            "python-reference",
            "interpreted",
            "reference",
            "portable",
            median=1_000_000,
        ),
        _result("s3.priority.v1", "s3", "emulator", "O0", "portable", median=500),
    ]
    report = render_performance_report(rows, raw_result_path="raw.json")
    recommendation = report.split("## Recommended optimization priorities", 1)[1]
    assert "Review `s3.priority.v1` first" in recommendation


def _result(benchmark_id, implementation, execution_mode, optimization_mode, suite, *, median=100, loops=1):
    return {
        "benchmark_id": benchmark_id,
        "workload_version": "1.0.0",
        "category": "runtime",
        "suite": suite,
        "implementation": implementation,
        "execution_mode": execution_mode,
        "optimization_mode": optimization_mode,
        "status": "measured",
        "median_ns": median,
        "loops_per_sample": loops,
        "coefficient_of_variation": 0.01 if median is not None else None,
        "artifact_size_bytes": 10,
        "comparability_classification": "COMPARABLE",
        "repository_sha": "a" * 40,
        "operating_system": "Linux",
        "architecture": "x86_64",
        "runner_type": "controlled-linux",
        "warmup_count": 3,
        "sample_count": 15,
        "compiler_name": implementation,
        "compiler_version": "test",
        "compiler_flags": [],
    }
