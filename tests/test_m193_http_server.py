from __future__ import annotations

import socket

from bootstrap.s3.async_http import HTTPLimits
from bootstrap.s3.async_http_server import (
    HTTPServerErrorCode,
    HTTPServerResponse,
    IncrementalHTTPRequestParser,
    LoopbackHTTPServer,
    StreamingHTTPServer,
)
from bootstrap.s3.results import Result


def test_incremental_server_frames_partial_headers_and_body() -> None:
    server = StreamingHTTPServer()
    assert server.open("loopback").is_ok
    assert server.receive("loopback", b"POST /echo HTTP/1.1\r\nContent-Length: 5\r\n").value_or(()) == ()
    result = server.receive("loopback", b"\r\nhello")
    request = result.value_or(())[0]
    assert request.method == "POST"
    assert request.target == "/echo"
    assert request.body == b"hello"
    encoded = HTTPServerResponse(200, "OK", (("X-Route", "echo"),), b"hello").encode()
    assert encoded.is_ok
    assert b"Content-Length: 5" in encoded.value_or(b"")


def test_server_rejects_smuggling_and_oversize_frames() -> None:
    server = StreamingHTTPServer(limits=HTTPLimits(max_header_bytes=128, max_header_line_bytes=128, max_body_bytes=4))
    assert server.open("bad").is_ok
    duplicate = (
        b"POST / HTTP/1.1\r\nContent-Length: 1\r\n"
        b"Content-Length: 1\r\n\r\na"
    )
    assert server.receive("bad", duplicate).error_or(None).code is HTTPServerErrorCode.FRAMING
    assert server.open("transfer").is_ok
    assert server.receive("transfer", b"POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n").error_or(None).code is HTTPServerErrorCode.UNSUPPORTED_TRANSFER
    assert server.open("body").is_ok
    oversized = b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\n"
    assert server.receive("body", oversized).error_or(None).code is HTTPServerErrorCode.BODY_LIMIT


