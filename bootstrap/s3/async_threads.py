"""Bounded multithread async execution and transfer-safe values for M1.83."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from .async_core import AsyncState, Poll, PollKind
from .async_futures import FutureErrorCode, MoveOnlyFuture
from .results import Result


T = TypeVar("T")


class ThreadExecutorErrorCode(Enum):
    OWNERSHIP = "ownership"
    UNSAFE_TRANSFER = "unsafe_transfer"
    RESOURCE_LIMIT = "resource_limit"
    INVALID_STATE = "invalid_state"
    UNKNOWN_TASK = "unknown_task"
    QUEUE_FULL = "queue_full"


@dataclass(frozen=True, slots=True)
class ThreadExecutorError:
    code: ThreadExecutorErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class TransferValue(Generic[T]):
    """An immutable, closed value admitted to a worker boundary."""

    value: T

    @classmethod
    def create(cls, value: T) -> Result[TransferValue[T], ThreadExecutorError]:
        if not _transfer_safe(value):
            return Result.err(ThreadExecutorError(ThreadExecutorErrorCode.UNSAFE_TRANSFER, "transfer", "value is not in the closed transfer domain"))
        return Result.ok(cls(value))


@dataclass(frozen=True, slots=True)
class ThreadPoll(Generic[T]):
    task_id: int
    poll: Poll[T]
    worker_index: int


@dataclass(frozen=True, slots=True)
class ThreadExecutorLimits:
    max_workers: int = 2
    max_tasks: int = 64
    max_ready: int = 128

    def __post_init__(self) -> None:
        values = (self.max_workers, self.max_tasks, self.max_ready)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("thread executor limits must be positive integers")
        if self.max_workers > self.max_tasks:
            raise ValueError("worker count cannot exceed task limit")


@dataclass(slots=True)
class _Task:
    owner: MoveOnlyFuture[object]
    transfer: TransferValue[object] | None


class BoundedThreadExecutor:
    """Fixed-worker executor with explicit admission and wakeup bounds."""

    def __init__(self, *, limits: ThreadExecutorLimits | None = None) -> None:
        self.limits = limits or ThreadExecutorLimits()
        self._queue: queue.Queue[int | None] = queue.Queue(maxsize=self.limits.max_ready)
        self._tasks: dict[int, _Task] = {}
        self._queued: set[int] = set()
        self._polls: list[ThreadPoll[object]] = []
        self._lock = threading.Lock()
        self._closed = False
        self._next_task = 0
        self._workers = tuple(
            threading.Thread(target=self._worker, args=(index,), name=f"s3-async-{index}")
            for index in range(self.limits.max_workers)
        )
        for worker in self._workers:
            worker.start()

    @property
    def task_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    @property
    def alive_workers(self) -> int:
        return sum(worker.is_alive() for worker in self._workers)

    def spawn(
        self,
        owner: MoveOnlyFuture[T],
        *,
        transfer: TransferValue[object] | None = None,
    ) -> Result[int, ThreadExecutorError]:
        if not isinstance(owner, MoveOnlyFuture):
            return Result.err(ThreadExecutorError(ThreadExecutorErrorCode.OWNERSHIP, "spawn", "spawn requires an owned Future"))
        with self._lock:
            if self._closed:
                return Result.err(ThreadExecutorError(ThreadExecutorErrorCode.INVALID_STATE, "spawn", "executor is closed"))
            if len(self._tasks) >= self.limits.max_tasks:
                return Result.err(ThreadExecutorError(ThreadExecutorErrorCode.RESOURCE_LIMIT, "spawn", "task limit exceeded"))
        moved = owner.move()
        if moved.is_err:
            error = moved.error_or(None)
            return Result.err(ThreadExecutorError(ThreadExecutorErrorCode.OWNERSHIP, "spawn", error.detail))
        with self._lock:
            identifier = self._next_task
            self._next_task += 1
            self._tasks[identifier] = _Task(moved.value_or(None), transfer)
        queued = self.wake(identifier)
        if queued.is_err:
            with self._lock:
                self._tasks.pop(identifier, None)
            return Result.err(queued.error_or(None))
        return Result.ok(identifier)

    def wake(self, task_id: int) -> Result[None, ThreadExecutorError]:
        with self._lock:
            if self._closed:
                return Result.err(ThreadExecutorError(ThreadExecutorErrorCode.INVALID_STATE, "wake", "executor is closed"))
            task = self._tasks.get(task_id)
            if task is None:
                return Result.err(ThreadExecutorError(ThreadExecutorErrorCode.UNKNOWN_TASK, "wake", "task is unknown"))
            if task.owner.state in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}:
                return Result.ok(None)
            if task_id in self._queued:
                return Result.ok(None)
            if self._queue.full():
                return Result.err(ThreadExecutorError(ThreadExecutorErrorCode.QUEUE_FULL, "wake", "ready queue is full"))
            self._queued.add(task_id)
            self._queue.put_nowait(task_id)
            return Result.ok(None)

    def take_polls(self) -> tuple[ThreadPoll[object], ...]:
        with self._lock:
            result = tuple(self._polls)
            self._polls.clear()
            return result

    def close(self) -> Result[None, ThreadExecutorError]:
        with self._lock:
            if self._closed:
                return Result.ok(None)
            self._closed = True
            tasks = tuple(self._tasks.values())
        for task in tasks:
            if task.owner.state not in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}:
                task.owner.cancel()
        for _worker in self._workers:
            self._queue.put(None)
        for worker in self._workers:
            worker.join()
        with self._lock:
            self._queued.clear()
            self._tasks.clear()
        return Result.ok(None)

    def _worker(self, worker_index: int) -> None:
        while True:
            task_id = self._queue.get()
            try:
                if task_id is None:
                    return
                with self._lock:
                    self._queued.discard(task_id)
                    task = self._tasks.get(task_id)
                if task is None:
                    continue
                outcome = task.owner.poll()
                with self._lock:
                    self._polls.append(ThreadPoll(task_id, outcome.value_or(None), worker_index))
            finally:
                self._queue.task_done()


def _transfer_safe(value: object) -> bool:
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return True
    if isinstance(value, tuple):
        return all(_transfer_safe(item) for item in value)
    return False
