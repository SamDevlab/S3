"""CREATED - NOT EXECUTED UNTIL MILESTONE 1.19 IMPLEMENTATION COMPLETION."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.s3bench import ManifestError, load_manifest


def test_official_manifest_has_unique_stable_cases():
    root = Path(__file__).resolve().parents[1]
    document, cases = load_manifest(
        root / "benchmarks" / "manifests" / "s3bench-1.0.0.json"
    )
    assert document["manifest_version"] == "1.0.0"
    assert cases == tuple(sorted(cases, key=lambda case: case.identity))
    assert len({case.identity for case in cases}) == len(cases)
    assert all(case.expected_checksum for case in cases)
    assert all(case.workload_version == "1.0.0" for case in cases)


def test_manifest_rejects_duplicate_benchmark_ids(tmp_path):
    source = tmp_path / "source.s3"
    source.write_text("fn main() -> tryte:\n    return 0\n", encoding="utf-8")
    workload = {
        "benchmark_id": "duplicate.v1",
        "workload_version": "1.0.0",
        "category": "test",
        "suite": "portable",
        "objective": "test",
        "input": {"id": "x", "size": 1},
        "expected_checksum": "0",
        "timed_region": "test",
        "implementations": [{
            "id": "s3", "adapter": "s3-emulator", "execution_mode": "emulator",
            "optimization_modes": ["O0"], "source": "source.s3"
        }],
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "campaign": "test",
        "workloads": [workload, workload],
    }), encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate benchmark ID"):
        load_manifest(manifest)


def test_manifest_rejects_path_traversal(tmp_path):
    outside = tmp_path.parent / "outside.s3"
    outside.write_text("not trusted", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "campaign": "test",
        "workloads": [{
            "benchmark_id": "escape.v1", "workload_version": "1.0.0",
            "category": "test", "suite": "portable", "objective": "test",
            "input": {"id": "x", "size": 1}, "expected_checksum": "0",
            "timed_region": "test", "implementations": [{
                "id": "s3", "adapter": "s3-emulator", "execution_mode": "emulator",
                "optimization_modes": ["O0"], "source": "../outside.s3"
            }]
        }]
    }), encoding="utf-8")
    with pytest.raises(ManifestError, match="escapes"):
        load_manifest(manifest)
