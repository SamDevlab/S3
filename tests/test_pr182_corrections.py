from __future__ import annotations

import hashlib
import io
import json
import tarfile

import pytest

from bootstrap.s3.async_core import (
    AsyncErrorCode,
    AsyncFuture,
    AsyncState,
    PollKind,
    complete,
    fail,
    pending,
)
from bootstrap.s3.async_network import (
    AsyncNetworkErrorCode,
    AsyncNetworkService,
    PendingResource,
)
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.network import NetworkAddress
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.registry_client import RegistryClient, RegistryError, RegistryLock
from bootstrap.s3.structured_concurrency import TaskGroup


pytestmark = pytest.mark.s3_fast


def test_m171_async_fn_await_compile_and_lower_deterministically() -> None:
    source = (
        "async fn child() -> i64:\n"
        "    return 7\n"
        "async fn main() -> i64:\n"
        "    return await child()\n"
    )
    first = compile_source(source)
    second = compile_source(source)
    assert first.async_syntax.async_function_names == frozenset({"child", "main"})
    assert first.async_state_machines == second.async_state_machines
    plans = {plan.function_name: plan for plan in first.async_state_machines}
    assert plans["child"].suspension_points == ()
    assert [point.callee for point in plans["main"].suspension_points] == ["child"]
    assert execute_ir(first.ir) == 7


def test_m171_async_calls_require_await_and_await_requires_async_scope() -> None:
    with pytest.raises(SemanticError, match="must be awaited"):
        compile_source(
            "async fn child() -> i64:\n"
            "    return 1\n"
            "fn main() -> i64:\n"
            "    return child()\n"
        )
    with pytest.raises(SemanticError, match="only valid inside async fn"):
        compile_source(
            "async fn child() -> i64:\n"
            "    return 1\n"
            "fn main() -> i64:\n"
            "    return await child()\n"
        )


def test_m171_source_rejects_ordinary_reference_live_across_await() -> None:
    with pytest.raises(SemanticError, match="live across await"):
        compile_source(
            "async fn child() -> i64:\n"
            "    return 1\n"
            "async fn main() -> i64:\n"
            "    value: i64 = 3\n"
            "    reference: &i64 = &value\n"
            "    return await child()\n"
        )


def test_m171_reentrant_poll_fails_closed() -> None:
    future: AsyncFuture[int]
    nested = []

    def step(_frame):
        nested.append(future.poll())
        return complete(1)

    future = AsyncFuture(step)
    outer = future.poll()
    assert outer.kind is PollKind.READY
    assert nested[0].kind is PollKind.FAILED
    assert nested[0].error is not None
    assert nested[0].error.code is AsyncErrorCode.INVALID_STATE
    assert "re-entrant" in nested[0].error.detail


def test_m172_join_preserves_success_failure_and_cancellation_results() -> None:
    group = TaskGroup()
    success = group.spawn_step(lambda _frame: complete(9)).value_or(None)
    assert success.poll().value == 9
    joined = success.join().value_or(None)
    assert joined.kind is PollKind.READY and joined.value == 9

    failed = group.spawn_step(
        lambda _frame: fail(AsyncErrorCode.OWNERSHIP, "child", "original")
    ).value_or(None)
    terminal = failed.poll()
    joined_failure = failed.join().value_or(None)
    assert terminal.error is joined_failure.error
    assert joined_failure.error.detail == "original"

    cancelled = group.spawn_step(lambda _frame: pending()).value_or(None)
    assert cancelled.poll().kind is PollKind.PENDING
    assert cancelled.cancel().is_ok
    joined_cancel = cancelled.join().value_or(None)
    assert joined_cancel.state is AsyncState.CANCELLED
    assert joined_cancel.error.code is AsyncErrorCode.CANCELLED
    assert group.close().is_ok


def test_m174_pending_resource_transfers_exact_identity_and_replacement_fails_closed() -> None:
    class Provider:
        def __init__(self, replace: bool = False):
            self.original = object()
            self.replacement = object()
            self.replace = replace
            self.calls = 0
            self.closed: list[object] = []

        def connect(self, _address):
            self.calls += 1
            if self.calls == 1:
                return PendingResource(self.original)
            return self.replacement if self.replace else self.original

        def accept(self, _listener): return object()
        def read(self, _stream, _amount): return b""
        def write(self, _stream, data): return len(data)
        def udp_send(self, _socket, data, _address): return len(data)
        def udp_receive(self, _socket): return b""
        def resolve(self, _host, _port): return ()
        def close(self, resource): self.closed.append(resource)

    provider = Provider()
    service = AsyncNetworkService(provider)
    future = service.connect(NetworkAddress.numeric("127.0.0.1", 1))
    assert future.poll().kind is PollKind.PENDING
    ready = future.poll()
    assert ready.kind is PollKind.READY
    assert ready.value.resource is provider.original
    ready.value.close()
    assert provider.closed == [provider.original]

    replacing = Provider(replace=True)
    service = AsyncNetworkService(replacing)
    future = service.connect(NetworkAddress.numeric("127.0.0.1", 1))
    assert future.poll().kind is PollKind.PENDING
    rejected = future.poll()
    assert rejected.kind is PollKind.FAILED
    assert rejected.error.code is AsyncNetworkErrorCode.PROVIDER_FAILURE
    assert set(replacing.closed) == {replacing.original, replacing.replacement}
    assert service.active_handles == 0


def _archive(members: tuple[tuple[str, bytes], ...], *, gzip: bool = False) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz" if gzip else "w") as archive:
        for name, content in members:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def _registry(tmp_path, payload: bytes, **kwargs):
    digest = hashlib.sha256(payload).hexdigest()
    root = tmp_path / "registry"
    (root / "objects").mkdir(parents=True)
    (root / "objects" / "package.tar").write_bytes(payload)
    (root / "index.json").write_text(json.dumps({
        "format": "s3.registry.index.v1",
        "packages": [{
            "name": "demo",
            "version": "1",
            "sha256": digest,
            "object": "objects/package.tar",
        }],
    }), encoding="utf-8")
    client = RegistryClient(root, **kwargs)
    return client, RegistryLock("demo", "1", digest)


def test_m179_uncompressed_member_cumulative_and_duplicate_path_limits_fail_closed(tmp_path) -> None:
    payload = _archive((("large.s3", b"x" * 4096),), gzip=True)
    client, lock = _registry(tmp_path / "member", payload, max_member_bytes=1024)
    destination = tmp_path / "member-output"
    with pytest.raises(RegistryError, match="member exceeds"):
        client.install(client.fetch(lock), destination)
    assert not destination.exists()

    payload = _archive((("a.s3", b"a" * 700), ("b.s3", b"b" * 700)), gzip=True)
    client, lock = _registry(
        tmp_path / "total",
        payload,
        max_member_bytes=1024,
        max_extracted_bytes=1024,
    )
    destination = tmp_path / "total-output"
    with pytest.raises(RegistryError, match="extracted byte limit"):
        client.install(client.fetch(lock), destination)
    assert not destination.exists()

    payload = _archive((("src/main.s3", b"one"), ("src/main.s3", b"two")))
    client, lock = _registry(tmp_path / "duplicate", payload)
    destination = tmp_path / "duplicate-output"
    with pytest.raises(RegistryError, match="duplicate canonical"):
        client.install(client.fetch(lock), destination)
    assert not destination.exists()
