"""Bounded ownership-aware synchronization primitives for M1.92."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

from .async_core import AsyncErrorCode, AsyncFuture, complete, fail, pending
from .results import Result


class SyncErrorCode(Enum):
    INVALID_STATE = "invalid_state"
    OWNERSHIP = "ownership"
    RESOURCE_LIMIT = "resource_limit"


@dataclass(frozen=True, slots=True)
class SyncError:
    code: SyncErrorCode
    operation: str
    detail: str


def _task_id(task_id: int) -> SyncError | None:
    if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id < 0:
        return SyncError(SyncErrorCode.INVALID_STATE, "task", "task id must be a non-negative integer")
    return None


@dataclass(slots=True)
class MutexGuard:
    _mutex: BoundedMutex
    task_id: int
    _released: bool = False

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> Result[None, SyncError]:
        return self._mutex._release_guard(self)


class BoundedMutex:
    """FIFO mutex with explicit guard ownership and bounded wake storage."""

    def __init__(self, *, max_waiters: int = 64) -> None:
        if isinstance(max_waiters, bool) or not isinstance(max_waiters, int) or max_waiters <= 0:
            raise ValueError("max_waiters must be a positive integer")
        self.max_waiters = max_waiters
        self._owner: int | None = None
        self._waiters: deque[int] = deque()
        self._granted: set[int] = set()
        self._wakeups: deque[int] = deque()

    @property
    def owner(self) -> int | None:
        return self._owner

    @property
    def waiter_count(self) -> int:
        return len(self._waiters)

    def acquire(self, task_id: int) -> Result[MutexGuard | None, SyncError]:
        error = _task_id(task_id)
        if error is not None:
            return Result.err(error)
        if task_id in self._granted and self._owner == task_id:
            self._granted.remove(task_id)
            self._forget_wakeup(task_id)
            return Result.ok(MutexGuard(self, task_id))
        if self._owner is None:
            self._owner = task_id
            return Result.ok(MutexGuard(self, task_id))
        if self._owner == task_id or task_id in self._waiters or task_id in self._granted:
            return Result.err(SyncError(SyncErrorCode.INVALID_STATE, "acquire", "task already owns or waits for the mutex"))
        if len(self._waiters) >= self.max_waiters:
            return Result.err(SyncError(SyncErrorCode.RESOURCE_LIMIT, "acquire", "mutex waiter limit exceeded"))
        self._waiters.append(task_id)
        return Result.ok(None)

    def acquire_async(self, task_id: int) -> AsyncFuture[MutexGuard]:
        """Return a resumable, ownership-aware mutex acquisition future."""

        error = _task_id(task_id)
        if error is not None:
            return AsyncFuture(lambda _frame: fail(AsyncErrorCode.INVALID_STATE, "acquire", error.detail))
        registered = False

        def step(_frame):
            nonlocal registered
            if task_id in self._granted and self._owner == task_id:
                self._granted.remove(task_id)
                self._forget_wakeup(task_id)
                return complete(MutexGuard(self, task_id))
            if self._owner is None:
                self._owner = task_id
                return complete(MutexGuard(self, task_id))
            if self._owner == task_id:
                return fail(AsyncErrorCode.INVALID_STATE, "acquire", "task already owns the mutex")
            if task_id not in self._waiters and task_id not in self._granted:
                if len(self._waiters) >= self.max_waiters:
                    return fail(AsyncErrorCode.FRAME_LIMIT, "acquire", "mutex waiter limit exceeded")
                self._waiters.append(task_id)
                registered = True
            if task_id in self._waiters or registered:
                return pending()
            return fail(AsyncErrorCode.INVALID_STATE, "acquire", "mutex acquisition is unavailable")

        return AsyncFuture(step, cancel_hook=lambda: self.cancel_wait(task_id))

    def cancel_wait(self, task_id: int) -> Result[None, SyncError]:
        error = _task_id(task_id)
        if error is not None:
            return Result.err(error)
        if task_id in self._granted:
            self._granted.remove(task_id)
            if self._owner == task_id:
                self._owner = None
                self._promote_next()
            self._forget_wakeup(task_id)
            return Result.ok(None)
        if task_id not in self._waiters:
            return Result.err(SyncError(SyncErrorCode.INVALID_STATE, "cancel_wait", "task is not waiting"))
        self._waiters.remove(task_id)
        self._forget_wakeup(task_id)
        return Result.ok(None)

    def drain_wakeups(self) -> tuple[int, ...]:
        result = tuple(self._wakeups)
        self._wakeups.clear()
        return result

    def _release_guard(self, guard: MutexGuard) -> Result[None, SyncError]:
        if guard._mutex is not self or guard._released:
            return Result.err(SyncError(SyncErrorCode.OWNERSHIP, "release", "guard was already released or belongs to another mutex"))
        if self._owner != guard.task_id:
            return Result.err(SyncError(SyncErrorCode.OWNERSHIP, "release", "task does not own the mutex"))
        guard._released = True
        self._owner = None
        self._promote_next()
        return Result.ok(None)

    def _promote_next(self) -> None:
        if self._owner is not None:
            return
        while self._waiters:
            next_task = self._waiters.popleft()
            self._owner = next_task
            self._granted.add(next_task)
            self._record_wakeup(next_task)
            return

    def _record_wakeup(self, task_id: int) -> None:
        if task_id in self._wakeups:
            return
        if len(self._wakeups) >= self.max_waiters:
            raise RuntimeError("mutex wake storage bound was exceeded")
        self._wakeups.append(task_id)

    def _forget_wakeup(self, task_id: int) -> None:
        try:
            self._wakeups.remove(task_id)
        except ValueError:
            pass

    @property
    def wake_storage_count(self) -> int:
        return len(self._wakeups)


class BoundedEvent:
    """Deterministic manual- or auto-reset event with bounded waiters."""

    def __init__(self, *, max_waiters: int = 64, auto_reset: bool = False) -> None:
        if isinstance(max_waiters, bool) or not isinstance(max_waiters, int) or max_waiters <= 0:
            raise ValueError("max_waiters must be a positive integer")
        if not isinstance(auto_reset, bool):
            raise TypeError("auto_reset must be boolean")
        self.max_waiters = max_waiters
        self.auto_reset = auto_reset
        self._set = False
        self._waiters: deque[int] = deque()
        self._granted: set[int] = set()
        self._wakeups: deque[int] = deque()

    @property
    def is_set(self) -> bool:
        return self._set

    @property
    def waiter_count(self) -> int:
        return len(self._waiters)

    def wait(self, task_id: int) -> Result[bool, SyncError]:
        error = _task_id(task_id)
        if error is not None:
            return Result.err(error)
        if task_id in self._granted:
            self._granted.remove(task_id)
            self._forget_wakeup(task_id)
            return Result.ok(True)
        if self._set:
            if self.auto_reset:
                self._set = False
            return Result.ok(True)
        if task_id in self._waiters:
            return Result.err(SyncError(SyncErrorCode.INVALID_STATE, "wait", "task is already waiting"))
        if len(self._waiters) >= self.max_waiters:
            return Result.err(SyncError(SyncErrorCode.RESOURCE_LIMIT, "wait", "event waiter limit exceeded"))
        self._waiters.append(task_id)
        return Result.ok(False)

    def wait_async(self, task_id: int) -> AsyncFuture[bool]:
        """Return a resumable event wait whose wake grant cannot be lost."""

        error = _task_id(task_id)
        if error is not None:
            return AsyncFuture(lambda _frame: fail(AsyncErrorCode.INVALID_STATE, "wait", error.detail))
        registered = False

        def step(_frame):
            nonlocal registered
            if task_id in self._granted:
                self._granted.remove(task_id)
                self._forget_wakeup(task_id)
                return complete(True)
            if self._set and not self.auto_reset:
                return complete(True)
            if self._set and self.auto_reset:
                self._set = False
                return complete(True)
            if task_id not in self._waiters:
                if len(self._waiters) >= self.max_waiters:
                    return fail(AsyncErrorCode.FRAME_LIMIT, "wait", "event waiter limit exceeded")
                self._waiters.append(task_id)
                registered = True
            if task_id in self._waiters or registered:
                return pending()
            return fail(AsyncErrorCode.INVALID_STATE, "wait", "event wait is unavailable")

        return AsyncFuture(step, cancel_hook=lambda: self.cancel_wait(task_id))

    def set(self) -> Result[None, SyncError]:
        self._set = True
        if self.auto_reset:
            if self._waiters:
                task_id = self._waiters.popleft()
                self._granted.add(task_id)
                self._record_wakeup(task_id)
                self._set = False
            return Result.ok(None)
        while self._waiters:
            task_id = self._waiters.popleft()
            self._granted.add(task_id)
            self._record_wakeup(task_id)
        return Result.ok(None)

    def clear(self) -> Result[None, SyncError]:
        self._set = False
        return Result.ok(None)

    def cancel_wait(self, task_id: int) -> Result[None, SyncError]:
        error = _task_id(task_id)
        if error is not None:
            return Result.err(error)
        if task_id in self._granted:
            self._granted.remove(task_id)
            self._forget_wakeup(task_id)
            return Result.ok(None)
        if task_id not in self._waiters:
            return Result.err(SyncError(SyncErrorCode.INVALID_STATE, "cancel_wait", "task is not waiting"))
        self._waiters.remove(task_id)
        self._forget_wakeup(task_id)
        return Result.ok(None)

    def drain_wakeups(self) -> tuple[int, ...]:
        result = tuple(self._wakeups)
        self._wakeups.clear()
        return result

    def _record_wakeup(self, task_id: int) -> None:
        if task_id in self._wakeups:
            return
        if len(self._wakeups) >= self.max_waiters:
            raise RuntimeError("event wake storage bound was exceeded")
        self._wakeups.append(task_id)

    def _forget_wakeup(self, task_id: int) -> None:
        try:
            self._wakeups.remove(task_id)
        except ValueError:
            pass

    @property
    def wake_storage_count(self) -> int:
        return len(self._wakeups)
