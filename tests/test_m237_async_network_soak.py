from __future__ import annotations

from bootstrap.s3.async_core import AsyncFuture, complete
from bootstrap.s3.async_executor import AsyncExecutor, ExecutorLimits, FakeClock


def test_bounded_executor_reaps_terminal_tasks_and_timers_across_repeated_workloads() -> None:
    clock = FakeClock()
    executor = AsyncExecutor(
        clock=clock,
        limits=ExecutorLimits(max_tasks=2, max_timers=2),
    )

    for value in range(32):
        task_id = executor.spawn(AsyncFuture(lambda _frame, value=value: complete(value))).value_or(-1)
        assert executor.call_at(clock.now, task_id).is_ok
        report = executor.run_until_idle()
        assert report.completed == (task_id,)
        assert executor.reap_completed() == (task_id,)
        snapshot = executor.snapshot()
        assert snapshot.live_tasks == 0
        assert snapshot.timers == 0
        assert snapshot.queued_wakeups == 0
        assert snapshot.ready_items == 0

    assert executor.snapshot().task_states == ()
    assert executor.close().is_ok
    assert executor.snapshot().closed is True
