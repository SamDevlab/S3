"""Bounded structured tasks layered on the M1.71 async state machine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from .async_core import AsyncError, AsyncErrorCode, AsyncFuture, AsyncState, Poll, PollKind, Step
from .results import Result


T = TypeVar("T")


class TaskErrorCode(Enum):
    RESOURCE_LIMIT = "resource_limit"
    JOINED = "joined"
    ESCAPED = "escaped"
    CHILD_FAILED = "child_failed"
    UNFINISHED = "unfinished"
    INVALID_STATE = "invalid_state"


@dataclass(frozen=True, slots=True)
class TaskError:
    code: TaskErrorCode
    operation: str
    detail: str


class TaskHandle(Generic[T]):
    """An owned child handle. Joining consumes its exact terminal result once."""

    def __init__(self, identifier: int, future: AsyncFuture[T], owner: TaskGroup) -> None:
        self.identifier = identifier
        self._future = future
        self._owner = owner
        self._joined = False
        self._terminal_poll: Poll[T] | None = None

    @property
    def joined(self) -> bool:
        return self._joined

    @property
    def state(self) -> AsyncState:
        return self._future.state

    def poll(self) -> Poll[T] | TaskError:
        if self._joined:
            return TaskError(TaskErrorCode.JOINED, "poll", "task handle was already joined")
        if self._terminal_poll is not None:
            return self._terminal_poll
        outcome = self._future.poll()
        if outcome.kind in {PollKind.READY, PollKind.FAILED} and outcome.state in {
            AsyncState.COMPLETED,
            AsyncState.FAILED,
            AsyncState.CANCELLED,
        }:
            self._terminal_poll = outcome
        return outcome

    def join(self) -> Result[Poll[T], TaskError]:
        if self._joined:
            return Result.err(TaskError(TaskErrorCode.JOINED, "join", "task handle was already joined"))
        if self._future.state not in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}:
            return Result.err(TaskError(TaskErrorCode.UNFINISHED, "join", "task is not terminal"))
        if self._terminal_poll is None:
            return Result.err(TaskError(TaskErrorCode.INVALID_STATE, "join", "terminal task result was not retained by its owned handle"))
        self._joined = True
        return Result.ok(self._terminal_poll)

    def cancel(self) -> Result[None, TaskError]:
        if self._joined:
            return Result.err(TaskError(TaskErrorCode.JOINED, "cancel", "task handle was already joined"))
        if self._terminal_poll is not None:
            return Result.err(TaskError(TaskErrorCode.INVALID_STATE, "cancel", "task is already terminal"))
        result = self._future.cancel()
        if result.is_err:
            error = result.error_or(None)
            return Result.err(TaskError(TaskErrorCode.INVALID_STATE, "cancel", error.detail))
        self._terminal_poll = Poll.failed(
            AsyncState.CANCELLED,
            AsyncError(AsyncErrorCode.CANCELLED, "cancel", "task was cancelled"),
        )
        return Result.ok(None)


class TaskGroup:
    """A deterministic parent scope that owns every admitted child."""

    def __init__(self, *, max_children: int = 64, parent: TaskGroup | None = None) -> None:
        if isinstance(max_children, bool) or not isinstance(max_children, int) or max_children <= 0:
            raise ValueError("max_children must be a positive integer")
        self.max_children = max_children
        self.parent = parent
        self._children: list[TaskHandle[object]] = []
        self._next_id = 0
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def children(self) -> tuple[TaskHandle[object], ...]:
        return tuple(self._children)

    def spawn(self, future: AsyncFuture[T]) -> Result[TaskHandle[T], TaskError]:
        if self._closed:
            return Result.err(TaskError(TaskErrorCode.INVALID_STATE, "spawn", "task group is closed"))
        if not isinstance(future, AsyncFuture):
            return Result.err(TaskError(TaskErrorCode.INVALID_STATE, "spawn", "spawn requires an owned future"))
        if len(self._children) >= self.max_children:
            return Result.err(TaskError(TaskErrorCode.RESOURCE_LIMIT, "spawn", "task group child limit exceeded"))
        handle: TaskHandle[T] = TaskHandle(self._next_id, future, self)
        self._next_id += 1
        self._children.append(handle)  # type: ignore[arg-type]
        return Result.ok(handle)

    def spawn_step(self, step: Step[T]) -> Result[TaskHandle[T], TaskError]:
        return self.spawn(AsyncFuture(step))

    def poll_once(self) -> tuple[tuple[int, Poll[object]], ...] | TaskError:
        if self._closed:
            return TaskError(TaskErrorCode.INVALID_STATE, "poll", "task group is closed")
        results: list[tuple[int, Poll[object]]] = []
        for handle in self._children:
            if handle.joined or handle.state in {AsyncState.COMPLETED, AsyncState.CANCELLED}:
                continue
            outcome = handle.poll()
            if isinstance(outcome, TaskError):
                return outcome
            results.append((handle.identifier, outcome))
            if outcome.kind is PollKind.FAILED and outcome.error is not None:
                self._cancel_unfinished()
                return TaskError(TaskErrorCode.CHILD_FAILED, "poll", outcome.error.detail)
        return tuple(results)

    def close(self, *, cancel_unfinished: bool = True) -> Result[None, TaskError]:
        if self._closed:
            return Result.ok(None)
        unfinished = [handle for handle in self._children if handle.state not in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}]
        if unfinished and not cancel_unfinished:
            return Result.err(TaskError(TaskErrorCode.UNFINISHED, "close", "child task escaped its scope"))
        if unfinished:
            self._cancel_unfinished()
        if any(handle.state not in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED} for handle in self._children):
            return Result.err(TaskError(TaskErrorCode.UNFINISHED, "close", "child cancellation did not reach terminal state"))
        self._closed = True
        return Result.ok(None)

    def _cancel_unfinished(self) -> None:
        for handle in self._children:
            if handle.state not in {AsyncState.COMPLETED, AsyncState.FAILED, AsyncState.CANCELLED}:
                handle.cancel()

    def __enter__(self) -> TaskGroup:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.close(cancel_unfinished=True)


def task_failure(error: AsyncError) -> TaskError:
    code = TaskErrorCode.CHILD_FAILED
    if error.code is AsyncErrorCode.CANCELLED:
        code = TaskErrorCode.INVALID_STATE
    return TaskError(code, "task", error.detail)
