from __future__ import annotations

import socket

from bootstrap.s3.async_channels import AsyncChannel, ChannelErrorCode, OwnedMessage
from bootstrap.s3.async_core import AsyncFuture, PollKind, complete, pending
from bootstrap.s3.async_executor import AsyncExecutor, ExecutorLimits, FakeClock
from bootstrap.s3.async_http_server import HTTPServerResponse, LoopbackHTTPServer
from bootstrap.s3.async_network import AsyncNetworkService
from bootstrap.s3.async_tls import AsyncTlsConfig, AsyncTlsService, Ready, WantRead
from bootstrap.s3.http2 import FrameType, Http2Connection, Http2Frame, PREFACE, serialize_frame
from bootstrap.s3.network import NetworkAddress


class _NetworkProvider:
    def __init__(self) -> None:
        self.closed: list[object] = []

    def connect(self, _address):
        return object()

    def accept(self, _listener):
        return object()

    def read(self, _stream, _amount):
        return b""

    def write(self, _stream, data):
        return len(data)

    def udp_send(self, _socket, data, _address):
        return len(data)

    def udp_receive(self, _socket):
        return b""

    def resolve(self, _host, _port):
        return ()

    def close(self, resource):
        self.closed.append(resource)


class _TlsProvider:
    def __init__(self) -> None:
        self.handshakes = 0
        self.closed: list[object] = []

    def handshake(self, connection, _hostname):
        self.handshakes += 1
        return WantRead() if self.handshakes == 1 else Ready(connection)

    def read(self, _connection, _amount):
        return Ready(b"ok")

    def write(self, _connection, data):
        return Ready(len(data))

    def close(self, connection):
        self.closed.append(connection)


def test_bounded_async_soak_reclaims_tasks_timers_channels_and_network_handles() -> None:
    clock = FakeClock()
    executor = AsyncExecutor(
        clock=clock,
        limits=ExecutorLimits(max_tasks=2, max_queued_wakeups=2, max_timers=2, max_registrations=2),
    )
    provider = _NetworkProvider()
    network = AsyncNetworkService(provider, max_handles=2)

    for round_id in range(48):
        channel = AsyncChannel[int](capacity=1)
        sender, receiver = channel.split()
        assert sender.send(OwnedMessage(round_id)).is_ok
        blocked = sender.send_awaitable(OwnedMessage(round_id + 1))
        assert blocked.poll().kind is PollKind.PENDING
        assert receiver.recv().value_or(None).move().value_or(None) == round_id
        assert blocked.poll().kind is PollKind.READY
        sender.close()
        receiver.close()
        assert channel.closed

        task_id = executor.spawn(AsyncFuture(lambda _frame: complete(round_id))).value_or(-1)
        registration = executor.reactor.register(f"soak-{round_id}", task_id).value_or(None)
        assert registration is not None
        assert executor.call_at(clock.now, task_id).is_ok
        assert executor.run_until_idle().completed == (task_id,)
        assert executor.reap_completed() == (task_id,)
        assert executor.snapshot().reactor_registrations == 0
        assert executor.snapshot().timers == 0

        handle_result = network.connect(NetworkAddress.numeric("127.0.0.1", 1)).poll()
        assert handle_result.kind is PollKind.READY
        assert handle_result.value.close().is_ok
        assert network.active_handles == 0

    assert executor.close().is_ok
    assert executor.snapshot().closed
    assert executor.snapshot().reactor_registrations == 0
    assert network.active_handles == 0
    assert len(provider.closed) == 48


def test_bounded_cancellation_releases_owned_frame_and_pending_tls_resource() -> None:
    dropped: list[object] = []
    executor = AsyncExecutor()
    future = AsyncFuture(lambda frame: frame.own("resource", object(), dropped.append) and pending())
    task_id = executor.spawn(future).value_or(-1)
    assert executor.run_once().steps == 1
    assert executor.close().is_ok
    assert len(dropped) == 1
    assert task_id == 0

    provider = _TlsProvider()
    tls_future = AsyncTlsService(provider).handshake(object(), AsyncTlsConfig("fixture.test"))
    assert tls_future.poll().kind is PollKind.PENDING
    assert tls_future.cancel().is_ok
    assert len(provider.closed) == 1


def test_real_loopback_http1_soak_preserves_body_bounds_and_closes_connections() -> None:
    for payload in (b"a", b"bc", b"def", b"ghij"):
        server = LoopbackHTTPServer(max_chunk_bytes=2)
        started = server.start()
        assert started.is_ok
        host, port = started.value_or(("", 0))
        client = socket.create_connection((host, port), timeout=2)
        try:
            client.sendall(
                b"POST /soak HTTP/1.1\r\nContent-Length: "
                + str(len(payload)).encode("ascii")
                + b"\r\n\r\n"
                + payload
            )

            def handle(request):
                assert request.body == payload
                return HTTPServerResponse(200, "OK", (), b"ok")

            assert server.serve_once(handle).is_ok
            client.settimeout(2)
            response = bytearray()
            while True:
                chunk = client.recv(64)
                if not chunk:
                    break
                response.extend(chunk)
            assert b"HTTP/1.1 200 OK" in response
            assert response.endswith(b"ok")
        finally:
            client.close()
            assert server.close().is_ok
        assert server.active_connections == 0


def test_http2_stream_state_and_bounded_tls_progress_repeat() -> None:
    for stream_id in range(1, 17):
        connection = Http2Connection()
        connection.accept_preface(PREFACE)
        headers = serialize_frame(Http2Frame(FrameType.HEADERS, 0, stream_id, b"\x82\x84"))
        data = serialize_frame(Http2Frame(FrameType.DATA, 1, stream_id, b"body"))
        assert connection.receive(headers).stream_id == stream_id
        assert connection.receive(data).stream_id == stream_id
        assert connection.streams[stream_id] == "half-closed"

    for _ in range(16):
        provider = _TlsProvider()
        future = AsyncTlsService(provider).handshake(object(), AsyncTlsConfig("fixture.test"))
        assert future.poll().kind is PollKind.PENDING
        client_result = future.poll()
        assert client_result.kind is PollKind.READY
        client = client_result.value
        assert client.read(2).poll().value == b"ok"
        assert client.write(b"ok").poll().value == 2
        assert client.close().is_ok
        assert len(provider.closed) == 1


def test_backpressure_reports_full_without_losing_message_ownership() -> None:
    channel = AsyncChannel[int](capacity=1)
    sender, receiver = channel.split()
    assert sender.send(OwnedMessage(1)).is_ok
    message = OwnedMessage(2)
    result = sender.send(message)
    assert result.is_err
    assert result.error_or(None).code is ChannelErrorCode.FULL
    assert message.moved is False
    receiver.close()
    sender.close()
