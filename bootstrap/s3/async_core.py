"""Deterministic hosted async/await core for S3 M1.71.

The module models the normative state machine directly. It intentionally does
not use Python generators: a transition callback receives an explicit frame
and returns one explicit transition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, TypeVar

from .results import Result


T = TypeVar("T")
U = TypeVar("U")


class AsyncState(Enum):
    CREATED = "created"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PollKind(Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class AsyncErrorCode(Enum):
    INVALID_STATE = "invalid_state"
    OWNERSHIP = "ownership"
    BORROW_ACROSS_AWAIT = "borrow_across_await"
    FRAME_LIMIT = "frame_limit"
    CALLBACK_FAILURE = "callback_failure"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AsyncError:
    code: AsyncErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class Poll(Generic[T]):
    kind: PollKind
    state: AsyncState
    value: T | None = None
    error: AsyncError | None = None

    @classmethod
    def pending(cls, state: AsyncState) -> Poll[T]:
        return cls(PollKind.PENDING, state)

    @classmethod
    def ready(cls, state: AsyncState, value: T) -> Poll[T]:
        return cls(PollKind.READY, state, value=value)

    @classmethod
    def failed(cls, state: AsyncState, error: AsyncError) -> Poll[T]:
        return cls(PollKind.FAILED, state, error=error)


class OwnedSlot(Generic[T]):
    """A frame-owned value with observable move and exactly-once drop."""

    def __init__(self, value: T, drop: Callable[[T], None] | None = None) -> None:
        self._value = value
        self._drop = drop or _discard
        self._moved = False
        self._dropped = False

    @property
    def moved(self) -> bool:
        return self._moved

    @property
    def dropped(self) -> bool:
        return self._dropped

    def move(self) -> Result[T, AsyncError]:
        if self._moved or self._dropped:
            return Result.err(AsyncError(AsyncErrorCode.OWNERSHIP, "move", "frame slot was already consumed"))
        self._moved = True
        return Result.ok(self._value)

    def drop(self) -> Result[None, AsyncError]:
        if self._dropped:
            return Result.ok(None)
        self._dropped = True
        if not self._moved:
            self._drop(self._value)
        return Result.ok(None)


class BorrowToken:
    """A lexical borrow whose lifetime must end before suspension."""

    def __init__(self, frame: AsyncFrame, name: str) -> None:
        self._frame = frame
        self.name = name
        self._released = False

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._frame._borrows.remove(self)


@dataclass(slots=True)
class AsyncFrame:
    """Explicit state-machine storage for one async invocation."""

    max_slots: int = 64
    state: AsyncState = AsyncState.CREATED
    slots: dict[str, OwnedSlot[object]] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)
    _borrows: list[BorrowToken] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.max_slots, bool) or not isinstance(self.max_slots, int) or self.max_slots <= 0:
            raise ValueError("max_slots must be a positive integer")

    def own(self, name: str, value: object, drop: Callable[[object], None] | None = None) -> Result[None, AsyncError]:
        if not name or name in self.slots:
            return Result.err(AsyncError(AsyncErrorCode.OWNERSHIP, "own", "frame slot name is unavailable"))
        if len(self.slots) >= self.max_slots:
            return Result.err(AsyncError(AsyncErrorCode.FRAME_LIMIT, "own", "async frame slot limit exceeded"))
        self.slots[name] = OwnedSlot(value, drop)
        return Result.ok(None)

    def move(self, name: str) -> Result[object, AsyncError]:
        slot = self.slots.get(name)
        if slot is None:
            return Result.err(AsyncError(AsyncErrorCode.OWNERSHIP, "move", f"unknown frame slot {name!r}"))
        return slot.move()

    def borrow(self, name: str) -> Result[BorrowToken, AsyncError]:
        if not name:
            return Result.err(AsyncError(AsyncErrorCode.OWNERSHIP, "borrow", "borrow name must not be empty"))
        token = BorrowToken(self, name)
        self._borrows.append(token)
        return Result.ok(token)

    def suspend(self) -> Result[None, AsyncError]:
        if self._borrows:
            return Result.err(AsyncError(AsyncErrorCode.BORROW_ACROSS_AWAIT, "suspend", "ordinary lexical borrow is live across await"))
        self.state = AsyncState.SUSPENDED
        self.trace.append(AsyncState.SUSPENDED.value)
        return Result.ok(None)

    def complete(self) -> None:
        self.state = AsyncState.COMPLETED
        self.trace.append(AsyncState.COMPLETED.value)
        self.drop_owned()

    def fail(self, error: AsyncError) -> None:
        self.state = AsyncState.FAILED
        self.trace.append(f"{AsyncState.FAILED.value}:{error.code.value}")
        self.drop_owned()

    def cancel(self) -> None:
        self.state = AsyncState.CANCELLED
        self.trace.append(AsyncState.CANCELLED.value)
        self.drop_owned()

    def drop_owned(self) -> None:
        for name in sorted(self.slots):
            self.slots[name].drop()


@dataclass(frozen=True, slots=True)
class Pending:
    pass


@dataclass(frozen=True, slots=True)
class Complete(Generic[T]):
    value: T


@dataclass(frozen=True, slots=True)
class Fail:
    error: AsyncError


Transition = Pending | Complete[T] | Fail
Step = Callable[[AsyncFrame], Transition]


class AsyncFuture(Generic[T]):
    """Move-only future driven by one deterministic transition callback."""

    def __init__(self, step: Step[T], *, frame: AsyncFrame | None = None, cancel_hook: Callable[[], None] | None = None) -> None:
        if not callable(step):
            raise TypeError("async future step must be callable")
        if cancel_hook is not None and not callable(cancel_hook):
            raise TypeError("async future cancellation hook must be callable")
        self.frame = frame or AsyncFrame()
        self._step = step
        self._cancel_hook = cancel_hook
        self._terminal_consumed = False

    @property
    def state(self) -> AsyncState:
        return self.frame.state

    @property
    def terminal_consumed(self) -> bool:
        return self._terminal_consumed

    def poll(self) -> Poll[T]:
        if self._terminal_consumed:
            return Poll.failed(self.frame.state, AsyncError(AsyncErrorCode.INVALID_STATE, "poll", "terminal future was already consumed"))
        if self.frame.state is AsyncState.RUNNING:
            return Poll.failed(self.frame.state, AsyncError(AsyncErrorCode.INVALID_STATE, "poll", "re-entrant future poll is not allowed"))
        if self.frame.state in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}:
            self._terminal_consumed = True
            return Poll.failed(self.frame.state, AsyncError(AsyncErrorCode.INVALID_STATE, "poll", "future is already terminal"))
        self.frame.state = AsyncState.RUNNING
        self.frame.trace.append(AsyncState.RUNNING.value)
        try:
            transition = self._step(self.frame)
        except BaseException as error:
            failure = AsyncError(AsyncErrorCode.CALLBACK_FAILURE, "poll", type(error).__name__)
            self.frame.fail(failure)
            self._terminal_consumed = True
            return Poll.failed(self.frame.state, failure)
        if isinstance(transition, Pending):
            suspended = self.frame.suspend()
            if suspended.is_err:
                error = suspended.error_or(None)
                self.frame.fail(error)
                self._terminal_consumed = True
                return Poll.failed(self.frame.state, error)
            return Poll.pending(self.frame.state)
        if isinstance(transition, Complete):
            self.frame.complete()
            self._terminal_consumed = True
            return Poll.ready(self.frame.state, transition.value)
        if isinstance(transition, Fail):
            self.frame.fail(transition.error)
            self._terminal_consumed = True
            return Poll.failed(self.frame.state, transition.error)
        error = AsyncError(AsyncErrorCode.CALLBACK_FAILURE, "poll", "step returned an invalid transition")
        self.frame.fail(error)
        self._terminal_consumed = True
        return Poll.failed(self.frame.state, error)

    def cancel(self) -> Result[None, AsyncError]:
        if self._terminal_consumed:
            return Result.err(AsyncError(AsyncErrorCode.INVALID_STATE, "cancel", "future was already consumed"))
        if self.frame.state is AsyncState.RUNNING:
            return Result.err(AsyncError(AsyncErrorCode.INVALID_STATE, "cancel", "running future cannot be cancelled re-entrantly"))
        if self.frame.state in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}:
            return Result.err(AsyncError(AsyncErrorCode.INVALID_STATE, "cancel", "future is already terminal"))
        if self._cancel_hook is not None:
            try:
                self._cancel_hook()
            except BaseException as error:
                failure = AsyncError(AsyncErrorCode.CALLBACK_FAILURE, "cancel", type(error).__name__)
                self.frame.fail(failure)
                self._terminal_consumed = True
                return Result.err(failure)
        self.frame.cancel()
        self._terminal_consumed = True
        return Result.ok(None)

    def abandon(self) -> Result[None, AsyncError]:
        return self.cancel()


def pending() -> Pending:
    return Pending()


def complete(value: T) -> Complete[T]:
    return Complete(value)


def fail(code: AsyncErrorCode, operation: str, detail: str) -> Fail:
    return Fail(AsyncError(code, operation, detail))


def _discard(_value: object) -> None:
    return None
