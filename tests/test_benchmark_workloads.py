import pytest
import json
from pathlib import Path

from bootstrap.s3 import OptimizationLevel
from tools.benchmark import (
    BENCHMARK_FORMAT_VERSION,
    DETERMINISTIC_BASELINE_SOURCE_FORMAT_VERSION,
    load_manifest,
    run_hosted_pipeline,
)
from tools.generate_deterministic_baseline import (
    BASELINE_FORMAT_VERSION,
    generate_baseline,
)

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
        ret_o0 = run_hosted_pipeline(src, OptimizationLevel.O0, w["max_instructions"], w["max_frames"])[0]
        ret_o1 = run_hosted_pipeline(src, OptimizationLevel.O1, w["max_instructions"], w["max_frames"])[0]
        assert ret_o0 == w["expected_return"]
        assert ret_o1 == w["expected_return"]

def test_deterministic_metrics_gate():
    root = Path(__file__).resolve().parent.parent
    baseline_path = root / "benchmarks" / "baseline-0.8-e2.json"

    assert baseline_path.is_file(), "Deterministic E2 baseline is missing"

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    assert set(baseline) == {
        "baseline_format_version",
        "benchmark_format_version",
        "workloads",
    }
    assert baseline["baseline_format_version"] == BASELINE_FORMAT_VERSION
    assert baseline["benchmark_format_version"] == DETERMINISTIC_BASELINE_SOURCE_FORMAT_VERSION

    # The historical E2 baseline must remain pinned to the source format that
    # existed when it was generated, even if the public benchmark report format
    # advances later.
    assert baseline["benchmark_format_version"] != BENCHMARK_FORMAT_VERSION

    # Guard against accidentally wiring the current public report version into
    # the baseline generator.
    from tools import benchmark as benchmark_module

    original_version = benchmark_module.BENCHMARK_FORMAT_VERSION
    benchmark_module.BENCHMARK_FORMAT_VERSION = "9.9.9"
    try:
        assert generate_baseline()["benchmark_format_version"] == DETERMINISTIC_BASELINE_SOURCE_FORMAT_VERSION
    finally:
        benchmark_module.BENCHMARK_FORMAT_VERSION = original_version
    assert generate_baseline() == baseline

    manifest_path = root / "benchmarks" / "manifest.json"
    manifest = load_manifest(manifest_path)
    expected_workloads = {w["id"]: w for w in manifest["workloads"]}

    actual_workloads = baseline.get("workloads", {})

    assert len(expected_workloads) == 7, "Manifest must have exactly 7 workloads"

    for w_id in expected_workloads:
        assert w_id in actual_workloads, f"Workload missing from baseline: {w_id}"

    for w_id in actual_workloads:
        assert w_id in expected_workloads, f"Extra workload found in baseline: {w_id}"

    required_opt = {"O0", "O1"}
    required_static_ir = {
        "function_count",
        "block_count",
        "instruction_count",
    }
    required_static_s3 = {
        "function_count",
        "block_count",
        "opcode_count",
        "textual_size_bytes",
        "sha256",
    }
    required_dynamic = {
        "executed_s3_opcodes",
        "maximum_frame_depth_observed",
        "function_call_count",
    }

    for w_id, w_data in actual_workloads.items():
        w = expected_workloads[w_id]
        src = (root / "benchmarks" / w["file"]).read_text(encoding="utf-8")
        assert set(w_data) == required_opt

        for opt_str in ("O0", "O1"):
            b_res = w_data[opt_str]
            assert set(b_res) == {
                "expected_return",
                "ir",
                "s3_assembly",
                "execution",
            }
            assert set(b_res["ir"]) == required_static_ir
            assert set(b_res["s3_assembly"]) == required_static_s3
            assert set(b_res["execution"]) == required_dynamic

            opt = OptimizationLevel.O1 if opt_str == "O1" else OptimizationLevel.O0

            # run hosted to get actual dynamic metrics
            ret, _, static_metrics, dynamic_metrics, _, _, _ = run_hosted_pipeline(src, opt, w["max_instructions"], w["max_frames"])

            # verify values
            assert ret == b_res["expected_return"], f"Divergent expected_return in {w_id} {opt_str}"

            for f in required_static_ir:
                assert static_metrics["ir"][f] == b_res["ir"][f], f"Divergent ir.{f} in {w_id} {opt_str}"
            for f in required_static_s3:
                assert static_metrics["s3_assembly"][f] == b_res["s3_assembly"][f], f"Divergent s3_assembly.{f} in {w_id} {opt_str}"
            for f in required_dynamic:
                assert dynamic_metrics["execution"][f] == b_res["execution"][f], f"Divergent execution.{f} in {w_id} {opt_str}"
