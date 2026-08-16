"""Runtime-owned values for the M1.35 scalar and M1.39 buffer boundaries.

The public buffer classes deliberately model the language contract rather than
Python's convenient list semantics: capacity is explicit, push/append never
resize implicitly, and an active borrow prevents operations that could move or
invalidate the owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator

from .numeric import validate_f64, validate_i64


class DynamicError(TypeError):
    """Raised when a dynamic scalar is constructed or read incorrectly."""


class DynamicKind(Enum):
    TRIT = "trit"
    TRYTE = "tryte"
    I64 = "i64"
    F64 = "f64"


@dataclass(frozen=True, slots=True)
class DynamicValue:
    """A closed tagged union with no implicit numeric conversion."""

    kind: DynamicKind
    value: int | float

    def __post_init__(self) -> None:
        if self.kind is DynamicKind.F64:
            object.__setattr__(self, "value", validate_f64(self.value))
            return
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise DynamicError(f"{self.kind.value} dynamic value must be an integer")
        value = validate_i64(self.value)
        if self.kind is DynamicKind.TRIT and value not in (-1, 0, 1):
            raise DynamicError("trit dynamic value must be -1, 0, or 1")
        object.__setattr__(self, "value", value)

    @classmethod
    def trit(cls, value: int) -> DynamicValue:
        return cls(DynamicKind.TRIT, value)

    @classmethod
    def tryte(cls, value: int) -> DynamicValue:
        return cls(DynamicKind.TRYTE, value)

    @classmethod
    def i64(cls, value: int) -> DynamicValue:
        return cls(DynamicKind.I64, value)

    @classmethod
    def f64(cls, value: float) -> DynamicValue:
        return cls(DynamicKind.F64, value)

    def require(self, kind: DynamicKind) -> int | float:
        if self.kind is not kind:
            raise DynamicError(
                f"dynamic value has type {self.kind.value}; expected {kind.value}"
            )
        return self.value


MAX_BUFFER_BYTES = 2_147_483_647
DEFAULT_MAX_BUFFER_BYTES = 67_108_864


class BufferRuntimeError(RuntimeError):
    """Base class for deterministic dynamic-buffer traps."""

    code = "S3E_BUFFER"


class BufferBoundsError(BufferRuntimeError):
    code = "S3E_BUFFER_BOUNDS"


class BufferCapacityError(BufferRuntimeError):
    code = "S3E_BUFFER_CAPACITY"


class BufferAllocationError(BufferRuntimeError):
    code = "S3E_BUFFER_ALLOCATION"


class BufferFullError(BufferRuntimeError):
    code = "S3E_BUFFER_FULL"


class TextEncodingError(BufferRuntimeError):
    code = "S3E_TEXT_INVALID_UTF8"


class TextBoundaryError(BufferRuntimeError):
    code = "S3E_TEXT_BOUNDARY"


class BufferOctetRangeError(BufferRuntimeError):
    code = "S3E_BUFFER_OCTET_RANGE"


class BorrowConflictError(BufferRuntimeError):
    code = "S3E_SEMANTIC_BORROW_CONFLICT"


class MovedValueError(BufferRuntimeError):
    code = "S3E_SEMANTIC_USE_AFTER_MOVE"


class Allocator:
    """The single target-provided allocator boundary used by M1.39."""

    def __init__(
        self,
        *,
        max_bytes: int = DEFAULT_MAX_BUFFER_BYTES,
        max_allocations: int | None = None,
    ) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
            raise TypeError("max_bytes must be an integer")
        if not 0 <= max_bytes <= MAX_BUFFER_BYTES:
            raise ValueError("max_bytes is outside the logical buffer limit")
        if max_allocations is not None and (
            isinstance(max_allocations, bool)
            or not isinstance(max_allocations, int)
            or max_allocations < 0
        ):
            raise ValueError("max_allocations must be non-negative or None")
        self.max_bytes = max_bytes
        self.max_allocations = max_allocations
        self.allocations = 0
        self.allocated_bytes = 0

    def reserve(self, requested: int) -> None:
        """Validate one exact allocation without exposing host size_t rules."""

        if isinstance(requested, bool) or not isinstance(requested, int):
            raise BufferCapacityError("capacity must be an i64 integer")
        if requested < 0 or requested > MAX_BUFFER_BYTES:
            raise BufferCapacityError("capacity is outside the i64 buffer limit")
        if requested > self.max_bytes:
            raise BufferAllocationError(
                f"allocation request {requested} exceeds active limit {self.max_bytes}"
            )
        if self.max_allocations is not None and self.allocations >= self.max_allocations:
            raise BufferAllocationError("allocator allocation limit reached")
        self.allocations += 1
        self.allocated_bytes += requested


class BorrowedBuffer:
    """Lexically manageable non-owning view of a dynamic byte/text owner."""

    def __init__(self, owner: "DynamicBytes | DynamicText", mutable: bool) -> None:
        self._owner = owner
        self.mutable = mutable
        self._closed = False
        owner._acquire_borrow(mutable)

    @property
    def owner(self) -> "DynamicBytes | DynamicText":
        if self._closed:
            raise BorrowConflictError("borrow is no longer active")
        return self._owner

    @property
    def length(self) -> int:
        return self.owner.length

    @property
    def capacity(self) -> int:
        return self.owner.capacity

    def close(self) -> None:
        if not self._closed:
            self._owner._release_borrow(self.mutable)
            self._closed = True

    def __enter__(self) -> "BorrowedBuffer":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def __getitem__(self, index: int) -> int:
        return self.owner[index]

    def __setitem__(self, index: int, value: int) -> None:
        if not self.mutable:
            raise BorrowConflictError("shared borrow is immutable")
        self.owner[index] = value


class DynamicBytes:
    """Owned runtime byte sequence with exact explicit capacity."""

    def __init__(
        self,
        capacity: int = 0,
        *,
        allocator: Allocator | None = None,
        _data: bytes | bytearray = b"",
    ) -> None:
        self.allocator = allocator or Allocator()
        _validate_capacity(capacity)
        if len(_data) > capacity:
            raise BufferCapacityError("initial data exceeds capacity")
        if capacity:
            self.allocator.reserve(capacity)
        self._storage = bytearray(capacity)
        self._storage[: len(_data)] = _data
        self._length = len(_data)
        self._shared_borrows = 0
        self._mutable_borrow = False
        self._moved = False

    @property
    def length(self) -> int:
        self._require_live()
        return self._length

    @property
    def capacity(self) -> int:
        self._require_live()
        return len(self._storage)

    def _require_live(self) -> None:
        if self._moved:
            raise MovedValueError("owned buffer was moved")

    def _require_unborrowed(self) -> None:
        self._require_live()
        if self._shared_borrows or self._mutable_borrow:
            raise BorrowConflictError("owner operation overlaps an active borrow")

    def _acquire_borrow(self, mutable: bool) -> None:
        self._require_live()
        if mutable:
            if self._mutable_borrow or self._shared_borrows:
                raise BorrowConflictError("mutable borrow overlaps an active borrow")
            self._mutable_borrow = True
        else:
            if self._mutable_borrow:
                raise BorrowConflictError("shared borrow overlaps a mutable borrow")
            self._shared_borrows += 1

    def _release_borrow(self, mutable: bool) -> None:
        if mutable:
            self._mutable_borrow = False
        elif self._shared_borrows:
            self._shared_borrows -= 1

    def move(self) -> "DynamicBytes":
        self._require_unborrowed()
        replacement = object.__new__(type(self))
        replacement.allocator = self.allocator
        replacement._storage = self._storage
        replacement._length = self._length
        replacement._shared_borrows = 0
        replacement._mutable_borrow = False
        replacement._moved = False
        self._moved = True
        return replacement

    def reserve(self, capacity: int) -> None:
        self._require_unborrowed()
        _validate_capacity(capacity)
        if capacity <= self.capacity:
            return
        self.allocator.reserve(capacity)
        self._storage.extend(b"\x00" * (capacity - self.capacity))

    def get(self, index: int) -> int:
        self._require_live()
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < self._length:
            raise BufferBoundsError("byte index is outside [0, length)")
        return self._storage[index]

    def set(self, index: int, value: int) -> None:
        self._require_unborrowed()
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < self._length:
            raise BufferBoundsError("byte index is outside [0, length)")
        _validate_octet(value)
        self._storage[index] = value

    def push(self, value: int) -> None:
        self._require_unborrowed()
        _validate_octet(value)
        if self._length >= self.capacity:
            raise BufferFullError("byte buffer has no reserved capacity")
        self._storage[self._length] = value
        self._length += 1

    def clone(self) -> "DynamicBytes":
        self._require_live()
        return DynamicBytes(self._length, allocator=self.allocator, _data=self.to_bytes())

    def slice(self, start: int, end: int) -> "DynamicBytes":
        self._require_live()
        _validate_slice(start, end, self._length)
        return DynamicBytes(end - start, allocator=self.allocator, _data=self.to_bytes()[start:end])

    def concat(self, other: "DynamicBytes") -> "DynamicBytes":
        self._require_live()
        other._require_live()
        data = self.to_bytes() + other.to_bytes()
        return DynamicBytes(len(data), allocator=self.allocator, _data=data)

    def to_bytes(self) -> bytes:
        self._require_live()
        return bytes(self._storage[: self._length])

    def borrow(self, *, mutable: bool = False) -> BorrowedBuffer:
        return BorrowedBuffer(self, mutable)

    def __getitem__(self, index: int) -> int:
        return self.get(index)

    def __setitem__(self, index: int, value: int) -> None:
        self.set(index, value)


class DynamicText:
    """Owned valid UTF-8 text; lengths and capacities are byte counts."""

    def __init__(
        self,
        value: str = "",
        *,
        capacity: int | None = None,
        allocator: Allocator | None = None,
        _bytes: bytes | None = None,
    ) -> None:
        if _bytes is None:
            if not isinstance(value, str):
                raise TypeError("dynamic text requires a string")
            data = value.encode("utf-8")
        else:
            data = bytes(_bytes)
            _decode_utf8(data)
        if capacity is None:
            capacity = len(data)
        self._bytes = DynamicBytes(capacity, allocator=allocator, _data=data)

    @classmethod
    def new(cls, capacity: int, *, allocator: Allocator | None = None) -> "DynamicText":
        return cls(capacity=capacity, allocator=allocator)

    @classmethod
    def from_static(cls, value: str, *, allocator: Allocator | None = None) -> "DynamicText":
        return cls(value, allocator=allocator)

    @classmethod
    def from_bytes(cls, value: DynamicBytes, *, allocator: Allocator | None = None) -> "DynamicText":
        return cls(allocator=allocator, _bytes=value.to_bytes())

    @property
    def length(self) -> int:
        return self._bytes.length

    @property
    def capacity(self) -> int:
        return self._bytes.capacity

    def reserve(self, capacity: int) -> None:
        self._bytes.reserve(capacity)

    def _acquire_borrow(self, mutable: bool) -> None:
        self._bytes._acquire_borrow(mutable)

    def _release_borrow(self, mutable: bool) -> None:
        self._bytes._release_borrow(mutable)

    def append(self, value: "DynamicText") -> None:
        self.append_static(value.to_string())

    def append_static(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("dynamic text append requires a string")
        data = value.encode("utf-8")
        if len(data) > self.capacity - self.length:
            raise BufferFullError("text buffer has no reserved capacity")
        for byte in data:
            self._bytes.push(byte)

    def clone(self) -> "DynamicText":
        return DynamicText(_bytes=self._bytes.to_bytes(), allocator=self._bytes.allocator)

    def concat(self, other: "DynamicText") -> "DynamicText":
        return DynamicText(_bytes=self._bytes.to_bytes() + other._bytes.to_bytes(), allocator=self._bytes.allocator)

    def slice(self, start: int, end: int) -> "DynamicText":
        data = self._bytes.to_bytes()
        _validate_slice(start, end, len(data))
        if not _is_utf8_boundary(data, start) or not _is_utf8_boundary(data, end):
            raise TextBoundaryError("text slice is not on a UTF-8 boundary")
        return DynamicText(_bytes=data[start:end], allocator=self._bytes.allocator)

    def find(self, needle: "DynamicText") -> int:
        return self.to_string().find(needle.to_string())

    def to_string(self) -> str:
        return _decode_utf8(self._bytes.to_bytes())

    def borrow(self, *, mutable: bool = False) -> BorrowedBuffer:
        return BorrowedBuffer(self, mutable)


def bytes_new(capacity: int, *, allocator: Allocator | None = None) -> DynamicBytes:
    return DynamicBytes(capacity, allocator=allocator)


def _owned(value: DynamicBytes | DynamicText | BorrowedBuffer):
    return value.owner if isinstance(value, BorrowedBuffer) else value


def bytes_len(value: DynamicBytes | BorrowedBuffer) -> int:
    return _owned(value).length


def bytes_capacity(value: DynamicBytes | BorrowedBuffer) -> int:
    return _owned(value).capacity


def bytes_get(value: DynamicBytes | BorrowedBuffer, index: int) -> int:
    return _owned(value).get(index)


def bytes_set(value: DynamicBytes | BorrowedBuffer, index: int, octet: int) -> None:
    _owned(value).set(index, octet)


def bytes_push(value: DynamicBytes | BorrowedBuffer, octet: int) -> None:
    _owned(value).push(octet)


def bytes_reserve(value: DynamicBytes | BorrowedBuffer, capacity: int) -> None:
    _owned(value).reserve(capacity)


def bytes_clone(value: DynamicBytes | BorrowedBuffer) -> DynamicBytes:
    return _owned(value).clone()


def bytes_concat(left: DynamicBytes | BorrowedBuffer, right: DynamicBytes | BorrowedBuffer) -> DynamicBytes:
    return _owned(left).concat(_owned(right))


def bytes_slice(value: DynamicBytes | BorrowedBuffer, start: int, end: int) -> DynamicBytes:
    return _owned(value).slice(start, end)


def text_new(capacity: int, *, allocator: Allocator | None = None) -> DynamicText:
    return DynamicText.new(capacity, allocator=allocator)


def bytes_from_text(value: DynamicText, *, allocator: Allocator | None = None) -> DynamicBytes:
    return DynamicBytes(value.length, allocator=allocator, _data=value.to_string().encode("utf-8"))


def text_from_bytes(value: DynamicBytes, *, allocator: Allocator | None = None) -> DynamicText:
    return DynamicText.from_bytes(value, allocator=allocator)


def text_len(value: DynamicText | BorrowedBuffer) -> int:
    return _owned(value).length


def text_capacity(value: DynamicText | BorrowedBuffer) -> int:
    return _owned(value).capacity


def text_reserve(value: DynamicText | BorrowedBuffer, capacity: int) -> None:
    _owned(value).reserve(capacity)


def text_append(value: DynamicText | BorrowedBuffer, suffix: DynamicText | BorrowedBuffer) -> None:
    _owned(value).append(_owned(suffix))


def text_append_static(value: DynamicText | BorrowedBuffer, suffix: str) -> None:
    _owned(value).append_static(suffix)


def text_clone(value: DynamicText | BorrowedBuffer) -> DynamicText:
    return _owned(value).clone()


def text_concat(left: DynamicText | BorrowedBuffer, right: DynamicText | BorrowedBuffer) -> DynamicText:
    return _owned(left).concat(_owned(right))


def text_slice(value: DynamicText | BorrowedBuffer, start: int, end: int) -> DynamicText:
    return _owned(value).slice(start, end)


def text_find(value: DynamicText | BorrowedBuffer, needle: DynamicText | BorrowedBuffer) -> int:
    return _owned(value).find(_owned(needle))


def _validate_capacity(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_BUFFER_BYTES:
        raise BufferCapacityError("capacity must be a non-negative i64 within the buffer limit")


def _validate_octet(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
        raise BufferOctetRangeError("value is not an octet")


def _validate_slice(start: int, end: int, length: int) -> None:
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, end)):
        raise BufferBoundsError("slice bounds must be i64 integers")
    if not 0 <= start <= end <= length:
        raise BufferBoundsError("slice bounds are outside [0, length]")


def _decode_utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TextEncodingError("invalid UTF-8") from error


def _is_utf8_boundary(data: bytes, position: int) -> bool:
    return position == 0 or position == len(data) or not (data[position] & 0xC0) == 0x80
