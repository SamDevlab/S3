from __future__ import annotations

import pytest

from bootstrap.s3.async_core import AsyncFuture, complete, pending
from bootstrap.s3.async_executor import AsyncExecutor, ExecutorLimits, FakeClock


pytestmark = pytest.mark.s3_fast


def test_executor_runs_ready_tasks_in_fair_stable_order() -> None:
    calls: list[int] = []

    def make_step(identifier: int):
        return lambda _frame: calls.append(identifier) or complete(identifier)

    executor = AsyncExecutor()
    assert executor.spawn(AsyncFuture(make_step(0))).is_ok
    assert executor.spawn(AsyncFuture(make_step(1))).is_ok
    report = executor.run_until_idle()
    assert report.completed == (0, 1)
    assert calls == [0, 1]


def test_wakeups_are_coalesced_and_completed_tasks_do_not_reawaken() -> None:
    executor = AsyncExecutor()
    task_id = executor.spawn(AsyncFuture(lambda _frame: complete(None))).value_or(-1)
    assert executor.wake(task_id).is_ok
    assert executor.wake(task_id).is_ok
    assert executor.queued_wakeups == 1
    assert executor.run_until_idle().completed == (task_id,)
    assert executor.wake(task_id).is_ok
    assert executor.queued_wakeups == 0


def test_timer_order_and_cancellation_use_fake_monotonic_clock() -> None:
    clock = FakeClock()
    executor = AsyncExecutor(clock=clock)

    calls: dict[str, int] = {"first": 0, "second": 0}

    def make_step(name: str):
        def step(_frame):
            calls[name] += 1
            return pending() if calls[name] == 1 else complete(name)

        return step

    first = executor.spawn(AsyncFuture(make_step("first"))).value_or(-1)
    second = executor.spawn(AsyncFuture(make_step("second"))).value_or(-1)
    timer_first = executor.call_at(5, first).value_or(None)
    timer_second = executor.call_at(3, second).value_or(None)
    assert timer_first is not None and timer_second is not None
    assert executor.cancel_timer(timer_first).is_ok
    assert executor.run_until_idle().completed == ()
    clock.advance(3)
    assert executor.run_until_idle().completed == (second,)
    clock.advance(2)
    assert executor.run_until_idle().completed == ()


def test_reactor_readiness_wakes_registered_task() -> None:
    executor = AsyncExecutor()
    task_id = executor.spawn(AsyncFuture(lambda _frame: complete(1))).value_or(-1)
    registration = executor.reactor.register("socket-0", task_id).value_or(None)
    assert registration is not None
    # Consume the admission wakeup; the future is not polled again until ready.
    assert executor.run_once().completed == (task_id,)
    assert executor.reactor.signal("socket-0").is_ok
    assert executor.run_until_idle().completed == ()


def test_executor_limits_and_idle_report_are_explicit() -> None:
    executor = AsyncExecutor(limits=ExecutorLimits(max_tasks=1, max_queued_wakeups=1, max_timers=1, max_registrations=1))
    assert executor.spawn(AsyncFuture(lambda _frame: pending())).is_ok
    overflow = executor.spawn(AsyncFuture(lambda _frame: complete(None)))
    assert overflow.is_err
    assert executor.run_once().idle is True


def test_executor_shutdown_cancels_suspended_frames() -> None:
    drops: list[int] = []

    def step(frame):
        frame.own("value", 7, drops.append)
        return pending()

    executor = AsyncExecutor()
    task_id = executor.spawn(AsyncFuture(step)).value_or(-1)
    assert executor.run_once().steps == 1
    assert executor.close().is_ok
    assert drops == [7]
    assert executor.wake(task_id).is_err
