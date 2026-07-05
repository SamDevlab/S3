"""Internal telemetry and metrics collection for the S3 toolchain."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class EmulationMetrics:
    """Metrics collected during an emulation run."""
    executed_s3_opcodes: int = 0
    maximum_frame_depth_observed: int = 0
    function_call_count: int = 0


class PhaseTimer:
    """A simple timer to measure non-overlapping pipeline phases."""

    def __init__(self, clock=time.perf_counter_ns):
        self._clock = clock
        self._phases: dict[str, int] = {}
        self._current_phase: str | None = None
        self._start_time: int | None = None

    def start(self, name: str) -> None:
        if self._current_phase is not None:
            raise ValueError(f"Cannot start '{name}' while '{self._current_phase}' is running")
        if name in self._phases:
            raise ValueError(f"Phase '{name}' was already measured")
        self._current_phase = name
        self._start_time = self._clock()

    def stop(self, name: str) -> None:
        if self._current_phase != name:
            raise ValueError(f"Cannot stop '{name}', currently in '{self._current_phase}'")
        end_time = self._clock()
        assert self._start_time is not None
        duration = end_time - self._start_time
        if duration < 0:
            raise ValueError("Negative duration observed")
        self._phases[name] = duration
        self._current_phase = None
        self._start_time = None

    def measure(self, name: str):
        """Context manager to measure a phase."""
        class _Context:
            def __init__(self, timer: PhaseTimer, phase_name: str):
                self.timer = timer
                self.phase_name = phase_name

            def __enter__(self):
                self.timer.start(self.phase_name)

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.timer.stop(self.phase_name)

        return _Context(self, name)

    def snapshot(self) -> dict[str, int]:
        """Return a defensive copy of the collected phase durations in nanoseconds."""
        return dict(self._phases)
