from __future__ import annotations

from bootstrap.s3.async_sync import BoundedEvent, BoundedMutex, SyncErrorCode


def test_mutex_is_fifo_and_double_unlock_is_rejected() -> None:
    mutex = BoundedMutex(max_waiters=2)
    first = mutex.acquire(10)
    guard = first.value_or(None)
    assert guard is not None
    assert mutex.acquire(20).value_or("waiting") is None
    assert mutex.acquire(21).value_or("waiting") is None
    assert guard.release().is_ok
    assert mutex.drain_wakeups() == (20,)
    promoted = mutex.acquire(20).value_or(None)
    assert promoted is not None
    assert promoted.release().is_ok
    assert mutex.drain_wakeups() == (21,)
    assert guard.release().error_or(None).code is SyncErrorCode.OWNERSHIP


def test_mutex_waiter_limit_and_cancellation_are_fail_closed() -> None:
    mutex = BoundedMutex(max_waiters=1)
    guard = mutex.acquire(1).value_or(None)
    assert guard is not None
    assert mutex.acquire(2).is_ok
    assert mutex.acquire(3).error_or(None).code is SyncErrorCode.RESOURCE_LIMIT
    assert mutex.cancel_wait(2).is_ok
    assert mutex.cancel_wait(2).error_or(None).code is SyncErrorCode.INVALID_STATE
    assert guard.release().is_ok
    assert mutex.drain_wakeups() == ()


def test_manual_event_wakes_all_waiters_in_registration_order() -> None:
    event = BoundedEvent(max_waiters=3)
    assert event.wait(4).value_or(True) is False
    assert event.wait(2).value_or(True) is False
    assert event.set().is_ok
    assert event.drain_wakeups() == (4, 2)
    assert event.wait(8).value_or(False) is True
    assert event.clear().is_ok
    assert event.wait(8).value_or(True) is False


def test_auto_event_releases_one_waiter_and_rejects_waiter_overflow() -> None:
    event = BoundedEvent(max_waiters=1, auto_reset=True)
    assert event.wait(1).value_or(True) is False
    assert event.wait(2).error_or(None).code is SyncErrorCode.RESOURCE_LIMIT
    assert event.set().is_ok
    assert event.drain_wakeups() == (1,)
    assert event.wait(3).value_or(False) is False
    assert event.set().is_ok
    assert event.drain_wakeups() == (3,)


def test_async_mutex_and_event_keep_wake_grants_until_the_owner_polls() -> None:
    mutex = BoundedMutex()
    first = mutex.acquire_async(1)
    guard = first.poll().value
    assert guard is not None
    waiter = mutex.acquire_async(2)
    assert waiter.poll().kind.value == "pending"
    assert guard.release().is_ok
    assert waiter.poll().kind.value == "ready"
    promoted = waiter.poll()
    assert promoted.kind.value == "failed"

    event = BoundedEvent(auto_reset=True)
    waiting = event.wait_async(4)
    assert waiting.poll().kind.value == "pending"
    assert event.set().is_ok
    assert waiting.poll().value is True
    cancelled = event.wait_async(5)
    assert cancelled.poll().kind.value == "pending"
    assert cancelled.cancel().is_ok
    assert event.cancel_wait(5).error_or(None).code is SyncErrorCode.INVALID_STATE
