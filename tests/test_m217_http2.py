from __future__ import annotations

import pytest

from bootstrap.s3.http2 import (
    PREFACE,
    ConnectionState,
    FrameType,
    Http2Connection,
    Http2Error,
    Http2Frame,
    parse_frame,
    serialize_frame,
)


def test_http2_preface_frame_round_trip_and_stream_state() -> None:
    connection = Http2Connection()
    connection.accept_preface(PREFACE)
    assert connection.state is ConnectionState.OPEN
    headers = serialize_frame(Http2Frame(FrameType.HEADERS, 0, 1, b"headers"))
    assert parse_frame(headers) == Http2Frame(FrameType.HEADERS, 0, 1, b"headers")
    connection.receive(headers)
    data = serialize_frame(Http2Frame(FrameType.DATA, 1, 1, b"body"))
    connection.receive(data)
    assert connection.streams[1] == "half-closed"


def test_http2_rejects_bad_lengths_streams_and_transitions() -> None:
    connection = Http2Connection()
    connection.accept_preface(PREFACE)
    with pytest.raises(Http2Error, match="length"):
        parse_frame(b"\x00\x00\x10\x00\x00\x00\x00\x00\x00", max_frame_size=8)
    with pytest.raises(Http2Error, match="non-zero"):
        serialize_frame(Http2Frame(FrameType.DATA, 0, 0, b"x"))
    connection.receive(serialize_frame(Http2Frame(FrameType.GOAWAY, 0, 0, b"\x00" * 8)))
    assert connection.state is ConnectionState.GOAWAY
    with pytest.raises(Http2Error, match="after GOAWAY"):
        connection.receive(serialize_frame(Http2Frame(FrameType.HEADERS, 0, 3, b"h")))


def test_http2_flow_control_and_ping_shapes_are_bounded() -> None:
    with pytest.raises(Http2Error, match="increment"):
        serialize_frame(Http2Frame(FrameType.WINDOW_UPDATE, 0, 0, b"\x00\x00\x00\x00"))
    with pytest.raises(Http2Error, match="eight-byte"):
        serialize_frame(Http2Frame(FrameType.PING, 0, 0, b"short"))
