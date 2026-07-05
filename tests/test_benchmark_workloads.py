import pytest
import json
import os
from pathlib import Path
from tools.benchmark import load_manifest, run_hosted_pipeline
from bootstrap.s3 import OptimizationLevel

def test_manifest_invalid_json(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text("{invalid")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_manifest(p)

def test_manifest_unsupported_version(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"manifest_version": "9.9.9"}))
    with pytest.raises(ValueError, match="Unsupported manifest version"):
        load_manifest(p)

def test_manifest_missing_workloads(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"manifest_version": "1.0.0"}))
    with pytest.raises(ValueError, match="Workloads must be a non-empty list"):
        load_manifest(p)

def test_manifest_duplicate_id(tmp_path):
    p = tmp_path / "manifest.json"
    f1 = tmp_path / "f"
    f2 = tmp_path / "f2"
    f1.write_text("dummy")
    f2.write_text("dummy")

    p.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "workloads": [
            {"id": "minimal", "file": "f", "expected_return": 0, "max_instructions": 1, "max_frames": 1},
            {"id": "minimal", "file": "f2", "expected_return": 0, "max_instructions": 1, "max_frames": 1}
        ]
    }))
    with pytest.raises(ValueError, match="Duplicate workload ID"):
        load_manifest(p)

def test_manifest_missing_id(tmp_path):
    p = tmp_path / "manifest.json"
    f1 = tmp_path / "f"
    f1.write_text("dummy")
    p.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "workloads": [{"file": "f", "expected_return": 0, "max_instructions": 1, "max_frames": 1}]
    }))
    with pytest.raises(ValueError, match="Invalid or missing ID"):
        load_manifest(p)

def test_manifest_invalid_file(tmp_path):
    p = tmp_path / "manifest.json"
    abs_path = "C:/absolute/path" if os.name == "nt" else "/absolute/path"
    p.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "workloads": [{"id": "minimal", "file": abs_path}]
    }))
    with pytest.raises(ValueError, match="Absolute path"):
        load_manifest(p)

def test_manifest_traversal(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "workloads": [{"id": "minimal", "file": "../test"}]
    }))
    with pytest.raises(ValueError, match="Path traversal"):
        load_manifest(p)

def test_manifest_limits(tmp_path):
    p = tmp_path / "manifest.json"
    f1 = tmp_path / "minimal.s3"
    f1.write_text("dummy")
    base = {"manifest_version": "1.0.0", "workloads": [{"id": "minimal", "file": "minimal.s3", "expected_return": 0, "max_instructions": 0, "max_frames": 1}]}
    p.write_text(json.dumps(base))
    with pytest.raises(ValueError, match="Invalid max_instructions"):
        load_manifest(p)

def test_load_official_manifest():
    root = Path(__file__).resolve().parent.parent
    p = root / "benchmarks" / "manifest.json"
    data = load_manifest(p)
    assert len(data["workloads"]) == 7

def test_workloads_execution():
    root = Path(__file__).resolve().parent.parent
    p = root / "benchmarks" / "manifest.json"
    data = load_manifest(p)

    for w in data["workloads"]:
        src = (root / "benchmarks" / w["file"]).read_text(encoding="utf-8")
        ret_o0 = run_hosted_pipeline(src, OptimizationLevel.O0, w["max_instructions"], w["max_frames"])
        ret_o1 = run_hosted_pipeline(src, OptimizationLevel.O1, w["max_instructions"], w["max_frames"])
        assert ret_o0 == w["expected_return"]
        assert ret_o1 == w["expected_return"]
