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
    UNSAFE_SHARED_STATE = "unsafe_shared_state"


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
        self._reserved_active = 0

    @property
    def active_count(self) -> int:
        """Return active execution reservations, excluding completed handles."""

        with self._lock:
            return self._reserved_active

    def spawn(
        self,
        entry: Callable[[T], U],
        argument: T | OwnedValue[T],
    ) -> Result[ThreadHandle[U], ThreadError]:
        if not callable(entry):
            return Result.err(ThreadError(ThreadErrorCode.INVALID_ENTRY, "spawn", "entry must be callable"))
        if not isinstance(argument, OwnedValue) and not _is_safe_direct_argument(argument):
            return Result.err(
                ThreadError(
                    ThreadErrorCode.UNSAFE_SHARED_STATE,
                    "spawn",
                    "direct thread arguments must be immutable or explicit synchronization roots",
                )
            )
        with self._lock:
            if self._reserved_active >= self._max_active:
                return Result.err(ThreadError(ThreadErrorCode.RESOURCE_LIMIT, "spawn", "active thread limit exceeded"))
            self._reserved_active += 1

        slot_released = False
        slot_release_lock = threading.Lock()

        def release_slot() -> None:
            nonlocal slot_released
            with slot_release_lock:
                if slot_released:
                    return
                slot_released = True
            with self._lock:
                self._reserved_active -= 1

        try:
            if isinstance(argument, OwnedValue):
                moved = argument.move()
                if moved.is_err:
                    release_slot()
                    return Result.err(moved.error_or(None))
                payload = moved.value_or(None)
            else:
                payload = argument
            result_box: dict[str, object] = {}

            def run() -> None:
                try:
                    result_box["result"] = entry(payload)  # type: ignore[arg-type]
                except BaseException as error:
                    result_box["result"] = ThreadError(
                        ThreadErrorCode.WORKER_FAILURE,
                        "worker",
                        type(error).__name__,
                    )
                finally:
                    release_slot()

            thread = threading.Thread(target=run, daemon=False)
            handle: ThreadHandle[U] = ThreadHandle(thread, result_box)
            with self._lock:
                self._handles.append(handle)  # type: ignore[arg-type]
            try:
                thread.start()
            except BaseException:
                with self._lock:
                    self._handles.remove(handle)  # type: ignore[arg-type]
                release_slot()
                raise
            return Result.ok(handle)
        except BaseException:
            release_slot()
            raise

    def join_all(self) -> tuple[Result[object, ThreadError], ...]:
        return tuple(handle.join() for handle in tuple(self._handles) if not handle.joined)


def _is_safe_direct_argument(value: object) -> bool:
    """Reject implicit mutable sharing while allowing explicit sync roots."""

    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return True
    if isinstance(value, tuple):
        return all(_is_safe_direct_argument(item) for item in value)
    if isinstance(value, frozenset):
        return all(_is_safe_direct_argument(item) for item in value)
    return bool(getattr(value, "__s3_thread_shareable__", False))
