"""Bounded single-thread cooperative executor for S3 M1.73."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .async_core import AsyncFuture, AsyncState, Poll, PollKind
from .results import Result


class ExecutorErrorCode(Enum):
    RESOURCE_LIMIT = "resource_limit"
    INVALID_STATE = "invalid_state"
    UNKNOWN_TASK = "unknown_task"
    UNKNOWN_TIMER = "unknown_timer"
    UNKNOWN_REGISTRATION = "unknown_registration"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class ExecutorError:
    code: ExecutorErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class ExecutorLimits:
    max_tasks: int = 64
    max_queued_wakeups: int = 128
    max_timers: int = 128
    max_registrations: int = 128

    def __post_init__(self) -> None:
        values = (self.max_tasks, self.max_queued_wakeups, self.max_timers, self.max_registrations)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("executor limits must be positive integers")


class FakeClock:
    """Monotonic controllable clock for deterministic timer tests."""

    def __init__(self, initial: int = 0) -> None:
        if isinstance(initial, bool) or not isinstance(initial, int) or initial < 0:
            raise ValueError("clock initial value must be a non-negative integer")
        self._now = initial

    @property
    def now(self) -> int:
        return self._now

    def advance(self, delta: int) -> None:
        if isinstance(delta, bool) or not isinstance(delta, int) or delta < 0:
            raise ValueError("clock delta must be a non-negative integer")
        self._now += delta


@dataclass(slots=True)
class TimerHandle:
    identifier: int
    deadline: int
    task_id: int
    cancelled: bool = False


@dataclass(slots=True)
class ReactorRegistration:
    key: str
    task_id: int
    closed: bool = False


class DeterministicReactor:
    """Portable readiness registration with deterministic injected signals."""

    def __init__(self, max_registrations: int = 128) -> None:
        self._max = max_registrations
        self._registrations: dict[str, ReactorRegistration] = {}
        self._ready: set[str] = set()

    def register(self, key: str, task_id: int) -> Result[ReactorRegistration, ExecutorError]:
        if not key or key in self._registrations:
            return Result.err(ExecutorError(ExecutorErrorCode.DUPLICATE, "register", "reactor key is already registered"))
        if len(self._registrations) >= self._max:
            return Result.err(ExecutorError(ExecutorErrorCode.RESOURCE_LIMIT, "register", "reactor registration limit exceeded"))
        registration = ReactorRegistration(key, task_id)
        self._registrations[key] = registration
        return Result.ok(registration)

    def signal(self, key: str) -> Result[None, ExecutorError]:
        if key not in self._registrations:
            return Result.err(ExecutorError(ExecutorErrorCode.UNKNOWN_REGISTRATION, "signal", "reactor key is unknown"))
        self._ready.add(key)
        return Result.ok(None)

    def poll(self) -> tuple[int, ...]:
        keys = tuple(sorted(self._ready))
        self._ready.clear()
        return tuple(self._registrations[key].task_id for key in keys if not self._registrations[key].closed)

    def close(self, registration: ReactorRegistration) -> Result[None, ExecutorError]:
        current = self._registrations.get(registration.key)
        if current is None:
            return Result.err(ExecutorError(ExecutorErrorCode.UNKNOWN_REGISTRATION, "close", "reactor key is unknown"))
        current.closed = True
        self._registrations.pop(registration.key, None)
        self._ready.discard(registration.key)
        return Result.ok(None)


@dataclass(frozen=True, slots=True)
class RunReport:
    steps: int
    completed: tuple[int, ...]
    failed: tuple[int, ...]
    idle: bool


class AsyncExecutor:
    """Single-thread cooperative executor with bounded wake and timer state."""

    def __init__(self, *, limits: ExecutorLimits | None = None, clock: FakeClock | None = None) -> None:
        self.limits = limits or ExecutorLimits()
        self.clock = clock or FakeClock()
        self.reactor = DeterministicReactor(self.limits.max_registrations)
        self._tasks: dict[int, AsyncFuture[object]] = {}
        self._ready: deque[int] = deque()
        self._queued: set[int] = set()
        self._timers: dict[int, TimerHandle] = {}
        self._next_task = 0
        self._next_timer = 0
        self._closed = False

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def queued_wakeups(self) -> int:
        return len(self._queued)

    def spawn(self, future: AsyncFuture[object]) -> Result[int, ExecutorError]:
        if self._closed:
            return Result.err(ExecutorError(ExecutorErrorCode.INVALID_STATE, "spawn", "executor is closed"))
        if len(self._tasks) >= self.limits.max_tasks:
            return Result.err(ExecutorError(ExecutorErrorCode.RESOURCE_LIMIT, "spawn", "task limit exceeded"))
        identifier = self._next_task
        self._next_task += 1
        self._tasks[identifier] = future
        self.wake(identifier)
        return Result.ok(identifier)

    def wake(self, task_id: int) -> Result[None, ExecutorError]:
        if self._closed:
            return Result.err(ExecutorError(ExecutorErrorCode.INVALID_STATE, "wake", "executor is closed"))
        if task_id not in self._tasks:
            return Result.err(ExecutorError(ExecutorErrorCode.UNKNOWN_TASK, "wake", "task is unknown"))
        future = self._tasks[task_id]
        if future.state in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}:
            return Result.ok(None)
        if task_id in self._queued:
            return Result.ok(None)
        if len(self._queued) >= self.limits.max_queued_wakeups:
            return Result.err(ExecutorError(ExecutorErrorCode.RESOURCE_LIMIT, "wake", "queued wakeup limit exceeded"))
        self._queued.add(task_id)
        self._ready.append(task_id)
        return Result.ok(None)

    def call_at(self, deadline: int, task_id: int) -> Result[TimerHandle, ExecutorError]:
        if task_id not in self._tasks:
            return Result.err(ExecutorError(ExecutorErrorCode.UNKNOWN_TASK, "timer", "task is unknown"))
        if isinstance(deadline, bool) or not isinstance(deadline, int) or deadline < self.clock.now:
            return Result.err(ExecutorError(ExecutorErrorCode.INVALID_STATE, "timer", "deadline must be monotonic"))
        if len(self._timers) >= self.limits.max_timers:
            return Result.err(ExecutorError(ExecutorErrorCode.RESOURCE_LIMIT, "timer", "timer limit exceeded"))
        handle = TimerHandle(self._next_timer, deadline, task_id)
        self._next_timer += 1
        self._timers[handle.identifier] = handle
        return Result.ok(handle)

    def cancel_timer(self, timer: TimerHandle) -> Result[None, ExecutorError]:
        current = self._timers.get(timer.identifier)
        if current is None:
            return Result.err(ExecutorError(ExecutorErrorCode.UNKNOWN_TIMER, "cancel_timer", "timer is unknown"))
        current.cancelled = True
        self._timers.pop(timer.identifier, None)
        return Result.ok(None)

    def run_once(self) -> RunReport:
        self._fire_timers()
        for task_id in self.reactor.poll():
            self.wake(task_id)
        if not self._ready:
            return RunReport(0, (), (), True)
        task_id = self._ready.popleft()
        self._queued.discard(task_id)
        future = self._tasks[task_id]
        outcome = future.poll()
        if outcome.kind is PollKind.PENDING:
            return RunReport(1, (), (), not self._ready)
        if outcome.kind is PollKind.READY:
            return RunReport(1, (task_id,), (), not self._ready)
        return RunReport(1, (), (task_id,), not self._ready)

    def run_until_idle(self, *, max_steps: int = 1024) -> RunReport:
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self._fire_timers()
        for task_id in self.reactor.poll():
            self.wake(task_id)
        steps = 0
        completed: list[int] = []
        failed: list[int] = []
        while self._ready and steps < max_steps:
            report = self.run_once()
            steps += report.steps
            completed.extend(report.completed)
            failed.extend(report.failed)
        return RunReport(steps, tuple(completed), tuple(failed), not self._ready)

    def close(self) -> Result[None, ExecutorError]:
        if self._closed:
            return Result.ok(None)
        for future in self._tasks.values():
            if future.state not in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}:
                future.cancel()
        self._ready.clear()
        self._queued.clear()
        self._timers.clear()
        self._closed = True
        return Result.ok(None)

    def _fire_timers(self) -> None:
        due = tuple(sorted(timer.identifier for timer in self._timers.values() if timer.deadline <= self.clock.now and not timer.cancelled))
        for identifier in due:
            timer = self._timers.pop(identifier)
            self.wake(timer.task_id)
