import pytest

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.metrics import PhaseTimer


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


def _clock_from(*values):
    iterator = iter(values)

    def clock():
        value = next(iterator)
        if isinstance(value, BaseException):
            raise value
        return value

    return clock


def test_phase_timer_preserves_body_exception_and_records_phase():
    timer = PhaseTimer()
    body_error = ValueError("Body error")

    with pytest.raises(ValueError, match="Body error") as exc_info:
        with timer.measure("fail_body"):
            raise body_error

    assert exc_info.value is body_error
    assert "fail_body" in timer.snapshot()


def test_phase_timer_stop_failure_clears_state():
    timer = PhaseTimer(clock=_clock_from(100, 50))

    with pytest.raises(ValueError, match="Negative duration"):
        with timer.measure("fail_stop"):
            pass

    assert timer.snapshot() == {}


def test_phase_timer_groups_body_and_stop_failures():
    timer = PhaseTimer(clock=_clock_from(100, 50))
    body_error = ValueError("Body error")

    with pytest.raises(ExceptionGroup) as exc_info:
        with timer.measure("fail_both"):
            raise body_error

    assert "Phase execution and stop both failed" in str(exc_info.value)
    assert exc_info.value.exceptions[0] is body_error
    assert "Negative duration" in str(exc_info.value.exceptions[1])
    assert timer.snapshot() == {}


def test_phase_timer_clock_failures_do_not_poison_state():
    start_timer = PhaseTimer(clock=_clock_from(RuntimeError("start failed")))
    with pytest.raises(RuntimeError, match="start failed"):
        with start_timer.measure("failed_start"):
            pass
    assert start_timer.snapshot() == {}

    stop_timer = PhaseTimer(
        clock=_clock_from(100, RuntimeError("stop failed"))
    )
    with pytest.raises(RuntimeError, match="stop failed"):
        with stop_timer.measure("failed_stop"):
            pass
    assert stop_timer.snapshot() == {}

    stop_timer._clock = _clock_from(0, 1)
    with stop_timer.measure("reused"):
        pass
    assert stop_timer.snapshot() == {"reused": 1}


def test_phase_timer_preserves_base_exceptions_when_stop_also_fails():
    timer = PhaseTimer(clock=_clock_from(100, 50))
    body_error = KeyboardInterrupt("body interrupted")

    with pytest.raises(BaseExceptionGroup) as exc_info:
        with timer.measure("interrupted"):
            raise body_error

    assert type(exc_info.value) is BaseExceptionGroup
    assert exc_info.value.exceptions[0] is body_error
    assert "Negative duration" in str(exc_info.value.exceptions[1])
    assert timer.snapshot() == {}
