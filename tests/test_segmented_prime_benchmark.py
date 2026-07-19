import json
import os
import pytest
import sys
from pathlib import Path

# Add project root to sys.path so we can import the tool
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.benchmark_segmented_primes import (
    simple_sieve,
    segmented_sieve_sequential,
    segmented_sieve_parallel,
    get_base_primes,
    process_segment,
    run_benchmark_cycle,
    _get_machine_profile
)

def test_simple_sieve_correctness():
    assert simple_sieve(10) == (4, 2, 7, 17)
    assert simple_sieve(100)[0] == 25
    assert simple_sieve(1000)[0] == 168

def test_segmented_sieve_sequential_correctness():
    assert segmented_sieve_sequential(10, 32768) == (4, 2, 7, 17)
    assert segmented_sieve_sequential(100, 32)[0] == 25
    assert segmented_sieve_sequential(1000, 256)[0] == 168

def test_segmented_sieve_parallel_correctness():
    assert segmented_sieve_parallel(10, 32768, 2) == (4, 2, 7, 17)
    assert segmented_sieve_parallel(100, 32, 2)[0] == 25
    assert segmented_sieve_parallel(1000, 256, 4)[0] == 168

def test_limits():
    for algo in [simple_sieve, lambda x: segmented_sieve_sequential(x, 1024), lambda x: segmented_sieve_parallel(x, 1024, 2)]:
        # limit < 2
        assert algo(1) == (0, None, None, 0)
        assert algo(-5) == (0, None, None, 0)
        
def test_segment_bounds():
    # segment small enough to force multiple segments
    c, f, l, s = segmented_sieve_sequential(100, 2) # 2 bytes = 4 numbers per segment
    assert c == 25
    assert f == 2
    assert l == 97
    
    # segment not exact multiple
    c, f, l, s = segmented_sieve_sequential(100, 7)
    assert c == 25

def test_workers_bounds():
    assert segmented_sieve_parallel(100, 1024, 1)[0] == 25
    assert segmented_sieve_parallel(100, 10, 60)[0] == 25 # more workers than segments

def test_checksum_is_deterministic():
    c1, f1, l1, s1 = segmented_sieve_sequential(10000, 1024)
    c2, f2, l2, s2 = segmented_sieve_parallel(10000, 1024, 4)
    assert s1 == s2

def test_run_benchmark_cycle():
    def mock_algo(limit):
        return limit * 2
    
    median, res = run_benchmark_cycle(mock_algo, (5,), warmups=2, runs=3)
    assert res == 10
    assert median > 0

def test_machine_profile():
    profile = _get_machine_profile()
    assert "os" in profile
    assert "cpu_name" in profile
    assert profile["logical_cpus"] is not None

def test_cli_verify(monkeypatch, capsys):
    from tools import benchmark_segmented_primes
    monkeypatch.setattr(sys, "argv", ["benchmark_segmented_primes.py", "verify"])
    
    # verify executes to limit 1M which takes ~0.5s total
    benchmark_segmented_primes.main()
    captured = capsys.readouterr()
    assert "[OK]" in captured.out
    assert "Limit: 1000000" in captured.out
    
def test_cli_quick(monkeypatch, capsys):
    from tools import benchmark_segmented_primes
    # Mock limits for quick to be very fast for testing
    monkeypatch.setattr("tools.benchmark_segmented_primes.run_benchmark_cycle", lambda *args: (1000, (4, 2, 7, 17)))
    monkeypatch.setattr(sys, "argv", ["benchmark_segmented_primes.py", "quick"])
    
    benchmark_segmented_primes.main()
    captured = capsys.readouterr()
    assert "Quick Benchmark:" in captured.out
    assert "Speedup:" in captured.out

def test_cli_gpu_probe(monkeypatch, capsys):
    from tools import benchmark_segmented_primes
    monkeypatch.setattr(sys, "argv", ["benchmark_segmented_primes.py", "gpu-probe"])
    
    benchmark_segmented_primes.main()
    captured = capsys.readouterr()
    assert "GPU Capability Probe" in captured.out
