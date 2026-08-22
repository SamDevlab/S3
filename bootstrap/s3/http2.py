"""Bounded HTTP/2 framing and connection-state foundation (HPACK deferred)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum, IntEnum


class Http2Error(ValueError):
    """Raised for malformed frames or illegal connection transitions."""


class FrameType(IntEnum):
    DATA = 0x0
    HEADERS = 0x1
    RST_STREAM = 0x3
    SETTINGS = 0x4
    PING = 0x6
    GOAWAY = 0x7
    WINDOW_UPDATE = 0x8


class ConnectionState(Enum):
    PREFACE = "preface"
    OPEN = "open"
    GOAWAY = "goaway"
    CLOSED = "closed"


PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"


@dataclass(frozen=True, slots=True)
class Http2Frame:
    frame_type: int
    flags: int
    stream_id: int
    payload: bytes

    def __post_init__(self) -> None:
        if isinstance(self.frame_type, bool) or not isinstance(self.frame_type, int) or not 0 <= self.frame_type <= 255:
            raise Http2Error("frame type must be an 8-bit integer")
        if isinstance(self.flags, bool) or not isinstance(self.flags, int) or not 0 <= self.flags <= 255:
            raise Http2Error("frame flags must be an 8-bit integer")
        if isinstance(self.stream_id, bool) or not isinstance(self.stream_id, int) or not 0 <= self.stream_id <= 0x7FFFFFFF:
            raise Http2Error("stream id must be a 31-bit integer")
        if not isinstance(self.payload, bytes):
            raise TypeError("frame payload must be bytes")


def parse_frame(data: bytes, *, max_frame_size: int = 16_384) -> Http2Frame:
    if not isinstance(data, bytes) or len(data) < 9:
        raise Http2Error("HTTP/2 frame header is incomplete")
    if isinstance(max_frame_size, bool) or not isinstance(max_frame_size, int) or max_frame_size <= 0:
        raise ValueError("max frame size must be positive")
    length = int.from_bytes(data[:3], "big")
    if length > max_frame_size or len(data) != length + 9:
        raise Http2Error("HTTP/2 frame length is invalid or exceeds bound")
    frame = Http2Frame(data[3], data[4], int.from_bytes(data[5:9], "big") & 0x7FFFFFFF, data[9:])
    _validate_frame(frame)
    return frame


def serialize_frame(frame: Http2Frame, *, max_frame_size: int = 16_384) -> bytes:
    _validate_frame(frame)
    if len(frame.payload) > max_frame_size:
        raise Http2Error("HTTP/2 frame payload exceeds bound")
    return len(frame.payload).to_bytes(3, "big") + bytes((frame.frame_type, frame.flags)) + struct.pack(">I", frame.stream_id) + frame.payload


def _validate_frame(frame: Http2Frame) -> None:
    try:
        kind = FrameType(frame.frame_type)
    except ValueError:
        return
    if kind is FrameType.PING and (frame.stream_id != 0 or len(frame.payload) != 8):
        raise Http2Error("PING requires stream 0 and an eight-byte payload")
    if kind is FrameType.SETTINGS:
        if frame.stream_id != 0 or (frame.flags & 0x1 and frame.payload) or len(frame.payload) % 6:
            raise Http2Error("SETTINGS frame is invalid")
    if kind is FrameType.GOAWAY and (frame.stream_id != 0 or len(frame.payload) < 8):
        raise Http2Error("GOAWAY frame is invalid")
    if kind in {FrameType.HEADERS, FrameType.DATA, FrameType.RST_STREAM} and frame.stream_id == 0:
        raise Http2Error("stream frame requires a non-zero stream id")
    if kind is FrameType.RST_STREAM and len(frame.payload) != 4:
        raise Http2Error("RST_STREAM payload must be four bytes")
    if kind is FrameType.WINDOW_UPDATE:
        if len(frame.payload) != 4 or int.from_bytes(frame.payload, "big") & 0x7FFFFFFF == 0:
            raise Http2Error("WINDOW_UPDATE increment is invalid")


class Http2Connection:
    """Pure state machine; it does not open sockets or decode HPACK."""

    def __init__(self, *, max_frame_size: int = 16_384) -> None:
        self.max_frame_size = max_frame_size
        self.state = ConnectionState.PREFACE
        self.streams: dict[int, str] = {}

    def accept_preface(self, data: bytes) -> None:
        if self.state is not ConnectionState.PREFACE or data != PREFACE:
            raise Http2Error("invalid HTTP/2 connection preface")
        self.state = ConnectionState.OPEN

    def receive(self, data: bytes) -> Http2Frame:
        if self.state not in {ConnectionState.OPEN, ConnectionState.GOAWAY}:
            raise Http2Error("connection is not accepting frames")
        frame = parse_frame(data, max_frame_size=self.max_frame_size)
        kind = FrameType(frame.frame_type) if frame.frame_type in set(item.value for item in FrameType) else None
        if kind is FrameType.GOAWAY:
            self.state = ConnectionState.GOAWAY
        elif kind is FrameType.HEADERS:
            if self.state is ConnectionState.GOAWAY:
                raise Http2Error("HEADERS are not allowed after GOAWAY")
            current = self.streams.get(frame.stream_id)
            if current in {"closed", "half-closed"}:
                raise Http2Error("HEADERS received on a closed stream")
            self.streams[frame.stream_id] = "half-closed" if frame.flags & 0x1 else "open"
        elif kind is FrameType.DATA:
            if self.streams.get(frame.stream_id) != "open":
                raise Http2Error("DATA requires an open stream")
            if frame.flags & 0x1:
                self.streams[frame.stream_id] = "half-closed"
        elif kind is FrameType.RST_STREAM:
            self.streams[frame.stream_id] = "closed"
        return frame
