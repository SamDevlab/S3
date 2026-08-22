"""Bounded, ownership-neutral async runtime observability."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Mapping


class AsyncEventKind(str, Enum):
    CREATED = "task_created"
    SCHEDULED = "task_scheduled"
    POLLED = "task_polled"
    COMPLETED = "task_completed"
    CANCELLED = "task_cancelled"
    TIMER_REGISTERED = "timer_registered"
    TIMER_FIRED = "timer_fired"
    CHANNEL_SEND = "channel_send"
    CHANNEL_RECEIVE = "channel_receive"


@dataclass(frozen=True, slots=True)
class AsyncEvent:
    sequence: int
    kind: AsyncEventKind
    task_id: int | None = None
    resource: str | None = None
    detail: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("event sequence must be a non-negative integer")
        if self.task_id is not None and (isinstance(self.task_id, bool) or not isinstance(self.task_id, int) or self.task_id < 0):
            raise ValueError("event task_id must be a non-negative integer")
        if self.resource is not None and (not isinstance(self.resource, str) or not self.resource):
            raise ValueError("event resource must be non-empty")
        if tuple(sorted(self.detail)) != self.detail or any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.detail):
            raise ValueError("event detail must be sorted string pairs")


@dataclass(frozen=True, slots=True)
class AsyncTelemetrySnapshot:
    enabled: bool
    capacity: int
    retained: tuple[AsyncEvent, ...]
    dropped: int
    counts: tuple[tuple[str, int], ...]


class BoundedAsyncTelemetry:
    """Thread-safe bounded event sink; disabled mode stores no events."""

    def __init__(self, *, capacity: int = 256, enabled: bool = True) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("telemetry capacity must be a positive integer")
        if not isinstance(enabled, bool):
            raise TypeError("telemetry enabled must be boolean")
        self.capacity = capacity
        self.enabled = enabled
        self._events: deque[AsyncEvent] = deque(maxlen=capacity)
        self._counts: Counter[str] = Counter()
        self._dropped = 0
        self._sequence = 0
        self._lock = Lock()

    def record(self, kind: AsyncEventKind, *, task_id: int | None = None, resource: str | None = None, detail: Mapping[str, str] | None = None) -> None:
        if not isinstance(kind, AsyncEventKind):
            raise TypeError("telemetry kind must be an AsyncEventKind")
        if not self.enabled:
            return
        normalized = tuple(sorted((str(key), str(value)) for key, value in (detail or {}).items()))
        with self._lock:
            event = AsyncEvent(self._sequence, kind, task_id, resource, normalized)
            self._sequence += 1
            if len(self._events) == self.capacity:
                self._dropped += 1
            self._events.append(event)
            self._counts[kind.value] += 1

    def snapshot(self) -> AsyncTelemetrySnapshot:
        with self._lock:
            return AsyncTelemetrySnapshot(self.enabled, self.capacity, tuple(self._events), self._dropped, tuple(sorted(self._counts.items())))
