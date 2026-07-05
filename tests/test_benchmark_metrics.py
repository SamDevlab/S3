import pytest
from bootstrap.s3.metrics import PhaseTimer, EmulationMetrics
from bootstrap.s3.emulator import Emulator

def test_phase_timer_basic():
    timer = PhaseTimer()
    with timer.measure("parsing"):
        pass
    with timer.measure("optimization"):
        pass
    snapshot = timer.snapshot()
    assert "parsing" in snapshot
    assert "optimization" in snapshot
    assert snapshot["parsing"] >= 0
    assert snapshot["optimization"] >= 0

def test_phase_timer_duplicate():
    timer = PhaseTimer()
    with timer.measure("test"):
        pass
    with pytest.raises(ValueError, match="already measured"):
        with timer.measure("test"):
            pass

def test_phase_timer_overlap():
    timer = PhaseTimer()
    with pytest.raises(ValueError, match="is running"):
        with timer.measure("outer"):
            with timer.measure("inner"):
                pass

def test_emulator_metrics_tracking():
    # A simple test checking the emulator metric initialization
    e = Emulator(enable_metrics=True)
    assert e.metrics is not None
    assert e.metrics.executed_s3_opcodes == 0
    assert e.metrics.maximum_frame_depth_observed == 0
    assert e.metrics.function_call_count == 0

    e_no_metrics = Emulator()
    assert e_no_metrics.metrics is None
