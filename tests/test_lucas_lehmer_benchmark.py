import pytest
import sys
import multiprocessing
from tools.benchmark_mersenne_bigint import ll_python, ll_binary_seq, run_with_watchdog, calibrate

def test_ll_python_correctness():
    cases = [(3, True), (11, False), (17, True), (23, False)]
    for p, expected in cases:
        res, t, s = ll_python(p)
        assert res == expected

def test_ll_binary_seq_correctness():
    cases = [(5, True), (13, True), (19, True), (31, True)]
    for p, expected in cases:
        res, t, s = ll_binary_seq(p)
        assert res == expected

def test_watchdog_timeout():
    # p=1000 will easily timeout if hard_timeout is small
    res = run_with_watchdog("python-int", 1000, hard_timeout=0.01)
    assert res["status"] == "hard_timeout"

def test_calibrate_function():
    # Fast prime calibration
    res = calibrate(5, "python-int", workers=1, max_cal_iters=4, cal_timeout=5)
    assert res["status"] == "completed"
    assert res["median_iter_ns"] > 0
    assert res["eta_s"] > 0
    assert res["eta_margin_s"] == res["eta_s"] * 1.25
