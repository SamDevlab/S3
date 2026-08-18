from __future__ import annotations

import threading
import time

from bootstrap.s3.results import Result
from bootstrap.s3.threads import (
    OwnedValue,
    ThreadErrorCode,
    ThreadRuntime,
)


def test_owned_value_moves_into_non_daemon_thread_and_returns_result() -> None:
    runtime = ThreadRuntime()
    owned = OwnedValue([1, 2, 3])
    spawned = runtime.spawn(lambda values: len(values), owned)
    assert spawned.is_ok
    assert owned.moved
    assert owned.value.error_or(None).code is ThreadErrorCode.OWNERSHIP
    handle = spawned.value_or(None)
    assert handle is not None and handle.daemon is False
    assert handle.join().value_or(-1) == 3


def test_scalar_and_generic_values_transfer_without_shared_mutation() -> None:
    runtime = ThreadRuntime()
    first = runtime.spawn(lambda value: value * 2, 7).value_or(None)
    second = runtime.spawn(lambda value: value[0] + value[1], (3, 4)).value_or(None)
    assert first is not None and second is not None
    assert first.join().value_or(-1) == 14
    assert second.join().value_or(-1) == 7


def test_worker_error_is_explicit_and_join_is_exactly_once() -> None:
    runtime = ThreadRuntime()
    handle = runtime.spawn(lambda _: 1 / 0, None).value_or(None)
    assert handle is not None
    failure = handle.join().error_or(None)
    assert failure.code is ThreadErrorCode.WORKER_FAILURE
    assert handle.join().error_or(None).code is ThreadErrorCode.JOINED


def test_multiple_threads_and_join_all_are_bounded() -> None:
    runtime = ThreadRuntime(max_active=3)
    handles = [runtime.spawn(lambda value: value + 1, value).value_or(None) for value in range(3)]
    assert all(handle is not None for handle in handles)
    results = runtime.join_all()
    assert [result.value_or(-1) for result in results] == [1, 2, 3]
    assert runtime.active_count == 0


def test_resource_limit_and_explicit_close_do_not_detach_running_thread() -> None:
    release = threading.Event()
    runtime = ThreadRuntime(max_active=1)
    first = runtime.spawn(lambda _: release.wait(1.0), None).value_or(None)
    assert first is not None
    limited = runtime.spawn(lambda _: None, None).error_or(None)
    assert limited.code is ThreadErrorCode.RESOURCE_LIMIT
    assert first.close().error_or(None).code is ThreadErrorCode.RUNNING
    release.set()
    time.sleep(0.01)
    assert first.join().is_ok