def test_request_and_response_streams_preserve_chunk_boundaries_and_accounting() -> None:
    parser = IncrementalHTTPRequestParser()
    first = parser.feed(b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\nhe").value_or(())
    assert len(first) == 1
    request = first[0]
    assert request.body_complete is False
    assert request.body_reader is not None
    assert request.body_reader.read_chunk().value_or(None) == b"he"
    assert parser.body_bytes_received == 2
    parsed = parser.feed(b"llo").value_or(())
    assert parsed == ()
    assert tuple(request.iter_body()) == (b"llo",)
    assert request.body_complete is True
    response = HTTPServerResponse(200, "OK", (), (b"ab", b"c"), content_length=3)
    stream = response.open_stream().value_or(None)
    assert stream.next_chunk().value_or(None).startswith(b"HTTP/1.1 200 OK")
    assert stream.next_chunk().value_or(None) == b"ab"
    assert stream.next_chunk().value_or(None) == b"c"
    assert stream.next_chunk().value_or(b"bad") is None


def test_request_reader_pulls_progressively_and_enforces_buffer_window() -> None:
    chunks = iter((b"abc", b"de"))

    def pull(_amount):
        return Result.ok(next(chunks, None))

    parser = IncrementalHTTPRequestParser(limits=HTTPLimits(max_body_bytes=8, max_buffered_body_bytes=3))
    parser.set_body_puller(pull)
    request = parser.feed(b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\n").value_or(())[0]
    assert request.body_complete is False
    assert tuple(request.iter_body()) == (b"abc", b"de")
    assert request.body_complete is True

    late_puller = IncrementalHTTPRequestParser(limits=HTTPLimits(max_body_bytes=8, max_buffered_body_bytes=2))
    late_request = late_puller.feed(b"POST / HTTP/1.1\r\nContent-Length: 1\r\n\r\n").value_or(())[0]
    late_puller.set_body_puller(lambda _amount: Result.ok(b"x"))
    assert tuple(late_request.iter_body()) == (b"x",)

    premature = IncrementalHTTPRequestParser(limits=HTTPLimits(max_body_bytes=8))
    premature_request = premature.feed(b"POST / HTTP/1.1\r\nContent-Length: 2\r\n\r\na").value_or(())[0]
    assert premature.mark_eof().is_ok
    assert premature_request.body_reader.read_chunk().value_or(None) == b"a"
    assert premature_request.body_reader.read_chunk().error_or(None).code is HTTPServerErrorCode.MALFORMED

    bounded = IncrementalHTTPRequestParser(limits=HTTPLimits(max_body_bytes=8, max_buffered_body_bytes=2))
    rejected = bounded.feed(b"POST / HTTP/1.1\r\nContent-Length: 3\r\n\r\nabc")
    assert rejected.error_or(None).code is HTTPServerErrorCode.QUEUE_LIMIT
    assert bounded.body_reader is not None
    assert bounded.body_reader.read_chunk(0).error_or(None).code is HTTPServerErrorCode.INVALID_ARGUMENT


def test_response_header_policy_and_connection_budget_are_bounded() -> None:
    server = StreamingHTTPServer(max_connections=1)
    assert server.open("one").is_ok
    assert server.open("two").error_or(None).code is HTTPServerErrorCode.CONNECTION_LIMIT
    unsafe = HTTPServerResponse(200, "OK", (("Connection", "keep-alive"),), b"").encode()
    assert unsafe.error_or(None).code is HTTPServerErrorCode.FRAMING
    assert server.close("one").is_ok
    assert server.receive("one", b"").error_or(None).code is HTTPServerErrorCode.CLOSED


def test_loopback_server_executes_real_tcp_request_and_closes_deterministically() -> None:
    server = LoopbackHTTPServer(
        limits=HTTPLimits(max_timeout_seconds=2),
        max_chunk_bytes=3,
    )
    started = server.start()
    assert started.is_ok
    host, port = started.value_or(("", 0))
    client = socket.create_connection((host, port), timeout=2)
    try:
        client.sendall(b"POST /echo HTTP/1.1\r\nContent-Length: 5\r\n\r\nhello")
        def handle(request):
            body = request.body
            return HTTPServerResponse(200, "OK", (("X-Body", str(len(body))),), body)

        served = server.serve_once(handle)
        assert served.is_ok
        client.settimeout(2)
        response = bytearray()
        while True:
            chunk = client.recv(64)
            if not chunk:
                break
            response.extend(chunk)
        assert b"HTTP/1.1 200 OK" in response
        assert b"Content-Length: 5" in response
        assert response.endswith(b"hello")
    finally:
        client.close()
        assert server.close().is_ok
    assert server.active_connections == 0


def test_loopback_body_backpressure_survives_coalesced_headers_and_body() -> None:
    limits = HTTPLimits(max_body_bytes=3, max_buffered_body_bytes=2, max_timeout_seconds=2)
    server = LoopbackHTTPServer(limits=limits, max_chunk_bytes=3)
    started = server.start()
    assert started.is_ok
    host, port = started.value_or(("", 0))
    client = socket.create_connection((host, port), timeout=2)
    observed: dict[str, object] = {}
    try:
        client.sendall(b"POST /bounded HTTP/1.1\r\nContent-Length: 3\r\n\r\nabc")

        def handle(request):
            reader = request.body_reader
            assert reader is not None
            chunks: list[bytes] = []
            maximum_retained = reader.buffered_bytes
            while True:
                result = reader.read_chunk()
                assert result.is_ok
                maximum_retained = max(maximum_retained, reader.buffered_bytes)
                chunk = result.value_or(None)
                if chunk is None:
                    break
                chunks.append(chunk)
                assert reader.buffered_bytes <= limits.max_buffered_body_bytes
            observed["body"] = b"".join(chunks)
            observed["maximum_retained"] = max(maximum_retained, reader.peak_buffered_bytes)
            return HTTPServerResponse(200, "OK", (), b"ok")

        served = server.serve_once(handle)
        assert served.is_ok
        client.settimeout(2)
        response = bytearray()
        while True:
            chunk = client.recv(64)
            if not chunk:
                break
            response.extend(chunk)
        assert b"HTTP/1.1 200 OK" in response
        assert response.endswith(b"ok")
        assert observed["body"] == b"abc"
        assert 0 < observed["maximum_retained"] <= limits.max_buffered_body_bytes
    finally:
        client.close()
        assert server.close().is_ok


def test_loopback_server_enforces_one_global_request_deadline() -> None:
    server = LoopbackHTTPServer(limits=HTTPLimits(max_timeout_seconds=0.05))
    started = server.start()
    assert started.is_ok
    host, port = started.value_or(("", 0))
    client = socket.create_connection((host, port), timeout=1)
    try:
        result = server.serve_once(lambda _request: HTTPServerResponse(200, "OK", (), b""))
        assert result.error_or(None).code is HTTPServerErrorCode.TIMEOUT
    finally:
        client.close()
        assert server.close().is_ok
