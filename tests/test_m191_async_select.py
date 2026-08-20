from __future__ import annotations

import json

import pytest

from bootstrap.s3.async_channels import AsyncChannel, ChannelErrorCode, select
from bootstrap.s3.async_ir import (
    AsyncActionKind,
    AsyncIRPollKind,
    cancel_async_ir,
    execute_async_ir,
)
from bootstrap.s3.diagnostics import ParseError, SemanticError
from bootstrap.s3.pipeline import compile_source, run_source


def test_select_is_first_class_in_async_ir_and_preserves_source_order() -> None:
    source = (
        "async fn first() -> i64:\n"
        "    return 11\n"
        "async fn second() -> i64:\n"
        "    return 22\n"
        "async fn main() -> i64:\n"
        "    select:\n"
        "        case await first():\n"
        "            return 11\n"
        "        case await second():\n"
        "            return 22\n"
    )
    compilation = compile_source(source)
    assert compilation.async_ir is not None
    assert compilation.ir is None
    assert compilation.assembly is None
    model = compilation.async_ir.executable("main")
    function = compilation.async_ir.ir_function("main")
    assert model is not None and function is not None
    assert [item.kind for item in model.actions] == [AsyncActionKind.SELECT]
    assert len(model.actions[0].select_arms) == 2
    assert [item.callee for item in model.actions[0].select_arms] == ["first", "second"]
    assert function.frame.states == (
        "created",
        "running_0",
        "suspended_0",
        "running_1",
        "completed",
        "failed",
        "cancelled",
    )
    plan = next(item for item in compilation.async_state_machines if item.function_name == "main")
    assert plan.suspension_points[0].callee == "select"
    frame, pending = execute_async_ir(function, program=compilation.async_ir)
    assert pending.kind is AsyncIRPollKind.PENDING
    _, ready = execute_async_ir(function, frame=frame, program=compilation.async_ir)
    assert ready.kind is AsyncIRPollKind.READY
    assert ready.value == 11
    assert run_source(source) == 11
    json.dumps(compilation.async_ir.to_dict(), sort_keys=True)


def test_select_can_resume_through_a_nested_bounded_await() -> None:
    source = (
        "async fn first() -> i64:\n"
        "    return 1\n"
        "async fn payload() -> i64:\n"
        "    return 31\n"
        "async fn main() -> i64:\n"
        "    select:\n"
        "        case await first():\n"
        "            value: i64 = await payload()\n"
        "            return value\n"
    )
    compilation = compile_source(source)
    assert compilation.async_ir is not None
    function = compilation.async_ir.ir_function("main")
    assert function is not None
    assert "suspended_1" in function.frame.states
    plan = next(item for item in compilation.async_state_machines if item.function_name == "main")
    assert tuple(point.callee for point in plan.suspension_points) == ("select", "payload")
    frame, first = execute_async_ir(function, program=compilation.async_ir)
    assert first.kind is AsyncIRPollKind.PENDING
    frame, second = execute_async_ir(function, frame=frame, program=compilation.async_ir)
    assert second.kind is AsyncIRPollKind.PENDING
    _, third = execute_async_ir(function, frame=frame, program=compilation.async_ir)
    assert third.kind is AsyncIRPollKind.READY
    assert third.value == 31


def test_select_future_arms_consume_all_candidates_and_cancel_drops_once() -> None:
    source = (
        "async fn first() -> i64:\n"
        "    return 7\n"
        "async fn second() -> i64:\n"
        "    return 9\n"
        "async fn main() -> i64:\n"
        "    first_future: Future<i64> = first()\n"
        "    second_future: Future<i64> = second()\n"
        "    select:\n"
        "        case await second_future:\n"
        "            return 9\n"
        "        case await first_future:\n"
        "            return 7\n"
    )
    compilation = compile_source(source)
    assert compilation.async_ir is not None
    function = compilation.async_ir.ir_function("main")
    assert function is not None
    frame, pending = execute_async_ir(function, program=compilation.async_ir)
    assert pending.kind is AsyncIRPollKind.PENDING
    owned = tuple(frame.futures.values())
    assert len(owned) == 2
    cancelled = cancel_async_ir(function, frame)
    assert cancelled.kind is AsyncIRPollKind.CANCELLED
    assert all(item.dropped for item in owned)
    assert run_source(source) == 9


def test_select_rejects_double_consumption_and_unbounded_arity() -> None:
    double_consume = (
        "async fn first() -> i64:\n"
        "    return 7\n"
        "async fn main() -> i64:\n"
        "    selected: Future<i64> = first()\n"
        "    select:\n"
        "        case await selected:\n"
        "            discard 0\n"
        "    return await selected\n"
    )
    with pytest.raises(SemanticError, match="already moved or consumed"):
        compile_source(double_consume)

    arms = "\n".join(
        f"        case await first():\n            return {index}\n"
        for index in range(9)
    )
    with pytest.raises(ParseError, match="at most 8 arms"):
        compile_source(
            "async fn first() -> i64:\n"
            "    return 1\n"
            "async fn main() -> i64:\n"
            "    select:\n"
            f"{arms}"
        )


def test_channel_select_is_bounded_deterministic_and_fail_closed() -> None:
    first_channel = AsyncChannel[int](1)
    second_channel = AsyncChannel[int](1)
    first_sender, first_receiver = first_channel.split()
    _, second_receiver = second_channel.split()
    from bootstrap.s3.async_channels import OwnedMessage

    assert first_sender.send(OwnedMessage(5)).is_ok
    selected = select((first_receiver, second_receiver))
    assert selected.is_ok
    assert selected.value_or(None).index == 0
    assert select((second_receiver,)).error_or(None).code is ChannelErrorCode.EMPTY
    assert select(tuple(first_receiver for _ in range(9))).error_or(None).code is ChannelErrorCode.INVALID
