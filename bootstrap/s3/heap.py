"""Bounded, identity-based heap storage for the M1.32 foundation.

Heap handles are opaque logical identities.  They are deliberately not host
addresses and cannot be converted to pointers or used after the heap closes.
The foundation has no free, GC, RC, or implicit lifetime extension.
"""

from __future__ import annotations

from dataclasses import dataclass


class HeapError(RuntimeError):
    """Base error for deterministic heap boundary violations."""


class HeapLimitError(HeapError):
    """Raised when an allocation would exceed the configured heap limit."""


class HeapIdentityError(HeapError):
    """Raised when a handle does not belong to this heap instance."""


class HeapClosedError(HeapError):
    """Raised when a closed heap or one of its handles is used."""


class HeapBoundsError(HeapError):
    """Raised for an access outside an allocation's element range."""


@dataclass(frozen=True, slots=True)
class HeapConfig:
    """Deterministic limits for one heap instance."""

    max_allocations: int = 1024
    max_elements: int = 6561

    def __post_init__(self) -> None:
        if self.max_allocations < 1:
            raise ValueError("max_allocations must be at least 1")
        if self.max_elements < 1:
            raise ValueError("max_elements must be at least 1")


@dataclass(frozen=True, slots=True)
class HeapHandle:
    """Opaque allocation identity scoped to one :class:`BoundedHeap`."""

    heap_id: int
    allocation_id: int
    length: int


@dataclass(slots=True)
class _Allocation:
    handle: HeapHandle
    values: list[int | None]


class BoundedHeap:
    """A deterministic, bounded store with explicit allocation identities."""

    def __init__(self, config: HeapConfig = HeapConfig(), *, heap_id: int = 1):
        if heap_id < 1:
            raise ValueError("heap_id must be at least 1")
        self.config = config
        self.heap_id = heap_id
        self._next_allocation_id = 0
        self._used_elements = 0
        self._allocations: dict[int, _Allocation] = {}
        self._closed = False

    @property
    def allocation_count(self) -> int:
        return len(self._allocations)

    @property
    def used_elements(self) -> int:
        return self._used_elements

    def allocate(self, length: int) -> HeapHandle:
        self._require_open()
        if length < 1:
            raise ValueError("allocation length must be at least 1")
        if self.allocation_count >= self.config.max_allocations:
            raise HeapLimitError(
                f"allocation limit {self.config.max_allocations} exceeded"
            )
        if self._used_elements + length > self.config.max_elements:
            raise HeapLimitError(
                f"heap element limit {self.config.max_elements} exceeded"
            )
        self._next_allocation_id += 1
        handle = HeapHandle(self.heap_id, self._next_allocation_id, length)
        self._allocations[handle.allocation_id] = _Allocation(
            handle, [None] * length
        )
        self._used_elements += length
        return handle

    def read(self, handle: HeapHandle, index: int) -> int | None:
        allocation = self._get(handle, index)
        return allocation.values[index]

    def write(self, handle: HeapHandle, index: int, value: int | None) -> None:
        allocation = self._get(handle, index)
        allocation.values[index] = value

    def snapshot(self) -> tuple[tuple[int, tuple[int | None, ...]], ...]:
        """Return a stable logical snapshot ordered by allocation identity."""

        self._require_open()
        return tuple(
            (allocation.handle.allocation_id, tuple(allocation.values))
            for allocation in sorted(
                self._allocations.values(), key=lambda item: item.handle.allocation_id
            )
        )

    def close(self) -> None:
        """End this heap lifetime without reclaiming through a handle."""

        self._closed = True
        self._allocations.clear()
        self._used_elements = 0

    def _get(self, handle: HeapHandle, index: int) -> _Allocation:
        self._require_open()
        if handle.heap_id != self.heap_id:
            raise HeapIdentityError("heap handle belongs to a different heap")
        allocation = self._allocations.get(handle.allocation_id)
        if allocation is None or allocation.handle != handle:
            raise HeapIdentityError("unknown or stale heap handle")
        if not 0 <= index < handle.length:
            raise HeapBoundsError(
                f"heap index {index} outside allocation length {handle.length}"
            )
        return allocation

    def _require_open(self) -> None:
        if self._closed:
            raise HeapClosedError("heap is closed")
