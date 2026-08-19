from __future__ import annotations

from bootstrap.s3.async_http import HTTPLimits, LocalHTTPClient, LocalHTTPFixtures, HTTPErrorCode, parse_http_response


def test_local_http_fixture_get_is_bounded_and_deterministic() -> None:
    fixtures = LocalHTTPFixtures()
    fixtures.add("/ok", b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nX-Mode: fixture\r\n\r\nhello")
    result = LocalHTTPClient(fixtures).get("http://fixture.local/ok").await_once()
    assert result.is_ok
    response = result.value_or(None)
    assert response.status == 200
    assert response.header("x-mode") == "fixture"
    assert response.body == b"hello"


def test_http_client_rejects_external_authorities_and_missing_framing() -> None:
    fixtures = LocalHTTPFixtures()
    client = LocalHTTPClient(fixtures)
    external = client.get("https://example.test/ok").poll().value_or(None)
    assert external.error is not None and HTTPErrorCode.INVALID_URL.value in external.error.detail
    malformed = parse_http_response(b"HTTP/1.1 200 OK\r\n\r\nhello")
    assert malformed.code is HTTPErrorCode.FRAMING


def test_http_parser_rejects_chunked_and_oversized_bodies() -> None:
    chunked = parse_http_response(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0\r\n\r\n")
    assert chunked.code is HTTPErrorCode.UNSUPPORTED_TRANSFER
    fixtures = LocalHTTPFixtures()
    fixtures.add("/large", b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello")
    response = LocalHTTPClient(fixtures, limits=HTTPLimits(max_body_bytes=4)).get("http://fixture.local/large").poll().value_or(None)
    assert response.error is not None and HTTPErrorCode.BODY_LIMIT.value in response.error.detail
