from __future__ import annotations

import pytest

from bootstrap.s3.heap import (
    BoundedHeap,
    HeapBoundsError,
    HeapClosedError,
    HeapConfig,
    HeapHandle,
    HeapIdentityError,
    HeapLimitError,
)


def test_heap_allocations_have_deterministic_logical_identity() -> None:
    heap = BoundedHeap(heap_id=7)
    first = heap.allocate(2)
    second = heap.allocate(1)

    assert first == HeapHandle(7, 1, 2)
    assert second == HeapHandle(7, 2, 1)
    assert heap.snapshot() == ((1, (None, None)), (2, (None,)))


def test_heap_storage_is_readable_writable_and_snapshot_stable() -> None:
    heap = BoundedHeap()
    handle = heap.allocate(2)

    heap.write(handle, 0, 11)
    heap.write(handle, 1, -3)

    assert heap.read(handle, 0) == 11
    assert heap.read(handle, 1) == -3
    assert heap.snapshot() == ((1, (11, -3)),)


def test_heap_rejects_element_and_allocation_limits() -> None:
    heap = BoundedHeap(HeapConfig(max_allocations=1, max_elements=2))
    heap.allocate(2)

    with pytest.raises(HeapLimitError):
        heap.allocate(1)

    limited_by_elements = BoundedHeap(HeapConfig(max_allocations=2, max_elements=2))
    limited_by_elements.allocate(1)
    with pytest.raises(HeapLimitError):
        limited_by_elements.allocate(2)


def test_heap_rejects_foreign_handles_and_out_of_bounds_access() -> None:
    heap = BoundedHeap(heap_id=1)
    other = BoundedHeap(heap_id=2)
    handle = heap.allocate(1)

    with pytest.raises(HeapIdentityError):
        other.read(handle, 0)
    with pytest.raises(HeapBoundsError):
        heap.read(handle, 1)


def test_heap_close_ends_heap_lifetime() -> None:
    heap = BoundedHeap()
    handle = heap.allocate(1)
    heap.close()

    with pytest.raises(HeapClosedError):
        heap.read(handle, 0)
