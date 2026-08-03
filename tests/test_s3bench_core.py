"""CREATED - NOT EXECUTED UNTIL MILESTONE 1.19 IMPLEMENTATION COMPLETION."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from benchmarks.s3bench import (
    BenchmarkError,
    BenchmarkHarness,
    BuildArtifact,
    ExecutionObservation,
    calibrate,
    collect_environment_metadata,
    compare_results,
    compute_statistics,
    duration_per_loop_ns,
    extract_checksum,
    load_manifest,
    render_markdown,
    run_command,
    validate_result_document,
    write_json,
)


class FakeAdapter:
    def __init__(self, checksum: str = "7") -> None:
        self.checksum = checksum
        self.loops: list[int] = []

    def build(self, case, build_dir):
        del case, build_dir
        return BuildArtifact(compile_duration_ns=5, artifact_size_bytes=8)

    def execute(self, case, artifact, loops, timeout_seconds):
        del case, artifact, timeout_seconds
        self.loops.append(loops)
        return ExecutionObservation(self.checksum, loops * 100)


def _case():
    root = Path(__file__).resolve().parents[1]
    _, cases = load_manifest(root / "benchmarks" / "manifests" / "s3bench-1.0.0.json")
    return replace(
        cases[0],
        benchmark_id="test.fake.v1",
        implementation="fake",
        adapter="fake",
        expected_checksum="7",
    )


def test_statistics_preserve_all_samples_and_use_nearest_rank_p95():
    samples = [1, 2, 3, 4, 100]
    summary = compute_statistics(samples)
    assert summary.median_ns == 3
    assert summary.mean_ns == 22
    assert summary.minimum_ns == 1
    assert summary.maximum_ns == 100
    assert summary.percentile_95_ns == 100
    assert summary.standard_deviation_ns > 0
    assert summary.coefficient_of_variation > 0


def test_statistics_reject_empty_or_negative_samples():
    with pytest.raises(ValueError):
        compute_statistics([])
    with pytest.raises(ValueError):
        compute_statistics([1, -1])


def test_calibration_is_bounded_and_deterministic():
    calibration = calibrate(
        lambda loops: loops * 10,
        target_sample_ns=100,
        maximum_loops=16,
        maximum_attempts=4,
    )
    assert calibration.loops_per_sample == 10
    assert calibration.attempts == 2
    assert calibration.last_duration_ns == 100


def test_calibration_rejects_unbounded_or_invalid_measurements():
    with pytest.raises(BenchmarkError, match="attempt limit"):
        calibrate(lambda loops: 1, target_sample_ns=1000, maximum_attempts=1)
    with pytest.raises(BenchmarkError, match="invalid duration"):
        calibrate(lambda loops: -1)


def test_safe_command_invocation_captures_status_and_timeout(tmp_path):
    success = run_command(
        [sys.executable, "-c", "print('checksum=4')"],
        cwd=tmp_path,
        timeout_seconds=10,
    )
    assert success.exit_code == 0
    assert not success.timed_out
    assert extract_checksum(success.stdout) == "4"


def test_checksum_requires_exactly_one_bounded_output_line():
    assert extract_checksum("note\nchecksum=abc\n") == "abc"
    with pytest.raises(BenchmarkError):
        extract_checksum("missing")
    with pytest.raises(BenchmarkError):
        extract_checksum("checksum=a\nchecksum=b\n")


def test_harness_excludes_verification_warmups_and_calibration_from_samples(tmp_path):
    adapter = FakeAdapter()
    harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)
    result = harness.run_case(
        _case(),
        build_dir=tmp_path / "build",
        warmups=2,
        samples=3,
        target_sample_ns=200,
    )
    assert adapter.loops == [1, 1, 1, 1, 2, 2, 2, 2]
    assert result["raw_durations_ns"] == [200, 200, 200]
    assert duration_per_loop_ns(result) == 100.0
    assert result["sample_count"] == 3
    assert result["correctness_status"] == "verified"


def test_harness_stops_before_measurement_on_checksum_failure(tmp_path):
    adapter = FakeAdapter("wrong")
    harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)
    with pytest.raises(BenchmarkError, match="checksum mismatch"):
        harness.run_case(_case(), build_dir=tmp_path, samples=2)
    assert adapter.loops == [1]


def test_verify_only_and_build_only_do_not_measure(tmp_path):
    adapter = FakeAdapter()
    harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)
    verified = harness.run_case(_case(), build_dir=tmp_path, verify_only=True)
    assert verified["status"] == "verified"
    assert adapter.loops == [1]
    adapter.loops.clear()
    built = harness.run_case(_case(), build_dir=tmp_path, build_only=True)
    assert built["status"] == "built"
    assert adapter.loops == []


def test_result_export_is_deterministic_and_private(tmp_path):
    adapter = FakeAdapter()
    harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)
    result = harness.run_case(_case(), build_dir=tmp_path, warmups=0, samples=2, loops=1)
    result["timestamp_utc"] = "2026-01-01T00:00:00+00:00"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_json(first, [result])
    write_json(second, [result])
    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    validate_result_document(payload["results"][0])
    serialized = first.read_text(encoding="utf-8").lower()
    assert "username" not in serialized
    assert "hostname" not in serialized
    assert "/users/" not in serialized


def test_metadata_has_no_personal_identity_fields(tmp_path):
    metadata = collect_environment_metadata(
        repository_root=tmp_path,
        runner_type="shared-ci",
        timestamp_utc="2026-01-01T00:00:00+00:00",
    )
    assert metadata["runner_type"] == "shared-ci"
    assert not {"username", "hostname", "home_directory", "environment"}.intersection(metadata)


def test_comparison_and_markdown_keep_missing_values_explicit():
    result = {
        "benchmark_id": "x.v1",
        "implementation": "c",
        "execution_mode": "native",
        "optimization_mode": "O2",
        "median_ns": None,
        "loops_per_sample": None,
        "coefficient_of_variation": None,
        "comparability_classification": "NOT_COMPARABLE",
    }
    comparison = compare_results([result], reference_implementation="c")
    assert comparison[0]["normalized_ratio"] is None
    markdown = render_markdown([result])
    assert "unavailable" in markdown
    assert "| 0 |" not in markdown
