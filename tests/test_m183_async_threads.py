from __future__ import annotations

import time

from bootstrap.s3.async_core import AsyncFuture, complete
from bootstrap.s3.async_futures import FutureErrorCode, MoveOnlyFuture
from bootstrap.s3.async_threads import (
    BoundedThreadExecutor,
    ThreadExecutorErrorCode,
    ThreadExecutorLimits,
    TransferValue,
)


def _wait_for_polls(executor: BoundedThreadExecutor, count: int) -> tuple:
    for _ in range(100):
        polls = executor.take_polls()
        if len(polls) >= count:
            return polls
        time.sleep(0.005)
    raise AssertionError("worker did not publish a poll")


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
    executor = BoundedThreadExecutor(limits=ThreadExecutorLimits(max_workers=1, max_tasks=1, max_ready=1))
    first = MoveOnlyFuture(AsyncFuture(lambda _frame: complete(1)))
    second = MoveOnlyFuture(AsyncFuture(lambda _frame: complete(2)))
    assert executor.spawn(first).is_ok
    rejected = executor.spawn(second)
    assert rejected.error_or(None).code is ThreadExecutorErrorCode.RESOURCE_LIMIT
    _wait_for_polls(executor, 1)
    assert executor.close().is_ok
