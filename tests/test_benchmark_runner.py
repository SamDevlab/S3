import pytest
import subprocess
import sys
from tools.benchmark import (
    calc_min,
    calc_max,
    calc_mean,
    calc_median,
    calc_p95,
)

def test_calc_min():
    assert calc_min([5, 2, 8]) == 2
    assert calc_min([1000000000]) == 1000000000
    with pytest.raises(ValueError):
        calc_min([])

def test_calc_max():
    assert calc_max([5, 2, 8]) == 8
    assert calc_max([1000000000]) == 1000000000
    with pytest.raises(ValueError):
        calc_max([])

def test_calc_mean():
    assert calc_mean([2, 4, 6]) == 4.0
    assert calc_mean([1]) == 1.0
    with pytest.raises(ValueError):
        calc_mean([])

def test_calc_median():
    assert calc_median([1, 2, 3]) == 2.0
    assert calc_median([1, 2, 3, 4]) == 2.5
    assert calc_median([1000000000]) == 1000000000.0
    with pytest.raises(ValueError):
        calc_median([])

def test_calc_p95():
    assert calc_p95([1]) == 1
    assert calc_p95([1, 2]) == 2
    assert calc_p95(list(range(1, 11))) == 10
    assert calc_p95(list(range(1, 21))) == 19
    assert calc_p95(list(range(1, 101))) == 95
    with pytest.raises(ValueError):
        calc_p95([])

def test_runner_cli_help():
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "In-process benchmark runner for S3" in res.stdout

def test_runner_cli_list():
    res = subprocess.run([sys.executable, "tools/benchmark.py", "--list"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "minimal" in res.stdout
    assert "arithmetic" in res.stdout
    assert "optimizer_stress" in res.stdout

def test_runner_cli_invalid_args():
    res = subprocess.run([sys.executable, "tools/benchmark.py"], capture_output=True, text=True)
    assert res.returncode != 0
    assert "Missing required arguments" in res.stderr

def test_runner_cli_invalid_workload():
    res = subprocess.run([
        sys.executable, "tools/benchmark.py",
        "--mode", "hosted-pipeline",
        "--optimization", "O0",
        "--workload", "unknown_wl"
    ], capture_output=True, text=True)
    assert res.returncode != 0
    assert "Unknown workload" in res.stderr
