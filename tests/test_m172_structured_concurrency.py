from __future__ import annotations

import pytest

from bootstrap.s3.async_core import AsyncFrame, AsyncFuture, AsyncState, PollKind, complete, pending
from bootstrap.s3.structured_concurrency import TaskErrorCode, TaskGroup


pytestmark = pytest.mark.s3_fast


def test_group_owns_children_and_join_is_explicit_once() -> None:
    group = TaskGroup(max_children=2)
    handle = group.spawn_step(lambda _frame: complete(3)).value_or(None)
    assert handle is not None
    assert handle.poll().kind is PollKind.READY
    assert handle.join().is_ok
    second = handle.join()
    assert second.is_err
    assert second.error_or(None).code is TaskErrorCode.JOINED
    assert group.close().is_ok


def test_group_polls_multiple_children_in_stable_id_order() -> None:
    group = TaskGroup(max_children=3)
    first = group.spawn_step(lambda _frame: complete("first")).value_or(None)
    second = group.spawn_step(lambda _frame: complete("second")).value_or(None)
    assert first is not None and second is not None
    results = group.poll_once()
    assert isinstance(results, tuple)
    assert [identifier for identifier, _ in results] == [0, 1]
    assert group.close().is_ok


def test_parent_scope_cancels_suspended_child_and_drops_frame_value() -> None:
    drops: list[int] = []

    def step(frame: AsyncFrame):
        frame.own("owned", 9, drops.append)
        return pending()

    group = TaskGroup()
    assert group.spawn(AsyncFuture(step)).is_ok
    assert group.poll_once()
    assert group.close().is_ok
    assert drops == [9]


def test_group_rejects_unfinished_scope_when_cancellation_is_disabled() -> None:
    group = TaskGroup()
    handle = group.spawn_step(lambda _frame: pending()).value_or(None)
    assert handle is not None
    assert group.poll_once()
    result = group.close(cancel_unfinished=False)
    assert result.is_err
    assert result.error_or(None).code is TaskErrorCode.UNFINISHED


def test_group_bounds_children_and_rejects_spawn_after_close() -> None:
    group = TaskGroup(max_children=1)
    assert group.spawn_step(lambda _frame: complete(None)).is_ok
    overflow = group.spawn_step(lambda _frame: complete(None))
    assert overflow.is_err
    assert overflow.error_or(None).code is TaskErrorCode.RESOURCE_LIMIT
    assert group.poll_once()
    assert group.close().is_ok
    closed = group.spawn_step(lambda _frame: complete(None))
    assert closed.is_err
    assert closed.error_or(None).code is TaskErrorCode.INVALID_STATE


def test_child_cancellation_is_idempotent_before_scope_close() -> None:
    group = TaskGroup()
    handle = group.spawn_step(lambda _frame: pending()).value_or(None)
    assert handle is not None
    assert group.poll_once()
    assert handle.cancel().is_ok
    second = handle.cancel()
    assert second.is_err
    assert handle.state is AsyncState.CANCELLED
    assert group.close().is_ok
