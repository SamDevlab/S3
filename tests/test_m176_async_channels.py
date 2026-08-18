from __future__ import annotations

import pytest

from bootstrap.s3.async_channels import (
    AsyncChannel,
    ChannelErrorCode,
    OwnedMessage,
    select,
)
from bootstrap.s3.async_core import PollKind


pytestmark = pytest.mark.s3_fast


def test_bounded_fifo_channel_consumes_message_ownership() -> None:
    channel = AsyncChannel[str](capacity=2)
    sender, receiver = channel.split()
    first = OwnedMessage("a")
    second = OwnedMessage("b")
    assert sender.send(first).is_ok
    assert sender.send(second).is_ok
    assert first.moved and second.moved
    assert receiver.recv().value_or(None).move().value_or(None) == "a"
    assert receiver.recv().value_or(None).move().value_or(None) == "b"


def test_full_send_preserves_recoverable_ownership_and_awaitable_retries() -> None:
    channel = AsyncChannel[int](capacity=1)
    sender, receiver = channel.split()
    assert sender.send(OwnedMessage(1)).is_ok
    message = OwnedMessage(2)
    failed = sender.send(message)
    assert failed.is_err and failed.error_or(None).code is ChannelErrorCode.FULL
    assert not message.moved
    operation = sender.send_awaitable(message)
    assert operation.poll().kind is PollKind.PENDING
    assert receiver.recv().is_ok
    assert operation.poll().kind is PollKind.READY
    assert operation.recover() is None


def test_close_drains_committed_values_then_reports_closed() -> None:
    channel = AsyncChannel[int](capacity=1)
    sender, receiver = channel.split()
    assert sender.send(OwnedMessage(7)).is_ok
    sender.close()
    assert receiver.recv().value_or(None).move().value_or(None) == 7
    closed = receiver.recv().error_or(None)
    assert closed.code is ChannelErrorCode.CLOSED
    receiver.close()
    assert channel.closed


def test_receive_awaitable_is_pending_until_message_arrives() -> None:
    channel = AsyncChannel[str](capacity=1)
    sender, receiver = channel.split()
    operation = receiver.recv_awaitable()
    assert operation.poll().kind is PollKind.PENDING
    assert sender.send(OwnedMessage("ready")).is_ok
    result = operation.poll()
    assert result.kind is PollKind.READY
    assert result.value.move().value_or(None) == "ready"  # type: ignore[union-attr]


def test_select_uses_lowest_registration_index_for_ties() -> None:
    left = AsyncChannel[int](capacity=1)
    right = AsyncChannel[int](capacity=1)
    left_sender, left_receiver = left.split()
    right_sender, right_receiver = right.split()
    assert left_sender.send(OwnedMessage(1)).is_ok
    assert right_sender.send(OwnedMessage(2)).is_ok
    result = select((left_receiver, right_receiver))
    assert result.is_ok
    selected = result.value_or(None)
    assert selected is not None
    assert selected.index == 0
    assert selected.message.move().value_or(None) == 1


def test_select_is_bounded_and_reports_empty_or_all_closed() -> None:
    first = AsyncChannel[int](capacity=1)
    second = AsyncChannel[int](capacity=1)
    first_sender, first_receiver = first.split()
    second_sender, second_receiver = second.split()
    assert select((first_receiver, second_receiver)).error_or(None).code is ChannelErrorCode.EMPTY
    first_sender.close()
    second_sender.close()
    assert select((first_receiver, second_receiver)).error_or(None).code is ChannelErrorCode.CLOSED
