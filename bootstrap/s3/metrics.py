"""Internal telemetry and metrics collection for the S3 toolchain."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class EmulationMetrics:
    """Metrics collected during an emulation run."""

    executed_s3_opcodes: int = 0
    maximum_frame_depth_observed: int = 0
    # Counts only TCALLs. The entry into 'main' is not counted.
    function_call_count: int = 0


class PhaseTimer:
    """A simple timer to measure non-overlapping pipeline phases."""

    def __init__(self, clock: Callable[[], int] | None = None):
        self._clock = clock if clock is not None else time.perf_counter_ns
        self._phases: dict[str, int] = {}
        self._current_phase: str | None = None
        self._start_time: int | None = None

    def start(self, name: str) -> None:
        if self._current_phase is not None:
            raise ValueError(f"Cannot start '{name}' while '{self._current_phase}' is running")
        if name in self._phases:
            raise ValueError(f"Phase '{name}' was already measured")
        start_time = self._clock()
        self._current_phase = name
        self._start_time = start_time

    def stop(self, name: str) -> None:
        if self._current_phase != name:
            raise ValueError(f"Cannot stop '{name}', currently in '{self._current_phase}'")
        if self._start_time is None:
            raise ValueError(f"Phase '{name}' was never started")

        start_time = self._start_time
        try:
            end_time = self._clock()
        finally:
            self._current_phase = None
            self._start_time = None

        duration = end_time - start_time
        if duration < 0:
            raise ValueError("Negative duration observed")

        self._phases[name] = duration

    def measure(self, name: str):
        """Context manager to measure a phase."""
        class _Context:
            def __init__(self, timer: PhaseTimer, phase_name: str):
                self.timer = timer
                self.phase_name = phase_name

            def __enter__(self):
                self.timer.start(self.phase_name)

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    self.timer.stop(self.phase_name)
                    return False

                assert exc_val is not None
                try:
                    self.timer.stop(self.phase_name)
                except BaseException as stop_exc:
                    raise BaseExceptionGroup(
                        "Phase execution and stop both failed",
                        [exc_val, stop_exc],
                    ) from None
                return False

        return _Context(self, name)

    def snapshot(self) -> dict[str, int]:
        """Return a defensive copy of the collected phase durations in nanoseconds."""
        if self._current_phase is not None:
            raise ValueError(f"Cannot snapshot while phase '{self._current_phase}' is active")
        return dict(self._phases)
