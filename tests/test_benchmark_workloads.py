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

def get_base_mock_workload(w_id="minimal"):
    return {
        "id": w_id,
        "description": "mock",
        "file": f"{w_id}.s3",
        "expected_return": 0,
        "max_instructions": 1,
        "max_frames": 1
    }

def test_manifest_duplicate_id(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "workloads": [get_base_mock_workload("minimal"), get_base_mock_workload("minimal")]
    }))
    with pytest.raises(ValueError, match="Duplicate workload ID"):
        load_manifest(p)

def test_manifest_missing_id(tmp_path):
    p = tmp_path / "manifest.json"
    w = get_base_mock_workload("minimal")
    del w["id"]
    p.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "workloads": [w]
    }))
    with pytest.raises(ValueError, match="Invalid or missing ID"):
        load_manifest(p)

def test_manifest_invalid_file(tmp_path):
    p = tmp_path / "manifest.json"
    # POSIX absolute
    w = get_base_mock_workload("minimal")
    w["file"] = "/absolute/path"
    p.write_text(json.dumps({"manifest_version": "1.0.0", "workloads": [w]}))
    with pytest.raises(ValueError, match="Absolute POSIX path"):
        load_manifest(p)

    # Windows absolute
    w["file"] = "C:\\\\absolute\\\\path"
    p.write_text(json.dumps({"manifest_version": "1.0.0", "workloads": [w]}))
    with pytest.raises(ValueError, match="Absolute Windows/UNC path"):
        load_manifest(p)

    # UNC path
    w["file"] = "\\\\\\\\server\\\\path"
    p.write_text(json.dumps({"manifest_version": "1.0.0", "workloads": [w]}))
    with pytest.raises(ValueError, match="Absolute Windows/UNC path"):
        load_manifest(p)

def test_manifest_traversal(tmp_path):
    p = tmp_path / "manifest.json"
    w = get_base_mock_workload("minimal")
    w["file"] = "../test"
    p.write_text(json.dumps({"manifest_version": "1.0.0", "workloads": [w]}))
    with pytest.raises(ValueError, match="Path traversal"):
        load_manifest(p)

def test_manifest_limits(tmp_path):
    p = tmp_path / "manifest.json"
    w = get_base_mock_workload("minimal")
    w["max_instructions"] = 0
    p.write_text(json.dumps({"manifest_version": "1.0.0", "workloads": [w]}))
    with pytest.raises(ValueError, match="Invalid max_instructions"):
        load_manifest(p)

def test_manifest_validation_failures(tmp_path):
    p = tmp_path / "manifest.json"

    def write_load(w_dict):
        p.write_text(json.dumps({"manifest_version": "1.0.0", "workloads": [w_dict]}))
        load_manifest(p)

    # expected_return is bool
    w = get_base_mock_workload("minimal")
    w["expected_return"] = True
    with pytest.raises(ValueError, match="Invalid expected_return"):
        write_load(w)

    # max_instructions is bool
    w = get_base_mock_workload("minimal")
    w["max_instructions"] = True
    with pytest.raises(ValueError, match="Invalid max_instructions"):
        write_load(w)

    # max_frames is bool
    w = get_base_mock_workload("minimal")
    w["max_frames"] = True
    with pytest.raises(ValueError, match="Invalid max_frames"):
        write_load(w)

    # description missing
    w = get_base_mock_workload("minimal")
    del w["description"]
    with pytest.raises(ValueError, match="Missing or empty description"):
        write_load(w)

    # description empty
    w = get_base_mock_workload("minimal")
    w["description"] = "   "
    with pytest.raises(ValueError, match="Missing or empty description"):
        write_load(w)

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
