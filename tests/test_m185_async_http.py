from __future__ import annotations

import socket
import ssl
import threading

import pytest

from bootstrap.s3.async_http import (
    BoundedHTTPClient,
    HTTPLimits,
    HTTPErrorCode,
    LocalHTTPClient,
    LocalHTTPFixtures,
    SocketHTTPTransport,
    parse_http_response,
)


def test_local_http_fixture_get_is_bounded_and_deterministic() -> None:
    fixtures = LocalHTTPFixtures()
    fixtures.add("/ok", b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nX-Mode: fixture\r\n\r\nhello")
    result = LocalHTTPClient(fixtures).get("http://fixture.local/ok").await_once()
    assert result.is_ok
    response = result.value_or(None)
    assert response.status == 200
    assert response.header("x-mode") == "fixture"
    assert response.body == b"hello"


def test_http_client_rejects_external_fixture_authorities_and_missing_framing() -> None:
    fixtures = LocalHTTPFixtures()
    client = LocalHTTPClient(fixtures)
    external = client.get("https://example.test/ok").poll().value_or(None)
    assert external.error is not None and HTTPErrorCode.INVALID_URL.value in external.error.detail
    malformed = parse_http_response(b"HTTP/1.1 200 OK\r\n\r\nhello")
    assert malformed.code is HTTPErrorCode.FRAMING


def test_http_parser_rejects_chunked_oversized_and_injected_headers() -> None:
    chunked = parse_http_response(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0\r\n\r\n")
    assert chunked.code is HTTPErrorCode.UNSUPPORTED_TRANSFER
    fixtures = LocalHTTPFixtures()
    fixtures.add("/large", b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello")
    response = LocalHTTPClient(fixtures, limits=HTTPLimits(max_body_bytes=4)).get("http://fixture.local/large").poll().value_or(None)
    assert response.error is not None and HTTPErrorCode.BODY_LIMIT.value in response.error.detail

    class NoopTransport:
        def request(self, **_kwargs):
            raise AssertionError("unsafe request must be rejected before transport")

    injected = BoundedHTTPClient(NoopTransport()).get(
        "http://example.test/",
        headers=(("X-Test", "ok\r\nInjected: yes"),),
    ).poll().value_or(None)
    assert injected.error is not None


def test_https_transport_secure_defaults_cannot_be_disabled_accidentally() -> None:
    transport = SocketHTTPTransport()
    assert transport._tls_context.verify_mode == ssl.CERT_REQUIRED
    assert transport._tls_context.check_hostname is True

    insecure = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    insecure.check_hostname = False
    insecure.verify_mode = ssl.CERT_NONE
    with pytest.raises(ValueError, match="certificate and hostname"):
        SocketHTTPTransport(tls_context=insecure)


def test_real_loopback_tcp_transport_executes_bounded_http_request() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    received = []

    def serve() -> None:
        connection, _address = server.accept()
        with connection:
            request = bytearray()
            while b"\r\n\r\n" not in request:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                request.extend(chunk)
            received.append(bytes(request))
            connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        server.close()

    thread = threading.Thread(target=serve)
    thread.start()
    result = BoundedHTTPClient().get(f"http://127.0.0.1:{port}/probe", timeout=2).await_once()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert result.is_ok
    assert result.value_or(None).body == b"ok"
    assert received and received[0].startswith(b"GET /probe HTTP/1.1\r\n")


def test_post_body_and_total_response_budget_are_bounded() -> None:
    class EchoTransport:
        def request(self, **kwargs):
            assert b"POST /upload HTTP/1.1" in kwargs["request"]
            assert kwargs["request"].endswith(b"payload")
            return b"HTTP/1.1 201 Created\r\nContent-Length: 2\r\n\r\nok"

    result = BoundedHTTPClient(EchoTransport()).post("https://registry.test/upload", body=b"payload").await_once()
    assert result.is_ok and result.value_or(None).status == 201
