from __future__ import annotations

import pytest

from bootstrap.s3.async_observability import AsyncEventKind, BoundedAsyncTelemetry


def test_async_telemetry_is_bounded_and_copies_event_data() -> None:
    telemetry = BoundedAsyncTelemetry(capacity=2)
    telemetry.record(AsyncEventKind.CREATED, task_id=4, detail={"phase": "create"})
    telemetry.record(AsyncEventKind.POLLED, task_id=4)
    telemetry.record(AsyncEventKind.COMPLETED, task_id=4)
    snapshot = telemetry.snapshot()
    assert len(snapshot.retained) == 2
    assert snapshot.dropped == 1
    assert snapshot.counts == (("task_completed", 1), ("task_created", 1), ("task_polled", 1))
    assert snapshot.retained[-1].detail == ()


def test_disabled_telemetry_has_minimal_semantic_footprint() -> None:
    telemetry = BoundedAsyncTelemetry(enabled=False)
    telemetry.record(AsyncEventKind.CREATED, task_id=1)
    assert telemetry.snapshot().retained == ()
    assert telemetry.snapshot().counts == ()


def test_telemetry_rejects_invalid_capacity() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        BoundedAsyncTelemetry(capacity=0)
