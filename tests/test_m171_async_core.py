from __future__ import annotations

import pytest

from bootstrap.s3.async_core import (
    AsyncErrorCode,
    AsyncFrame,
    AsyncFuture,
    AsyncState,
    PollKind,
    complete,
    pending,
)


pytestmark = pytest.mark.s3_fast


def test_future_has_deterministic_created_suspended_completed_trace() -> None:
    calls = 0

    def step(frame: AsyncFrame):
        nonlocal calls
        calls += 1
        return pending() if calls == 1 else complete("done")

    future = AsyncFuture(step)
    assert future.state is AsyncState.CREATED
    assert future.poll().kind is PollKind.PENDING
    assert future.poll().value == "done"
    assert future.frame.trace == ["running", "suspended", "running", "completed"]


def test_owned_value_survives_suspension_and_drops_once_on_completion() -> None:
    drops: list[str] = []
    calls = 0

    def step(frame: AsyncFrame):
        nonlocal calls
        calls += 1
        if calls == 1:
            assert frame.own("payload", "owned", drops.append).is_ok
            return pending()
        assert frame.move("payload").value_or(None) == "owned"
        return complete(7)

    future = AsyncFuture(step)
    assert future.poll().kind is PollKind.PENDING
    assert future.poll().kind is PollKind.READY
    assert drops == []
    assert future.frame.slots["payload"].dropped
    assert future.cancel().is_err


def test_live_lexical_borrow_is_rejected_across_await() -> None:
    def step(frame: AsyncFrame):
        assert frame.borrow("local").is_ok
        return pending()

    result = AsyncFuture(step).poll()
    assert result.kind is PollKind.FAILED
    assert result.error is not None
    assert result.error.code is AsyncErrorCode.BORROW_ACROSS_AWAIT


def test_cancelled_suspended_future_drops_initialized_slots() -> None:
    drops: list[int] = []

    def step(frame: AsyncFrame):
        assert frame.own("value", 42, drops.append).is_ok
        return pending()

    future = AsyncFuture(step)
    assert future.poll().kind is PollKind.PENDING
    assert future.cancel().is_ok
    assert future.state is AsyncState.CANCELLED
    assert drops == [42]
    assert future.poll().error is not None


def test_nested_future_is_explicitly_polled_without_hidden_generator() -> None:
    inner = AsyncFuture(lambda _frame: complete(5))
    outer_calls = 0

    def outer_step(_frame: AsyncFrame):
        nonlocal outer_calls
        outer_calls += 1
        result = inner.poll()
        if result.kind is PollKind.READY:
            return complete(result.value * 2)  # type: ignore[operator]
        return pending()

    outer = AsyncFuture(outer_step)
    assert outer.poll().value == 10
    assert outer_calls == 1


def test_terminal_future_cannot_be_polled_twice() -> None:
    future = AsyncFuture(lambda _frame: complete("value"))
    assert future.poll().kind is PollKind.READY
    second = future.poll()
    assert second.kind is PollKind.FAILED
    assert second.error is not None
    assert second.error.code is AsyncErrorCode.INVALID_STATE


def test_frame_limit_is_explicit() -> None:
    frame = AsyncFrame(max_slots=1)
    assert frame.own("one", 1).is_ok
    result = frame.own("two", 2)
    assert result.is_err
    assert result.error_or(None).code is AsyncErrorCode.FRAME_LIMIT
