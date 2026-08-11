"""Explicit tagged scalar values for the M1.35 dynamic boundary."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from .numeric import validate_f64, validate_i64
from .ternary import validate_trit, validate_tryte


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


class AllocationError(MemoryError):
    """Raised when the configured runtime allocator cannot satisfy a request."""


class Allocator:
    """Deterministic allocation provider boundary for owned runtime buffers."""

    def __init__(self, *, max_elements: int | None = None) -> None:
        if max_elements is not None and (not isinstance(max_elements, int) or max_elements < 0):
            raise ValueError("max_elements must be a non-negative integer or None")
        self.max_elements = max_elements
        self.allocations = 0

    def reserve(self, requested: int) -> None:
        if requested < 0:
            raise AllocationError("negative allocation request")
        if self.max_elements is not None and requested > self.max_elements:
            raise AllocationError(
                f"allocation request {requested} exceeds limit {self.max_elements}"
            )
        self.allocations += 1


T = TypeVar("T", int, float)


class BorrowedSlice(Generic[T]):
    """A bounded view into an OwnedBuffer; it never owns or copies elements."""

    def __init__(self, owner: OwnedBuffer[T], start: int, end: int, mutable: bool) -> None:
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
    """Runtime-sized contiguous storage owned by S3's runtime boundary."""

    _SIZES = {int: 8, float: 8}

    def __init__(
        self,
        element_type: type[T] | DynamicKind,
        *,
        allocator: Allocator | None = None,
        capacity: int = 0,
    ) -> None:
        self.kind = element_type if isinstance(element_type, DynamicKind) else None
        storage_type = float if element_type is DynamicKind.F64 else int if isinstance(element_type, DynamicKind) else element_type
        if storage_type not in self._SIZES:
            raise TypeError("owned buffers support only int and float primitives")
        if capacity < 0:
            raise ValueError("capacity must be non-negative")
        self.element_type = storage_type
        self.allocator = allocator or Allocator()
        self._capacity = capacity
        self._length = 0
        ctype = ctypes.c_longlong if element_type is int else ctypes.c_double
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
        return self._storage[index].item() if hasattr(self._storage[index], "item") else self._storage[index]

    def __setitem__(self, index: int, value: T) -> None:
        if not 0 <= index < self._length:
            raise IndexError("owned buffer index out of bounds")
        self._storage[index] = self._validate(value)

    def borrow(self, *, mutable: bool = False) -> BorrowedSlice[T]:
        return BorrowedSlice(self, 0, self.length, mutable)

    def borrow_range(self, start: int, end: int, *, mutable: bool = False) -> BorrowedSlice[T]:
        return BorrowedSlice(self, start, end, mutable)


class DynamicBytes(OwnedBuffer[int]):
    """Owned runtime bytes with the same checked growth contract."""

    def __init__(self, *, allocator: Allocator | None = None, capacity: int = 0) -> None:
        super().__init__(int, allocator=allocator, capacity=capacity)


class DynamicText:
    """Owned UTF-8 text backed by a runtime-owned byte buffer."""

    def __init__(self, value: str = "", *, allocator: Allocator | None = None) -> None:
        if not isinstance(value, str):
            raise TypeError("dynamic text requires a string")
        self._bytes = DynamicBytes(allocator=allocator, capacity=len(value.encode("utf-8")))
        for byte in value.encode("utf-8"):
            self._bytes.push(byte)

    @property
    def length(self) -> int:
        return self._bytes.length

    @property
    def capacity(self) -> int:
        return self._bytes.capacity

    def append(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("dynamic text append requires a string")
        for byte in value.encode("utf-8"):
            self._bytes.push(byte)

    def to_string(self) -> str:
        return bytes(self._bytes[index] for index in range(self._bytes.length)).decode("utf-8")
