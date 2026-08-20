from __future__ import annotations

import socket

from bootstrap.s3.async_http import HTTPLimits
from bootstrap.s3.async_http_server import (
    HTTPServerErrorCode,
    HTTPServerResponse,
    LoopbackHTTPServer,
    StreamingHTTPServer,
)


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
        served = server.serve_once(
            lambda request: HTTPServerResponse(200, "OK", (("X-Body", str(len(request.body))),), request.body)
        )
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
