"""Bounded ownership-safe channels and deterministic select for M1.76."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from .async_core import AsyncFuture, AsyncFrame, complete, fail, pending
from .results import Result


T = TypeVar("T")


class ChannelErrorCode(Enum):
    FULL = "full"
    EMPTY = "empty"
    CLOSED = "closed"
    OWNERSHIP = "ownership"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ChannelError:
    code: ChannelErrorCode
    operation: str
    detail: str


class OwnedMessage(Generic[T]):
    """Move-only message ownership at the channel boundary."""

    def __init__(self, value: T) -> None:
        self._value = value
        self._moved = False

    @property
    def moved(self) -> bool:
        return self._moved

    def move(self) -> Result[T, ChannelError]:
        if self._moved:
            return Result.err(ChannelError(ChannelErrorCode.OWNERSHIP, "move", "message was already moved"))
        self._moved = True
        return Result.ok(self._value)


class AsyncChannel(Generic[T]):
    def __init__(self, capacity: int) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("channel capacity must be a positive integer")
        self.capacity = capacity
        self._queue: deque[T] = deque()
        self._closed = False
        self._senders = 0
        self._receivers = 0

    def split(self) -> tuple[Sender[T], Receiver[T]]:
        self._senders += 1
        self._receivers += 1
        return Sender(self), Receiver(self)

    @property
    def closed(self) -> bool:
        return self._closed

    def _send(self, message: OwnedMessage[T]) -> Result[None, ChannelError]:
        if self._closed or self._receivers == 0:
            return Result.err(ChannelError(ChannelErrorCode.CLOSED, "send", "channel has no receiver"))
        if len(self._queue) >= self.capacity:
            return Result.err(ChannelError(ChannelErrorCode.FULL, "send", "channel capacity is full"))
        moved = message.move()
        if moved.is_err:
            return Result.err(moved.error_or(None))
        self._queue.append(moved.value_or(None))
        return Result.ok(None)

    def _recv(self) -> Result[OwnedMessage[T], ChannelError]:
        if self._queue:
            return Result.ok(OwnedMessage(self._queue.popleft()))
        if self._closed or self._senders == 0:
            return Result.err(ChannelError(ChannelErrorCode.CLOSED, "recv", "channel is closed"))
        return Result.err(ChannelError(ChannelErrorCode.EMPTY, "recv", "channel has no message"))

    def _close_sender(self) -> None:
        self._senders = max(0, self._senders - 1)

    def _close_receiver(self) -> None:
        self._receivers = max(0, self._receivers - 1)
        if self._receivers == 0:
            self._closed = True


class Sender(Generic[T]):
    def __init__(self, channel: AsyncChannel[T]) -> None:
        self._channel = channel
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def send(self, message: OwnedMessage[T]) -> Result[None, ChannelError]:
        if self._closed:
            return Result.err(ChannelError(ChannelErrorCode.CLOSED, "send", "sender is closed"))
        return self._channel._send(message)

    def send_awaitable(self, message: OwnedMessage[T]) -> ChannelSendOperation[T]:
        return ChannelSendOperation(self, message)

    def clone(self) -> Result[Sender[T], ChannelError]:
        if self._closed or self._channel.closed:
            return Result.err(ChannelError(ChannelErrorCode.CLOSED, "clone", "sender is closed"))
        self._channel._senders += 1
        return Result.ok(Sender(self._channel))

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._channel._close_sender()


class Receiver(Generic[T]):
    def __init__(self, channel: AsyncChannel[T]) -> None:
        self._channel = channel
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def recv(self) -> Result[OwnedMessage[T], ChannelError]:
        if self._closed:
            return Result.err(ChannelError(ChannelErrorCode.CLOSED, "recv", "receiver is closed"))
        return self._channel._recv()

    def recv_awaitable(self) -> ChannelReceiveOperation[T]:
        return ChannelReceiveOperation(self)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._channel._close_receiver()


class ChannelSendOperation(Generic[T]):
    def __init__(self, sender: Sender[T], message: OwnedMessage[T]) -> None:
        self.sender = sender
        self.message = message
        self._future = AsyncFuture(self._step)

    def poll(self):
        return self._future.poll()

    def recover(self) -> OwnedMessage[T] | None:
        return self.message if not self.message.moved else None

    def _step(self, frame: AsyncFrame):
        if "channel-message" not in frame.slots:
            frame.own("channel-message", self.message)
        result = self.sender.send(self.message)
        if result.is_ok:
            frame.move("channel-message")
            return complete(None)
        error = result.error_or(None)
        if error.code is ChannelErrorCode.FULL:
            return pending()
        return fail(error.code, error.operation, error.detail)


class ChannelReceiveOperation(Generic[T]):
    def __init__(self, receiver: Receiver[T]) -> None:
        self.receiver = receiver
        self._future = AsyncFuture(self._step)

    def poll(self):
        return self._future.poll()

    def _step(self, _frame: AsyncFrame):
        result = self.receiver.recv()
        if result.is_ok:
            return complete(result.value_or(None))
        error = result.error_or(None)
        if error.code is ChannelErrorCode.EMPTY:
            return pending()
        return fail(error.code, error.operation, error.detail)


@dataclass(frozen=True, slots=True)
class SelectResult(Generic[T]):
    index: int
    message: OwnedMessage[T]


def select(receivers: tuple[Receiver[T], ...]) -> Result[SelectResult[T], ChannelError]:
    """Select the lowest-index ready receiver; never probes unordered state."""

    if not receivers:
        return Result.err(ChannelError(ChannelErrorCode.INVALID, "select", "select requires at least one receiver"))
    closed = True
    for index, receiver in enumerate(receivers):
        result = receiver.recv()
        if result.is_ok:
            return Result.ok(SelectResult(index, result.value_or(None)))
        error = result.error_or(None)
        if error.code is not ChannelErrorCode.CLOSED:
            closed = False
    if closed:
        return Result.err(ChannelError(ChannelErrorCode.CLOSED, "select", "all selected receivers are closed"))
    return Result.err(ChannelError(ChannelErrorCode.EMPTY, "select", "no selected operation is ready"))
