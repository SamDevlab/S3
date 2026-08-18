from __future__ import annotations

import threading
import time

import pytest

from bootstrap.s3.results import Result
from bootstrap.s3.threads import (
    OwnedValue,
    ThreadErrorCode,
    ThreadRuntime,
)


class _AdmissionWindowLock:
    """Force two vulnerable capacity checks to complete before registration."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._local = threading.local()
        self._checks = 0
        self._checks_lock = threading.Lock()
        self._checks_done = threading.Event()

    def __enter__(self) -> "_AdmissionWindowLock":
        phase = getattr(self._local, "phase", None)
        if phase == "checked" and not self._checks_done.is_set():
            assert self._checks_done.wait(2.0)
        self._lock.acquire()
        if phase is None:
            self._local.phase = "checking"
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        phase = getattr(self._local, "phase", None)
        self._lock.release()
        if phase == "checking":
            with self._checks_lock:
                self._checks += 1
                if self._checks >= 2:
                    self._checks_done.set()
            self._local.phase = "checked"
        return False


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


def test_direct_mutable_sharing_is_rejected_without_an_explicit_sync_root() -> None:
    runtime = ThreadRuntime()
    result = runtime.spawn(lambda value: len(value), [1, 2, 3])
    failure = result.error_or(None)
    assert failure.code is ThreadErrorCode.UNSAFE_SHARED_STATE


def test_concurrent_spawn_limit_is_atomic_with_controlled_admission_window() -> None:
    release = threading.Event()
    worker_started = threading.Event()
    runtime = ThreadRuntime(max_active=1)
    runtime._lock = _AdmissionWindowLock()
    callers_ready = threading.Barrier(3)
    results: list[Result[object, object]] = []
    results_lock = threading.Lock()

    def worker(_: object) -> None:
        worker_started.set()
        assert release.wait(2.0)

    def caller() -> None:
        callers_ready.wait()
        result = runtime.spawn(worker, None)
        with results_lock:
            results.append(result)

    callers = [threading.Thread(target=caller), threading.Thread(target=caller)]
    for caller_thread in callers:
        caller_thread.start()
    callers_ready.wait()
    for caller_thread in callers:
        caller_thread.join(3.0)

    assert len(results) == 2
    assert sum(result.is_ok for result in results) == 1
    assert sum(
        1
        for result in results
        if result.is_err and result.error_or(None).code is ThreadErrorCode.RESOURCE_LIMIT
    ) == 1
    assert worker_started.wait(2.0)
    assert runtime.active_count <= 1
    release.set()
    runtime.join_all()


def test_resource_limit_preserves_owned_value_until_capacity_is_available() -> None:
    release = threading.Event()
    started = threading.Event()
    runtime = ThreadRuntime(max_active=1)
    first = runtime.spawn(lambda _: (started.set(), release.wait(2.0)), None).value_or(None)
    assert first is not None
    assert started.wait(2.0)

    owned = OwnedValue("payload")
    limited = runtime.spawn(lambda value: value, owned).error_or(None)
    assert limited.code is ThreadErrorCode.RESOURCE_LIMIT
    assert owned.moved is False

    release.set()
    assert first.join().is_ok
    second = runtime.spawn(lambda value: value, owned).value_or(None)
    assert second is not None
    assert second.join().value_or(None) == "payload"


def test_failed_owned_move_does_not_leak_capacity() -> None:
    runtime = ThreadRuntime(max_active=1)
    owned = OwnedValue("payload")
    assert owned.move().is_ok
    failure = runtime.spawn(lambda value: value, owned).error_or(None)
    assert failure.code is ThreadErrorCode.OWNERSHIP
    handle = runtime.spawn(lambda value: value, "ok").value_or(None)
    assert handle is not None
    assert handle.join().value_or(None) == "ok"


def test_thread_start_failure_rolls_back_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = ThreadRuntime(max_active=1)

    def fail_start(_: threading.Thread) -> None:
        raise RuntimeError("controlled start failure")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    with pytest.raises(RuntimeError, match="controlled start failure"):
        runtime.spawn(lambda _: None, None)

    monkeypatch.undo()
    handle = runtime.spawn(lambda _: "ok", None).value_or(None)
    assert handle is not None
    assert handle.join().value_or(None) == "ok"


def test_completed_unjoined_worker_releases_capacity() -> None:
    completed = threading.Event()
    runtime = ThreadRuntime(max_active=1)
    first = runtime.spawn(lambda _: (completed.set(), None), None).value_or(None)
    assert first is not None
    assert completed.wait(2.0)
    deadline = time.monotonic() + 2.0
    while first._thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.001)
    assert first._thread.is_alive() is False
    assert runtime.active_count == 0

    second = runtime.spawn(lambda _: "reused", None).value_or(None)
    assert second is not None
    assert second.join().value_or(None) == "reused"
    assert first.join().is_ok
