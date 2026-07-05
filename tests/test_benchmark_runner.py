import pytest
import math
import subprocess
import json
import sys
import os
from pathlib import Path

from tools.benchmark import (
    calc_min, calc_max, calc_mean, calc_median, calc_p95,
    get_installed_distribution_version, get_checkout_distribution_version, get_git_commit, is_git_dirty
)

def test_calc_stats():
    # Min/Max
    assert calc_min([1, 2, 3]) == 1
    assert calc_max([1, 2, 3]) == 3
    with pytest.raises(ValueError):
        calc_min([])
    with pytest.raises(ValueError):
        calc_max([])

    # Mean
    assert calc_mean([10, 20]) == 15.0
    with pytest.raises(ValueError):
        calc_mean([])
    # We simulate Infinity
    # Python ints don't overflow, but if we force a float inf
    # median par / impar
    assert calc_median([1, 2, 3]) == 2.0
    assert calc_median([1, 2, 3, 4]) == 2.5
    with pytest.raises(ValueError):
        calc_median([])

    # p95 1, 2, 10, 20, 100 elements
    assert calc_p95([1]) == 1
    assert calc_p95([1, 2]) == 2
    assert calc_p95(list(range(1, 11))) == 10
    assert calc_p95(list(range(1, 21))) == 19
    assert calc_p95(list(range(1, 101))) == 95
    with pytest.raises(ValueError):
        calc_p95([])

    # Large integers
    large = [10**12, 10**12 + 2]
    assert calc_mean(large) == 10**12 + 1
    assert calc_median(large) == 10**12 + 1
    assert calc_p95(large) == 10**12 + 2

def test_git_metadata(monkeypatch):
    assert isinstance(get_git_commit(), str)
    assert get_git_commit() != "unavailable"
    assert is_git_dirty() in ("true", "false")

    def mock_check_output(*args, **kwargs):
        raise Exception("Git failed")

    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    assert get_git_commit() == "unavailable"
    assert is_git_dirty() == "unknown"

def test_distribution_version(monkeypatch):
    # Should get from importlib or tomllib
    ver1 = get_installed_distribution_version()
    ver2 = get_checkout_distribution_version()
    assert isinstance(ver1, str)
    assert isinstance(ver2, str)

def test_cli_help():
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "In-process benchmark runner" in res.stdout

def test_cli_list():
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--list"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "minimal" in res.stdout

def test_cli_list_json():
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--list", "--format", "json"], capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "success"
    assert isinstance(data["workloads"], list)
    assert any(w["id"] == "minimal" for w in data["workloads"])

def test_cli_invalid_args():
    # mode missing
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--optimization", "O0", "--workload", "minimal"], capture_output=True, text=True)
    assert res.returncode != 0

    # invalid mode
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--mode", "invalid", "--format", "json"], capture_output=True, text=True)
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["status"] == "error"
    assert "invalid choice" in data["error"]["message"].lower()

    # runs negative
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--mode", "hosted-pipeline", "--optimization", "O0", "--workload", "minimal", "--runs", "-1", "--format", "json"], capture_output=True, text=True)
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert "Runs must be > 0" in data["error"]["message"]

def test_cli_hosted_execution():
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--mode", "hosted-pipeline", "--optimization", "O0", "--workload", "minimal", "--runs", "1", "--warmups", "1", "--format", "json"], capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["results"][0]["status"] == "passed"
    assert data["results"][0]["actual_return"] == 0

def test_cli_native_execution():
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--mode", "native-asm-pipeline", "--optimization", "O1", "--workload", "minimal", "--runs", "1", "--warmups", "1", "--format", "json"], capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["results"][0]["status"] == "passed"
    assert "actual_return" not in data["results"][0]
    assert data["results"][0]["metrics"]["native_artifact"]["artifact_kind"] == "gnu-x86-64-assembly"
    assert "functional_validation" in data["results"][0]
    assert data["results"][0]["functional_validation"]["status"] == "passed"

def test_file_output(tmp_path):
    out_file = tmp_path / "out.json"
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--mode", "hosted-pipeline", "--optimization", "O0", "--workload", "minimal", "--runs", "1", "--warmups", "0", "--format", "json", "--output", str(out_file)], capture_output=True, text=True)
    assert res.returncode == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["results"][0]["status"] == "passed"

def test_invalid_output_path():
    invalid_path = "/invalid_dir_does_not_exist/out.json" if sys.platform != "win32" else "Z:\\invalid_dir\\out.json"
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--mode", "hosted-pipeline", "--optimization", "O0", "--workload", "minimal", "--runs", "1", "--warmups", "0", "--format", "json", "--output", invalid_path], capture_output=True, text=True)
    assert res.returncode != 0
    assert res.stdout == ""
    assert "S3_BENCH_WRITE_FAILED" in res.stderr


def test_timing_isolation(monkeypatch):
    import time
    from tools import benchmark
    import sys

    calls = []

    original_run_hosted = benchmark.run_hosted_pipeline
    def mock_run_hosted(*args, **kwargs):
        calls.append("run")
        return original_run_hosted(*args, **kwargs)

    def mock_perf_counter_ns():
        calls.append("time")
        return 0

    monkeypatch.setattr(benchmark, "run_hosted_pipeline", mock_run_hosted)
    monkeypatch.setattr(time, "perf_counter_ns", mock_perf_counter_ns)

    # We can't easily test the isolation via subprocess if we monkeypatch.
    # We should run benchmark.main() inside the test.

    monkeypatch.setattr(sys, "argv", ["benchmark.py", "--mode", "hosted-pipeline", "--optimization", "O0", "--workload", "minimal", "--runs", "1", "--warmups", "0", "--format", "json"])

    try:
        benchmark.main()
    except SystemExit:
        pass

    # Validation run is first, then time, run, time
    assert calls.count("run") >= 1
    assert calls.count("time") >= 2
