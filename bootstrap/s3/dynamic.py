"""Runtime-owned values for the M1.35 scalar and M1.39 buffer boundaries.

The public buffer classes deliberately model the language contract rather than
Python's convenient list semantics: capacity is explicit, push/append never
resize implicitly, and an active borrow prevents operations that could move or
invalidate the owner.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Iterator, TypeVar

from .numeric import validate_f64, validate_i64
from .ternary import TRYTE_MAX, TRYTE_MIN, validate_trit, validate_tryte


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


class AllocationError(BufferAllocationError):
    """Compatibility error for the original scalar owned-buffer API."""


class Allocator:
    """The single target-provided allocator boundary used by M1.39."""

    def __init__(
        self,
        *,
        max_bytes: int = DEFAULT_MAX_BUFFER_BYTES,
        max_allocations: int | None = None,
        max_elements: int | None = None,
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
        if max_elements is not None and (
            isinstance(max_elements, bool)
            or not isinstance(max_elements, int)
            or max_elements < 0
        ):
            raise ValueError("max_elements must be non-negative or None")
        self.max_bytes = max_bytes
        self.max_allocations = max_allocations
        self.max_elements = max_elements
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
        if self.max_elements is not None and requested > self.max_elements:
            raise AllocationError(
                f"allocation request {requested} exceeds limit {self.max_elements}"
            )
        if self.max_allocations is not None and self.allocations >= self.max_allocations:
            raise BufferAllocationError("allocator allocation limit reached")
        self.allocations += 1
        self.allocated_bytes += requested


T = TypeVar("T", int, float)


class BorrowedSlice(Generic[T]):
    """Compatibility view for the original scalar owned-buffer API."""

    def __init__(self, owner: "OwnedBuffer[T]", start: int, end: int, mutable: bool) -> None:
        if not 0 <= start <= end <= owner.length:
            raise IndexError("borrowed slice bounds are outside the buffer")
        self._owner = owner
        self._start = start
        self._end = end
        self._mutable = mutable

    @property
    def length(self) -> int:
        return self._end - self._start

    @property
    def address(self) -> int:
        return self._owner.address + self._start * self._owner.element_size

    def __getitem__(self, index: int) -> T:
        if not 0 <= index < self.length:
            raise IndexError("borrowed slice index out of bounds")
        return self._owner[self._start + index]

    def __setitem__(self, index: int, value: T) -> None:
        if not self._mutable:
            raise DynamicError("borrowed slice is immutable")
        if not 0 <= index < self.length:
            raise IndexError("borrowed slice index out of bounds")
        self._owner[self._start + index] = value


class OwnedBuffer(Generic[T]):
    """Compatibility scalar buffer retained for the M1.35 public API."""

    _SIZES = {int: 8, float: 8}

    def __init__(
        self,
        element_type: type[T] | DynamicKind,
        *,
        allocator: Allocator | None = None,
        capacity: int = 0,
    ) -> None:
        self.kind = element_type if isinstance(element_type, DynamicKind) else None
        storage_type = (
            float if element_type is DynamicKind.F64
            else int if isinstance(element_type, DynamicKind)
            else element_type
        )
        if storage_type not in self._SIZES:
            raise TypeError("owned buffers support only int and float primitives")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
            raise ValueError("capacity must be a non-negative integer")
        self.element_type = storage_type
        self.allocator = allocator or Allocator()
        self._capacity = capacity
        self._length = 0
        ctype = ctypes.c_longlong if element_type is not DynamicKind.F64 and storage_type is int else ctypes.c_double
        self._storage = (ctype * capacity)()
        self.allocator.reserve(capacity)

    @property
    def element_size(self) -> int:
        return self._SIZES[self.element_type]

    @property
    def length(self) -> int:
        return self._length

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def address(self) -> int:
        return ctypes.addressof(self._storage) if self._capacity else 0

    def _validate(self, value: T) -> T:
        if self.element_type is int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise DynamicError("owned integer buffer requires int values")
            if self.kind is DynamicKind.TRIT:
                return validate_trit(value)  # type: ignore[return-value]
            if self.kind is DynamicKind.TRYTE:
                return validate_tryte(value)  # type: ignore[return-value]
            return value
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise DynamicError("owned float buffer requires numeric values")
        return float(value)  # type: ignore[return-value]

    def reserve(self, requested: int) -> None:
        if requested <= self._capacity:
            return
        self.allocator.reserve(requested)
        ctype = ctypes.c_longlong if self.element_type is int else ctypes.c_double
        replacement = (ctype * requested)()
        for index in range(self._length):
            replacement[index] = self._storage[index]
        self._storage = replacement
        self._capacity = requested

    def push(self, value: T) -> None:
        value = self._validate(value)
        if self.length == self.capacity:
            self.reserve(max(1, self.capacity * 2))
        self._storage[self._length] = value
        self._length += 1

    def __getitem__(self, index: int) -> T:
        if not 0 <= index < self._length:
            raise IndexError("owned buffer index out of bounds")
        return self._storage[index].value if hasattr(self._storage[index], "value") else self._storage[index]

    def __setitem__(self, index: int, value: T) -> None:
        if not 0 <= index < self._length:
            raise IndexError("owned buffer index out of bounds")
        self._storage[index] = self._validate(value)

    def borrow(self, *, mutable: bool = False) -> BorrowedSlice[T]:
        return BorrowedSlice(self, 0, self.length, mutable)

    def borrow_range(self, start: int, end: int, *, mutable: bool = False) -> BorrowedSlice[T]:
        return BorrowedSlice(self, start, end, mutable)


class BorrowedBuffer:
    """Lexically manageable non-owning view of a dynamic byte/text owner."""

    def __init__(self, owner: "DynamicBytes | DynamicText | DynamicVector", mutable: bool) -> None:
        self._owner = owner
        self.mutable = mutable
        self._closed = False
        owner._acquire_borrow(mutable)

    @property
    def owner(self) -> "DynamicBytes | DynamicText | DynamicVector":
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

    def append(self, value: "DynamicText | str") -> None:
        if isinstance(value, str):
            self.append_static(value)
            return
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


class DynamicVector:
    """Owned ordered collection for one closed scalar element family."""

    _ELEMENT_SIZES = {"tryte": 2, "i64": 8, "f64": 8}

    def __init__(
        self,
        element_type: str,
        capacity: int = 0,
        *,
        allocator: Allocator | None = None,
        _data: tuple[int | float, ...] = (),
    ) -> None:
        if element_type not in self._ELEMENT_SIZES:
            raise DynamicError(f"unsupported vector element type '{element_type}'")
        self.element_type = element_type
        self.allocator = allocator or Allocator()
        _validate_vector_capacity(capacity, self._ELEMENT_SIZES[element_type])
        if len(_data) > capacity:
            raise BufferCapacityError("initial vector data exceeds capacity")
        for value in _data:
            _validate_vector_element(element_type, value)
        if capacity:
            self.allocator.reserve(capacity * self._ELEMENT_SIZES[element_type])
        self._storage = list(_data) + [0] * (capacity - len(_data))
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
            raise MovedValueError("owned vector was moved")

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

    def move(self) -> "DynamicVector":
        self._require_unborrowed()
        replacement = object.__new__(type(self))
        replacement.element_type = self.element_type
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
        _validate_vector_capacity(capacity, self._ELEMENT_SIZES[self.element_type])
        if capacity <= self.capacity:
            return
        self.allocator.reserve(capacity * self._ELEMENT_SIZES[self.element_type])
        self._storage.extend([0] * (capacity - self.capacity))

    def push(self, value: int | float) -> None:
        self._require_unborrowed()
        _validate_vector_element(self.element_type, value)
        if self._length >= self.capacity:
            raise BufferFullError("vector has no reserved capacity")
        self._storage[self._length] = value
        self._length += 1

    def pop(self) -> int | float:
        self._require_unborrowed()
        if self._length == 0:
            raise BufferBoundsError("cannot pop an empty vector")
        self._length -= 1
        return self._storage[self._length]

    def get(self, index: int) -> int | float:
        self._require_live()
        _validate_vector_index(index, self._length)
        return self._storage[index]

    def set(self, index: int, value: int | float) -> None:
        self._require_unborrowed()
        _validate_vector_index(index, self._length)
        _validate_vector_element(self.element_type, value)
        self._storage[index] = value

    def clone(self) -> "DynamicVector":
        self._require_live()
        return DynamicVector(
            self.element_type,
            self.capacity,
            allocator=self.allocator,
            _data=tuple(self._storage[: self._length]),
        )

    def slice(self, start: int, end: int) -> "DynamicVector":
        self._require_live()
        _validate_slice(start, end, self._length)
        return DynamicVector(
            self.element_type,
            end - start,
            allocator=self.allocator,
            _data=tuple(self._storage[start:end]),
        )

    def borrow(self, *, mutable: bool = False) -> BorrowedBuffer:
        return BorrowedBuffer(self, mutable)

    def __iter__(self) -> Iterator[int | float]:
        self._require_live()
        return iter(tuple(self._storage[: self._length]))

    def __getitem__(self, index: int) -> int | float:
        return self.get(index)

    def __setitem__(self, index: int, value: int | float) -> None:
        self.set(index, value)


class DynamicMap:
    """Ordered i64 to i64 map with explicit capacity and stable insertion order."""

    def __init__(
        self,
        capacity: int = 0,
        *,
        allocator: Allocator | None = None,
        _data: tuple[tuple[int, int], ...] = (),
    ) -> None:
        _validate_collection_capacity(capacity, 16)
        if len(_data) > capacity:
            raise BufferCapacityError("initial map data exceeds capacity")
        for key, value in _data:
            _validate_i64_pair(key, value)
        self.allocator = allocator or Allocator()
        if capacity:
            self.allocator.reserve(capacity * 16)
        self._storage = list(_data) + [(0, 0)] * (capacity - len(_data))
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
            raise MovedValueError("owned map was moved")

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

    def _find(self, key: int) -> int:
        _validate_i64_pair(key, 0)
        for index in range(self._length):
            if self._storage[index][0] == key:
                return index
        return -1

    def move(self) -> "DynamicMap":
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
        _validate_collection_capacity(capacity, 16)
        if capacity <= self.capacity:
            return
        self.allocator.reserve(capacity * 16)
        self._storage.extend([(0, 0)] * (capacity - self.capacity))

    def put(self, key: int, value: int) -> None:
        self._require_unborrowed()
        _validate_i64_pair(key, value)
        index = self._find(key)
        if index >= 0:
            self._storage[index] = (key, value)
            return
        if self._length >= self.capacity:
            raise BufferFullError("map has no reserved capacity")
        self._storage[self._length] = (key, value)
        self._length += 1

    def contains(self, key: int) -> int:
        self._require_live()
        return -1 if self._find(key) >= 0 else 0

    def get(self, key: int) -> int:
        self._require_live()
        index = self._find(key)
        if index < 0:
            raise BufferBoundsError("map key is absent")
        return self._storage[index][1]

    def remove(self, key: int) -> None:
        self._require_unborrowed()
        index = self._find(key)
        if index < 0:
            return
        self._storage[index : self._length - 1] = self._storage[index + 1 : self._length]
        self._length -= 1
        self._storage[self._length] = (0, 0)

    def key_at(self, index: int) -> int:
        _validate_vector_index(index, self._length)
        return self._storage[index][0]

    def value_at(self, index: int) -> int:
        _validate_vector_index(index, self._length)
        return self._storage[index][1]

    def clone(self) -> "DynamicMap":
        self._require_live()
        return DynamicMap(
            self.capacity,
            allocator=self.allocator,
            _data=tuple(self._storage[: self._length]),
        )

    def borrow(self, *, mutable: bool = False) -> BorrowedBuffer:
        return BorrowedBuffer(self, mutable)


class DynamicSet:
    """Ordered i64 set derived from the same explicit collection contract."""

    def __init__(
        self,
        capacity: int = 0,
        *,
        allocator: Allocator | None = None,
        _data: tuple[int, ...] = (),
    ) -> None:
        _validate_collection_capacity(capacity, 8)
        if len(_data) > capacity:
            raise BufferCapacityError("initial set data exceeds capacity")
        for value in _data:
            validate_i64(value)
        if len(set(_data)) != len(_data):
            raise DynamicError("set data contains duplicate values")
        self.allocator = allocator or Allocator()
        if capacity:
            self.allocator.reserve(capacity * 8)
        self._storage = list(_data) + [0] * (capacity - len(_data))
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
            raise MovedValueError("owned set was moved")

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

    def _find(self, value: int) -> int:
        validate_i64(value)
        for index in range(self._length):
            if self._storage[index] == value:
                return index
        return -1

    def move(self) -> "DynamicSet":
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
        _validate_collection_capacity(capacity, 8)
        if capacity <= self.capacity:
            return
        self.allocator.reserve(capacity * 8)
        self._storage.extend([0] * (capacity - self.capacity))

    def add(self, value: int) -> None:
        self._require_unborrowed()
        validate_i64(value)
        if self._find(value) >= 0:
            return
        if self._length >= self.capacity:
            raise BufferFullError("set has no reserved capacity")
        self._storage[self._length] = value
        self._length += 1

    def contains(self, value: int) -> int:
        self._require_live()
        return -1 if self._find(value) >= 0 else 0

    def remove(self, value: int) -> None:
        self._require_unborrowed()
        index = self._find(value)
        if index < 0:
            return
        self._storage[index : self._length - 1] = self._storage[index + 1 : self._length]
        self._length -= 1
        self._storage[self._length] = 0

    def at(self, index: int) -> int:
        return self.get(index)

    def get(self, index: int) -> int:
        self._require_live()
        _validate_vector_index(index, self._length)
        return self._storage[index]

    def clone(self) -> "DynamicSet":
        self._require_live()
        return DynamicSet(
            self.capacity,
            allocator=self.allocator,
            _data=tuple(self._storage[: self._length]),
        )

    def borrow(self, *, mutable: bool = False) -> BorrowedBuffer:
        return BorrowedBuffer(self, mutable)


def bytes_new(capacity: int, *, allocator: Allocator | None = None) -> DynamicBytes:
    return DynamicBytes(capacity, allocator=allocator)


def _owned(value: DynamicBytes | DynamicText | DynamicVector | DynamicMap | DynamicSet | BorrowedBuffer):
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


def _vector_owner(value: DynamicVector | BorrowedBuffer, element_type: str) -> DynamicVector:
    owner = _owned(value)
    if not isinstance(owner, DynamicVector) or owner.element_type != element_type:
        raise DynamicError(f"expected {element_type} vector")
    return owner


def _vector_new(element_type: str, capacity: int, allocator: Allocator | None = None) -> DynamicVector:
    return DynamicVector(element_type, capacity, allocator=allocator)


def tryte_vector_new(capacity: int, *, allocator: Allocator | None = None) -> DynamicVector:
    return _vector_new("tryte", capacity, allocator)


def i64_vector_new(capacity: int, *, allocator: Allocator | None = None) -> DynamicVector:
    return _vector_new("i64", capacity, allocator)


def f64_vector_new(capacity: int, *, allocator: Allocator | None = None) -> DynamicVector:
    return _vector_new("f64", capacity, allocator)


def _vector_len(value: DynamicVector | BorrowedBuffer, element_type: str) -> int:
    return _vector_owner(value, element_type).length


def _vector_capacity(value: DynamicVector | BorrowedBuffer, element_type: str) -> int:
    return _vector_owner(value, element_type).capacity


def _vector_reserve(value: DynamicVector | BorrowedBuffer, capacity: int, element_type: str) -> None:
    _vector_owner(value, element_type).reserve(capacity)


def _vector_push(value: DynamicVector | BorrowedBuffer, element: int | float, element_type: str) -> None:
    _vector_owner(value, element_type).push(element)


def _vector_pop(value: DynamicVector | BorrowedBuffer, element_type: str) -> int | float:
    return _vector_owner(value, element_type).pop()


def _vector_get(value: DynamicVector | BorrowedBuffer, index: int, element_type: str) -> int | float:
    return _vector_owner(value, element_type).get(index)


def _vector_set(value: DynamicVector | BorrowedBuffer, index: int, element: int | float, element_type: str) -> None:
    _vector_owner(value, element_type).set(index, element)


def _vector_clone(value: DynamicVector | BorrowedBuffer, element_type: str) -> DynamicVector:
    return _vector_owner(value, element_type).clone()


def _vector_slice(value: DynamicVector | BorrowedBuffer, start: int, end: int, element_type: str) -> DynamicVector:
    return _vector_owner(value, element_type).slice(start, end)


def tryte_vector_len(value: DynamicVector | BorrowedBuffer) -> int:
    return _vector_len(value, "tryte")


def i64_vector_len(value: DynamicVector | BorrowedBuffer) -> int:
    return _vector_len(value, "i64")


def f64_vector_len(value: DynamicVector | BorrowedBuffer) -> int:
    return _vector_len(value, "f64")


def tryte_vector_capacity(value: DynamicVector | BorrowedBuffer) -> int:
    return _vector_capacity(value, "tryte")


def i64_vector_capacity(value: DynamicVector | BorrowedBuffer) -> int:
    return _vector_capacity(value, "i64")


def f64_vector_capacity(value: DynamicVector | BorrowedBuffer) -> int:
    return _vector_capacity(value, "f64")


def tryte_vector_reserve(value, capacity: int) -> None:
    _vector_reserve(value, capacity, "tryte")


def i64_vector_reserve(value, capacity: int) -> None:
    _vector_reserve(value, capacity, "i64")


def f64_vector_reserve(value, capacity: int) -> None:
    _vector_reserve(value, capacity, "f64")


def tryte_vector_push(value, element: int) -> None:
    _vector_push(value, element, "tryte")


def i64_vector_push(value, element: int) -> None:
    _vector_push(value, element, "i64")


def f64_vector_push(value, element: float) -> None:
    _vector_push(value, element, "f64")


def tryte_vector_pop(value) -> int:
    return _vector_pop(value, "tryte")


def i64_vector_pop(value) -> int:
    return _vector_pop(value, "i64")


def f64_vector_pop(value) -> float:
    return _vector_pop(value, "f64")


def tryte_vector_get(value, index: int) -> int:
    return _vector_get(value, index, "tryte")


def i64_vector_get(value, index: int) -> int:
    return _vector_get(value, index, "i64")


def f64_vector_get(value, index: int) -> float:
    return _vector_get(value, index, "f64")


def tryte_vector_set(value, index: int, element: int) -> None:
    _vector_set(value, index, element, "tryte")


def i64_vector_set(value, index: int, element: int) -> None:
    _vector_set(value, index, element, "i64")


def f64_vector_set(value, index: int, element: float) -> None:
    _vector_set(value, index, element, "f64")


def tryte_vector_clone(value) -> DynamicVector:
    return _vector_clone(value, "tryte")


def i64_vector_clone(value) -> DynamicVector:
    return _vector_clone(value, "i64")


def f64_vector_clone(value) -> DynamicVector:
    return _vector_clone(value, "f64")


def tryte_vector_slice(value, start: int, end: int) -> DynamicVector:
    return _vector_slice(value, start, end, "tryte")


def i64_vector_slice(value, start: int, end: int) -> DynamicVector:
    return _vector_slice(value, start, end, "i64")


def f64_vector_slice(value, start: int, end: int) -> DynamicVector:
    return _vector_slice(value, start, end, "f64")


def _map_owner(value: DynamicMap | BorrowedBuffer) -> DynamicMap:
    owner = _owned(value)
    if not isinstance(owner, DynamicMap):
        raise DynamicError("expected i64 map")
    return owner


def _set_owner(value: DynamicSet | BorrowedBuffer) -> DynamicSet:
    owner = _owned(value)
    if not isinstance(owner, DynamicSet):
        raise DynamicError("expected i64 set")
    return owner


def i64_map_new(capacity: int, *, allocator: Allocator | None = None) -> DynamicMap:
    return DynamicMap(capacity, allocator=allocator)


def i64_map_len(value) -> int:
    return _map_owner(value).length


def i64_map_capacity(value) -> int:
    return _map_owner(value).capacity


def i64_map_reserve(value, capacity: int) -> None:
    _map_owner(value).reserve(capacity)


def i64_map_put(value, key: int, item: int) -> None:
    _map_owner(value).put(key, item)


def i64_map_contains(value, key: int) -> int:
    return _map_owner(value).contains(key)


def i64_map_get(value, key: int) -> int:
    return _map_owner(value).get(key)


def i64_map_remove(value, key: int) -> None:
    _map_owner(value).remove(key)


def i64_map_key_at(value, index: int) -> int:
    return _map_owner(value).key_at(index)


def i64_map_value_at(value, index: int) -> int:
    return _map_owner(value).value_at(index)


def i64_map_clone(value) -> DynamicMap:
    return _map_owner(value).clone()


def i64_set_new(capacity: int, *, allocator: Allocator | None = None) -> DynamicSet:
    return DynamicSet(capacity, allocator=allocator)


def i64_set_len(value) -> int:
    return _set_owner(value).length


def i64_set_capacity(value) -> int:
    return _set_owner(value).capacity


def i64_set_reserve(value, capacity: int) -> None:
    _set_owner(value).reserve(capacity)


def i64_set_add(value, item: int) -> None:
    _set_owner(value).add(item)


def i64_set_contains(value, item: int) -> int:
    return _set_owner(value).contains(item)


def i64_set_remove(value, item: int) -> None:
    _set_owner(value).remove(item)


def i64_set_at(value, index: int) -> int:
    return _set_owner(value).at(index)


def i64_set_clone(value) -> DynamicSet:
    return _set_owner(value).clone()


def _validate_capacity(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_BUFFER_BYTES:
        raise BufferCapacityError("capacity must be a non-negative i64 within the buffer limit")


def _validate_vector_capacity(value: int, element_size: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BufferCapacityError("vector capacity must be a non-negative i64")
    if value > MAX_BUFFER_BYTES // element_size:
        raise BufferCapacityError("vector capacity exceeds the byte limit")


def _validate_collection_capacity(value: int, element_size: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BufferCapacityError("collection capacity must be a non-negative i64")
    if value > MAX_BUFFER_BYTES // element_size:
        raise BufferCapacityError("collection capacity exceeds the byte limit")


def _validate_i64_pair(key: int, value: int) -> None:
    validate_i64(key)
    validate_i64(value)


def _validate_vector_index(value: int, length: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < length:
        raise BufferBoundsError("vector index is outside [0, length)")


def _validate_vector_element(element_type: str, value: int | float) -> None:
    if element_type == "tryte":
        if isinstance(value, bool) or not isinstance(value, int) or not TRYTE_MIN <= value <= TRYTE_MAX:
            raise BufferOctetRangeError("value is outside tryte range")
        return
    if element_type == "i64":
        validate_i64(value)
        return
    validate_f64(value)


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
