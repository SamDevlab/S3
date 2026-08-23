"""Bounded HTTP/2 framing, HPACK decoding and connection state."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum, IntEnum

from .hpack_huffman import HuffmanError, decode_huffman


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


class HPACKError(Http2Error):
    """Raised when a bounded HPACK block is malformed or exceeds its contract."""


# RFC 7541 Appendix A. Dynamic state is bounded by HPACKDecoder.
_STATIC_TABLE = (
    (":authority", ""), (":method", "GET"), (":method", "POST"),
    (":path", "/"), (":path", "/index.html"), (":scheme", "http"),
    (":scheme", "https"), (":status", "200"), (":status", "204"),
    (":status", "206"), (":status", "304"), (":status", "400"),
    (":status", "404"), (":status", "500"), ("accept-charset", ""),
    ("accept-encoding", "gzip, deflate"), ("accept-language", ""),
    ("accept-ranges", ""), ("accept", ""), ("access-control-allow-origin", ""),
    ("age", ""), ("allow", ""), ("authorization", ""), ("cache-control", ""),
    ("content-disposition", ""), ("content-encoding", ""), ("content-language", ""),
    ("content-length", ""), ("content-location", ""), ("content-range", ""),
    ("content-type", ""), ("cookie", ""), ("date", ""), ("etag", ""),
    ("expect", ""), ("expires", ""), ("from", ""), ("host", ""),
    ("if-match", ""), ("if-modified-since", ""), ("if-none-match", ""),
    ("if-range", ""), ("if-unmodified-since", ""), ("last-modified", ""),
    ("link", ""), ("location", ""), ("max-forwards", ""), ("proxy-authenticate", ""),
    ("proxy-authorization", ""), ("range", ""), ("referer", ""),
    ("refresh", ""), ("retry-after", ""), ("server", ""), ("set-cookie", ""),
    ("strict-transport-security", ""), ("transfer-encoding", ""), ("user-agent", ""),
    ("vary", ""), ("via", ""), ("www-authenticate", ""),
)


def _hpack_integer(data: bytes, offset: int, prefix_bits: int) -> tuple[int, int]:
    if offset >= len(data):
        raise HPACKError("HPACK integer is truncated")
    mask = (1 << prefix_bits) - 1
    value = data[offset] & mask
    offset += 1
    if value < mask:
        return value, offset
    shift = 0
    while True:
        if offset >= len(data) or shift > 56:
            raise HPACKError("HPACK integer exceeds bound")
        byte = data[offset]
        offset += 1
        value += (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7


def _hpack_string(data: bytes, offset: int, *, max_string_bytes: int) -> tuple[str, int]:
    if offset >= len(data):
        raise HPACKError("HPACK string is truncated")
    huffman = bool(data[offset] & 0x80)
    length, offset = _hpack_integer(data, offset, 7)
    if length > max_string_bytes or offset + length > len(data):
        raise HPACKError("HPACK string exceeds bound")
    encoded = data[offset:offset + length]
    if huffman:
        try:
            encoded = decode_huffman(encoded, max_output_bytes=max_string_bytes)
        except HuffmanError as error:
            raise HPACKError(str(error)) from error
    try:
        return encoded.decode("utf-8"), offset + length
    except UnicodeDecodeError as error:
        raise HPACKError("HPACK string is not UTF-8") from error


def _entry_size(entry: tuple[str, str]) -> int:
    name, value = entry
    return 32 + len(name.encode("utf-8")) + len(value.encode("utf-8"))


def _evict_dynamic_table(
    table: list[tuple[str, str]],
    size: int,
    limit: int,
) -> int:
    while size > limit and table:
        size -= _entry_size(table.pop())
    return size


def _add_dynamic_entry(
    table: list[tuple[str, str]],
    size: int,
    entry: tuple[str, str],
    limit: int,
) -> int:
    entry_size = _entry_size(entry)
    if entry_size > limit:
        table.clear()
        return 0
    table.insert(0, entry)
    return _evict_dynamic_table(table, size + entry_size, limit)


class HPACKDecoder:
    """Bounded stateful HPACK decoder with RFC 7541 dynamic table semantics."""

    def __init__(self, *, max_dynamic_table_bytes: int = 4096) -> None:
        if (
            isinstance(max_dynamic_table_bytes, bool)
            or not isinstance(max_dynamic_table_bytes, int)
            or max_dynamic_table_bytes < 0
        ):
            raise ValueError("HPACK dynamic table bound must be non-negative")
        self.max_dynamic_table_bytes = max_dynamic_table_bytes
        self._table_limit = max_dynamic_table_bytes
        self._dynamic_table: tuple[tuple[str, str], ...] = ()
        self._dynamic_size = 0

    @property
    def dynamic_table(self) -> tuple[tuple[str, str], ...]:
        return self._dynamic_table

    @property
    def dynamic_table_size(self) -> int:
        return self._dynamic_size

    @property
    def table_size_limit(self) -> int:
        return self._table_limit

    def set_max_table_size(self, size: int) -> None:
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("HPACK table size must be non-negative")
        if size > self.max_dynamic_table_bytes:
            raise HPACKError("HPACK table size exceeds configured bound")
        table = list(self._dynamic_table)
        self._dynamic_size = _evict_dynamic_table(table, self._dynamic_size, size)
        self._dynamic_table = tuple(table)
        self._table_limit = size

    def _lookup(
        self,
        index: int,
        table: list[tuple[str, str]],
    ) -> tuple[str, str]:
        if index < 1:
            raise HPACKError("HPACK index must be positive")
        if index <= len(_STATIC_TABLE):
            return _STATIC_TABLE[index - 1]
        dynamic_index = index - len(_STATIC_TABLE) - 1
        if dynamic_index >= len(table):
            raise HPACKError("dynamic HPACK index is out of range")
        return table[dynamic_index]

    def _lookup_name(
        self,
        index: int,
        table: list[tuple[str, str]],
    ) -> str:
        return self._lookup(index, table)[0]

    def decode(
        self,
        block: bytes,
        *,
        max_headers: int = 128,
        max_header_bytes: int = 16_384,
    ) -> tuple[tuple[str, str], ...]:
        if not isinstance(block, bytes):
            raise TypeError("HPACK block must be bytes")
        if (
            isinstance(max_headers, bool)
            or not isinstance(max_headers, int)
            or max_headers <= 0
            or isinstance(max_header_bytes, bool)
            or not isinstance(max_header_bytes, int)
            or max_header_bytes <= 0
        ):
            raise ValueError("HPACK bounds must be positive")

        offset = 0
        result: list[tuple[str, str]] = []
        retained = 0
        table = list(self._dynamic_table)
        dynamic_size = self._dynamic_size
        table_limit = self._table_limit
        saw_header = False
        while offset < len(block):
            first = block[offset]
            if first & 0x80:
                index, offset = _hpack_integer(block, offset, 7)
                header = self._lookup(index, table)
                saw_header = True
            elif first & 0x40:
                index, offset = _hpack_integer(block, offset, 6)
                if index:
                    name = self._lookup_name(index, table)
                else:
                    name, offset = _hpack_string(
                        block,
                        offset,
                        max_string_bytes=max_header_bytes,
                    )
                value, offset = _hpack_string(
                    block,
                    offset,
                    max_string_bytes=max_header_bytes,
                )
                header = (name, value)
                dynamic_size = _add_dynamic_entry(table, dynamic_size, header, table_limit)
                saw_header = True
            elif first & 0x20:
                if saw_header:
                    raise HPACKError("HPACK table size update must precede headers")
                new_limit, offset = _hpack_integer(block, offset, 5)
                if new_limit > self.max_dynamic_table_bytes:
                    raise HPACKError("HPACK table size exceeds configured bound")
                table_limit = new_limit
                dynamic_size = _evict_dynamic_table(table, dynamic_size, table_limit)
                continue
            else:
                index, offset = _hpack_integer(block, offset, 4)
                if index:
                    name = self._lookup_name(index, table)
                else:
                    name, offset = _hpack_string(
                        block,
                        offset,
                        max_string_bytes=max_header_bytes,
                    )
                value, offset = _hpack_string(
                    block,
                    offset,
                    max_string_bytes=max_header_bytes,
                )
                header = (name, value)
                saw_header = True

            retained += len(header[0].encode("utf-8")) + len(header[1].encode("utf-8"))
            if len(result) >= max_headers or retained > max_header_bytes:
                raise HPACKError("decoded headers exceed bound")
            result.append(header)

        self._dynamic_table = tuple(table)
        self._dynamic_size = dynamic_size
        self._table_limit = table_limit
        return tuple(result)


def decode_hpack(
    block: bytes,
    *,
    decoder: HPACKDecoder | None = None,
    max_dynamic_table_bytes: int = 4096,
    max_headers: int = 128,
    max_header_bytes: int = 16_384,
) -> tuple[tuple[str, str], ...]:
    """Decode one HPACK block, optionally retaining dynamic state."""

    active = decoder or HPACKDecoder(max_dynamic_table_bytes=max_dynamic_table_bytes)
    return active.decode(
        block,
        max_headers=max_headers,
        max_header_bytes=max_header_bytes,
    )


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
