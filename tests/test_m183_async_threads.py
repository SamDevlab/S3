from __future__ import annotations

import threading
import time

from bootstrap.s3.async_core import AsyncFuture, complete, pending
from bootstrap.s3.async_futures import FutureErrorCode, MoveOnlyFuture
from bootstrap.s3.async_threads import (
    BoundedThreadExecutor,
    ThreadExecutorErrorCode,
    ThreadExecutorLimits,
    TransferValue,
)


def _wait_for_polls(executor: BoundedThreadExecutor, count: int) -> tuple:
    deadline = time.monotonic() + 2.0
    collected = []
    while time.monotonic() < deadline:
        collected.extend(executor.take_polls())
        if len(collected) >= count:
            return tuple(collected)
        time.sleep(0.005)
    raise AssertionError("worker did not publish the required polls")


def test_transfer_domain_rejects_mutable_or_arbitrary_values() -> None:
    assert TransferValue.create((1, "ok", b"bytes")).is_ok
    rejected = TransferValue.create([1, 2, 3])
    assert rejected.error_or(None).code is ThreadExecutorErrorCode.UNSAFE_TRANSFER


def test_bounded_executor_consumes_future_owner_and_runs_on_worker() -> None:
    executor = BoundedThreadExecutor(limits=ThreadExecutorLimits(max_workers=2, max_tasks=2, max_ready=2))
    owner = MoveOnlyFuture(AsyncFuture(lambda _frame: complete(41)))
    task = executor.spawn(owner, transfer=TransferValue.create("payload").value_or(None))
    assert task.is_ok
    assert owner.moved
    polls = _wait_for_polls(executor, 1)
    assert polls[0].poll.value == 41
    assert polls[0].worker_index in {0, 1}
    assert executor.close().is_ok
    assert executor.alive_workers == 0


def test_wakeup_is_deduplicated_and_moved_owner_cannot_be_reused() -> None:
    executor = BoundedThreadExecutor(limits=ThreadExecutorLimits(max_workers=1, max_tasks=1, max_ready=1))
    owner = MoveOnlyFuture(AsyncFuture(lambda _frame: complete(9)))
    task = executor.spawn(owner)
    assert task.is_ok
    assert executor.wake(task.value_or(None)).is_ok
    assert owner.poll().error_or(None).code is FutureErrorCode.OWNERSHIP
    _wait_for_polls(executor, 1)
    assert executor.close().is_ok


def test_task_admission_is_bounded() -> None:
    gate = threading.Event()
    executor = BoundedThreadExecutor(limits=ThreadExecutorLimits(max_workers=1, max_tasks=1, max_ready=1))
    first = MoveOnlyFuture(AsyncFuture(lambda _frame: pending() if not gate.is_set() else complete(1)))
    second = MoveOnlyFuture(AsyncFuture(lambda _frame: complete(2)))
    assert executor.spawn(first).is_ok
    rejected = executor.spawn(second)
    assert rejected.error_or(None).code is ThreadExecutorErrorCode.RESOURCE_LIMIT
    gate.set()
    assert executor.close().is_ok


def test_concurrent_admission_cannot_overbook_capacity() -> None:
    start = threading.Barrier(3)
    release = threading.Event()
    executor = BoundedThreadExecutor(limits=ThreadExecutorLimits(max_workers=1, max_tasks=1, max_ready=1))
    outcomes = []
    lock = threading.Lock()

    def submit(value: int) -> None:
        owner = MoveOnlyFuture(AsyncFuture(lambda _frame: pending() if not release.is_set() else complete(value)))
        start.wait()
        result = executor.spawn(owner)
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=submit, args=(value,)) for value in (1, 2)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert sum(result.is_ok for result in outcomes) == 1
    rejected = [result for result in outcomes if result.is_err]
    assert len(rejected) == 1
    assert rejected[0].error_or(None).code in {ThreadExecutorErrorCode.RESOURCE_LIMIT, ThreadExecutorErrorCode.QUEUE_FULL}
    assert executor.task_count <= 1
    release.set()
    assert executor.close().is_ok


def test_wake_during_active_poll_never_creates_two_active_polls() -> None:
    entered = threading.Event()
    release = threading.Event()
    active = 0
    max_active = 0
    polls = 0
    guard = threading.Lock()

    def step(_frame):
        nonlocal active, max_active, polls
        with guard:
            active += 1
            max_active = max(max_active, active)
            polls += 1
        entered.set()
        release.wait(timeout=2)
        with guard:
            active -= 1
        return pending() if polls == 1 else complete(7)

    executor = BoundedThreadExecutor(limits=ThreadExecutorLimits(max_workers=2, max_tasks=1, max_ready=2))
    task_id = executor.spawn(MoveOnlyFuture(AsyncFuture(step))).value_or(None)
    assert entered.wait(timeout=2)
    assert executor.wake(task_id).is_ok
    release.set()
    results = _wait_for_polls(executor, 2)
    assert len(results) >= 2
    assert max_active == 1
    assert executor.close().is_ok


def test_cancel_during_active_poll_is_deferred_until_poll_finishes() -> None:
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def step(_frame):
        entered.set()
        release.wait(timeout=2)
        finished.set()
        return pending()

    executor = BoundedThreadExecutor(limits=ThreadExecutorLimits(max_workers=1, max_tasks=1, max_ready=1))
    task_id = executor.spawn(MoveOnlyFuture(AsyncFuture(step))).value_or(None)
    assert entered.wait(timeout=2)
    assert executor.cancel(task_id).is_ok
    assert not finished.is_set()
    release.set()
    _wait_for_polls(executor, 1)
    deadline = time.monotonic() + 2
    while executor.task_count and time.monotonic() < deadline:
        time.sleep(0.005)
    assert executor.task_count == 0
    assert executor.close().is_ok
