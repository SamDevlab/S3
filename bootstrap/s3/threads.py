"""Explicit ownership-transfer thread primitives for M1.69."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Callable, Generic, TypeVar

from .results import Result


T = TypeVar("T")
U = TypeVar("U")


class ThreadErrorCode(Enum):
    INVALID_ENTRY = "invalid_entry"
    OWNERSHIP = "ownership"
    RESOURCE_LIMIT = "resource_limit"
    TIMEOUT = "timeout"
    JOINED = "joined"
    RUNNING = "running"
    WORKER_FAILURE = "worker_failure"


@dataclass(frozen=True, slots=True)
class ThreadError:
    code: ThreadErrorCode
    operation: str
    detail: str


class OwnedValue(Generic[T]):
    """A move-only wrapper used to make transfer consumption observable."""

    def __init__(self, value: T) -> None:
        self._value = value
        self._moved = False

    @property
    def moved(self) -> bool:
        return self._moved

    @property
    def value(self) -> Result[T, ThreadError]:
        if self._moved:
            return Result.err(ThreadError(ThreadErrorCode.OWNERSHIP, "read", "owned value was moved"))
        return Result.ok(self._value)

    def move(self) -> Result[T, ThreadError]:
        if self._moved:
            return Result.err(ThreadError(ThreadErrorCode.OWNERSHIP, "move", "owned value was already moved"))
        self._moved = True
        return Result.ok(self._value)


class ThreadHandle(Generic[T]):
    def __init__(self, thread: threading.Thread, result_box: dict[str, object]) -> None:
        self._thread = thread
        self._result_box = result_box
        self._joined = False

    @property
    def joined(self) -> bool:
        return self._joined

    @property
    def daemon(self) -> bool:
        return self._thread.daemon

    def join(self, timeout_ms: int | None = None) -> Result[T, ThreadError]:
        if self._joined:
            return Result.err(ThreadError(ThreadErrorCode.JOINED, "join", "thread was already joined"))
        if timeout_ms is not None and (isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0):
            return Result.err(ThreadError(ThreadErrorCode.TIMEOUT, "join", "timeout must be non-negative"))
        self._thread.join(None if timeout_ms is None else timeout_ms / 1000)
        if self._thread.is_alive():
            return Result.err(ThreadError(ThreadErrorCode.TIMEOUT, "join", "thread is still running"))
        self._joined = True
        result = self._result_box.get("result")
        if isinstance(result, ThreadError):
            return Result.err(result)
        return Result.ok(result)  # type: ignore[arg-type]

    def close(self) -> Result[None, ThreadError]:
        if self._joined:
            return Result.ok(None)
        if self._thread.is_alive():
            return Result.err(ThreadError(ThreadErrorCode.RUNNING, "close", "join is required before close"))
        self._joined = True
        return Result.ok(None)


class ThreadRuntime:
    """Bounded non-detached thread owner with explicit join lifecycle."""

    def __init__(self, *, max_active: int = 16) -> None:
        if isinstance(max_active, bool) or not isinstance(max_active, int) or max_active <= 0:
            raise ValueError("max_active must be positive")
        self._max_active = max_active
        self._handles: list[ThreadHandle[object]] = []
        self._lock = threading.Lock()

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(not handle.joined and handle._thread.is_alive() for handle in self._handles)

    def spawn(
        self,
        entry: Callable[[T], U],
        argument: T | OwnedValue[T],
    ) -> Result[ThreadHandle[U], ThreadError]:
        if not callable(entry):
            return Result.err(ThreadError(ThreadErrorCode.INVALID_ENTRY, "spawn", "entry must be callable"))
        with self._lock:
            active = sum(not handle.joined and handle._thread.is_alive() for handle in self._handles)
            if active >= self._max_active:
                return Result.err(ThreadError(ThreadErrorCode.RESOURCE_LIMIT, "spawn", "active thread limit exceeded"))
        if isinstance(argument, OwnedValue):
            moved = argument.move()
            if moved.is_err:
                return Result.err(moved.error_or(None))
            payload = moved.value_or(None)
        else:
            payload = argument
        result_box: dict[str, object] = {}

        def run() -> None:
            try:
                result_box["result"] = entry(payload)  # type: ignore[arg-type]
            except BaseException as error:
                result_box["result"] = ThreadError(ThreadErrorCode.WORKER_FAILURE, "worker", type(error).__name__)

        thread = threading.Thread(target=run, daemon=False)
        handle: ThreadHandle[U] = ThreadHandle(thread, result_box)
        with self._lock:
            self._handles.append(handle)  # type: ignore[arg-type]
        thread.start()
        return Result.ok(handle)

    def join_all(self) -> tuple[Result[object, ThreadError], ...]:
        return tuple(handle.join() for handle in tuple(self._handles) if not handle.joined)
