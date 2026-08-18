from __future__ import annotations

from bootstrap.s3.results import Result
from bootstrap.s3.synchronization import (
    AtomicI64,
    MemoryOrder,
    Mutex,
    SyncErrorCode,
)
from bootstrap.s3.threads import ThreadRuntime


def _guard(mutex: Mutex[object], timeout_ms: int | None = None):
    result = mutex.lock(timeout_ms)
    assert result.is_ok
    return result.value_or(None)


def test_atomic_load_store_and_fetch_add_validate_orders_and_i64() -> None:
    atomic = AtomicI64(4)
    assert atomic.lock_free is False
    assert atomic.load(MemoryOrder.ACQUIRE).value_or(-1) == 4
    assert atomic.store(9, MemoryOrder.RELEASE).is_ok
    assert atomic.fetch_add(3, MemoryOrder.ACQ_REL).value_or(-1) == 9
    assert atomic.load(MemoryOrder.SEQ_CST).value_or(-1) == 12
    assert atomic.load(MemoryOrder.RELEASE).error_or(None).code is SyncErrorCode.INVALID_ORDER
    assert atomic.store(1, MemoryOrder.ACQUIRE).error_or(None).code is SyncErrorCode.INVALID_ORDER
    assert atomic.store(1 << 63, MemoryOrder.RELEASE).error_or(None).code is SyncErrorCode.INVALID_VALUE
    assert atomic.load([]).error_or(None).code is SyncErrorCode.INVALID_ORDER


def test_atomic_compare_exchange_reports_observed_value_and_ordering() -> None:
    atomic = AtomicI64(7)
    exchanged = atomic.compare_exchange(
        7, 8, MemoryOrder.ACQ_REL, MemoryOrder.ACQUIRE
    ).value_or(None)
    assert exchanged is not None
    assert exchanged.observed == 7 and exchanged.exchanged
    mismatch = atomic.compare_exchange(
        7, 9, MemoryOrder.SEQ_CST, MemoryOrder.ACQUIRE
    ).value_or(None)
    assert mismatch is not None
    assert mismatch.observed == 8 and not mismatch.exchanged
    invalid = atomic.compare_exchange(
        8, 9, MemoryOrder.RELAXED, MemoryOrder.ACQUIRE
    ).error_or(None)
    assert invalid.code is SyncErrorCode.ORDERING


def test_atomic_overflow_is_explicit_and_does_not_mutate() -> None:
    atomic = AtomicI64((1 << 63) - 1)
    failure = atomic.fetch_add(1, MemoryOrder.RELAXED).error_or(None)
    assert failure.code is SyncErrorCode.OVERFLOW
    assert atomic.load(MemoryOrder.RELAXED).value_or(0) == (1 << 63) - 1


def test_mutex_guard_controls_access_and_releases_deterministically() -> None:
    mutex: Mutex[object] = Mutex({"count": 1})
    guard = _guard(mutex)
    assert guard is not None
    assert guard.get().value_or({})["count"] == 1
    assert guard.set({"count": 2}).is_ok
    assert guard.release().is_ok
    assert guard.release().is_ok
    assert guard.get().error_or(None).code is SyncErrorCode.CLOSED
    assert _guard(mutex).get().value_or({})["count"] == 2


def test_mutex_timeout_and_bounded_multithread_counter() -> None:
    mutex: Mutex[int] = Mutex(0)
    held = _guard(mutex)
    assert held is not None
    blocked = mutex.lock(timeout_ms=0).error_or(None)
    assert blocked.code is SyncErrorCode.TIMEOUT
    assert held.release().is_ok

    runtime = ThreadRuntime(max_active=4)

    def increment(shared: Mutex[int]) -> int:
        for _ in range(100):
            guard_result = shared.lock(timeout_ms=1000)
            if guard_result.is_err:
                return -1
            guard = guard_result.value_or(None)
            assert guard is not None
            current = guard.get().value_or(-1)
            guard.set(current + 1)
            guard.release()
        return 100

    handles = [runtime.spawn(increment, mutex).value_or(None) for _ in range(4)]
    assert all(handle is not None for handle in handles)
    assert [handle.join().value_or(-1) for handle in handles] == [100] * 4
    final = _guard(mutex)
    assert final is not None
    assert final.get().value_or(-1) == 400
    final.release()


def test_mutex_context_manager_closes_guard() -> None:
    mutex: Mutex[int] = Mutex(3)
    result = mutex.lock()
    assert result.is_ok
    guard = result.value_or(None)
    assert guard is not None
    with guard as entered:
        assert entered.get().value_or(-1) == 3
    assert guard.closed


def test_public_operations_return_result_values() -> None:
    assert isinstance(AtomicI64().load(MemoryOrder.RELAXED), Result)
    assert isinstance(Mutex(1).lock(), Result)
