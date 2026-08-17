"""Bounded M1.47 Python buffer and C ABI contracts.

This module models the stable boundary without depending on CPython private
APIs. Python views are borrowed for one call, while retained data is copied
into the existing S3-owned dynamic buffers.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Mapping, Sequence

from .dynamic import (
    BorrowConflictError,
    BufferRuntimeError,
    DynamicBytes,
    DynamicText,
)
from .ffi import FFIType, FFISignature, validate_signature


class BufferABIError(ValueError):
    """Raised for a view that is outside the bounded ABI profile."""


class BufferViewError(BufferABIError):
    """Raised when a Python object is not a one-dimensional byte view."""


class BufferReadOnlyError(BufferABIError):
    """Raised when a writable call is given a read-only view."""


class BufferReleasedError(BufferABIError):
    """Raised when a call-scoped view is used after release."""


class ABIStatus(IntEnum):
    """Stable integer statuses returned at the foreign boundary."""

    OK = 0
    INVALID_BUFFER = 1
    READ_ONLY = 2
    BORROW_CLOSED = 3
    BORROW_CONFLICT = 4
    BUFFER_ERROR = 5
    INTERNAL_ERROR = 6


@dataclass(frozen=True, slots=True)
class ABIErrorPayload:
    """Closed error payload; no Python exception crosses an ABI call."""

    code: str
    message: str

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("ABI error payload fields must be non-empty")


@dataclass(frozen=True, slots=True)
class ABIResult:
    """Explicit status/value result for hosted adapter calls."""

    status: ABIStatus
    value: Any = None
    error: ABIErrorPayload | None = None

    def __post_init__(self) -> None:
        if self.status is ABIStatus.OK and self.error is not None:
            raise ValueError("successful ABI result cannot contain an error")
        if self.status is not ABIStatus.OK and self.error is None:
            raise ValueError("failed ABI result requires an error payload")

    @property
    def ok(self) -> bool:
        return self.status is ABIStatus.OK


_I32 = "<iii"
_I32_MIN = -(2**31)
_I32_MAX = 2**31 - 1
_BYTE_FORMATS = frozenset({"B", "b", "c"})


@dataclass(frozen=True, slots=True)
class BufferDescriptor:
    """The stable 12-byte descriptor used by the C/Python boundary."""

    offset: int
    length: int
    capacity: int

    def __post_init__(self) -> None:
        values = (self.offset, self.length, self.capacity)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise BufferABIError("descriptor fields must be integers")
        if any(value < _I32_MIN or value > _I32_MAX for value in values):
            raise BufferABIError("descriptor fields must fit signed i32")
        if self.offset < 0 or self.length < 0 or self.capacity < 0:
            raise BufferABIError("descriptor fields must be non-negative")
        if self.length > self.capacity:
            raise BufferABIError("descriptor length exceeds capacity")

    def to_bytes(self) -> bytes:
        return struct.pack(_I32, self.offset, self.length, self.capacity)

    @classmethod
    def from_bytes(cls, payload: bytes) -> "BufferDescriptor":
        if len(payload) != struct.calcsize(_I32):
            raise BufferABIError("descriptor must contain exactly 12 bytes")
        return cls(*struct.unpack(_I32, payload))


class ABIByteView:
    """A released-once, one-dimensional byte view for one foreign call."""

    def __init__(
        self,
        view: memoryview,
        *,
        writable: bool,
        release_callback: Callable[[], None] | None = None,
        capacity: int | None = None,
    ) -> None:
        self._view = view
        self._writable = writable
        self._release_callback = release_callback
        self._closed = False
        view_capacity = len(view) if capacity is None else capacity
        self._descriptor = BufferDescriptor(0, len(view), view_capacity)

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def writable(self) -> bool:
        self._require_open()
        return self._writable

    @property
    def length(self) -> int:
        self._require_open()
        return self._descriptor.length

    @property
    def descriptor(self) -> BufferDescriptor:
        self._require_open()
        return self._descriptor

    def _require_open(self) -> None:
        if self._closed:
            raise BufferReleasedError("buffer view is released")

    def to_bytes(self) -> bytes:
        self._require_open()
        return self._view.tobytes()

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, index: int | slice) -> int | bytes:
        self._require_open()
        result = self._view[index]
        if isinstance(index, slice):
            return bytes(result)
        return int(result)

    def __setitem__(self, index: int | slice, value: int | bytes | bytearray) -> None:
        self._require_open()
        if not self._writable:
            raise BufferReadOnlyError("buffer view is read-only")
        self._view[index] = value

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._view.release()
        finally:
            if self._release_callback is not None:
                self._release_callback()
                self._release_callback = None

    release = close

    def __enter__(self) -> "ABIByteView":
        self._require_open()
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


def _normalized_byte_view(value: object, *, writable: bool) -> memoryview:
    try:
        view = memoryview(value)
    except TypeError as error:
        raise BufferViewError("object does not expose a Python buffer") from error
    try:
        if (
            view.ndim != 1
            or view.itemsize != 1
            or view.format not in _BYTE_FORMATS
            or not view.c_contiguous
            or view.strides != (1,)
        ):
            raise BufferViewError(
                "buffer must be one-dimensional, byte-format, and C-contiguous"
            )
        if writable and view.readonly:
            raise BufferReadOnlyError("writable buffer access requires a writable view")
        normalized = view.cast("B") if view.format != "B" else view
        if normalized.nbytes > _I32_MAX:
            normalized.release()
            raise BufferViewError("buffer length exceeds signed i32 ABI limit")
        return normalized
    except BaseException:
        if not view is locals().get("normalized"):
            view.release()
        raise


def adapt_python_buffer(value: object, *, writable: bool = False) -> ABIByteView:
    """Acquire and normalize one Python buffer view for a scoped call."""

    view = _normalized_byte_view(value, writable=writable)
    return ABIByteView(view, writable=writable and not view.readonly)


def _borrowed_s3_view(
    owner: DynamicBytes | DynamicText,
    *,
    writable: bool,
) -> ABIByteView:
    byte_owner = owner if isinstance(owner, DynamicBytes) else owner._bytes
    borrow = owner.borrow(mutable=writable)
    try:
        view = memoryview(byte_owner._storage)[: byte_owner.length]
        return ABIByteView(
            view,
            writable=writable,
            release_callback=borrow.close,
            capacity=byte_owner.capacity,
        )
    except BaseException:
        borrow.close()
        raise


def borrow_s3_bytes(owner: DynamicBytes, *, writable: bool = False) -> ABIByteView:
    """Expose S3-owned bytes without transferring ownership."""

    if not isinstance(owner, DynamicBytes):
        raise TypeError("borrow_s3_bytes requires DynamicBytes")
    return _borrowed_s3_view(owner, writable=writable)


def borrow_s3_text(owner: DynamicText, *, writable: bool = False) -> ABIByteView:
    """Expose UTF-8 bytes of S3-owned text without transferring ownership."""

    if not isinstance(owner, DynamicText):
        raise TypeError("borrow_s3_text requires DynamicText")
    return _borrowed_s3_view(owner, writable=writable)


def copy_to_s3_bytes(
    value: object,
    *,
    allocator: object | None = None,
) -> DynamicBytes:
    """Copy a Python or ABI view into S3-owned storage."""

    if isinstance(value, ABIByteView):
        return DynamicBytes(value.length, allocator=allocator, _data=value.to_bytes())
    with adapt_python_buffer(value) as view:
        return DynamicBytes(view.length, allocator=allocator, _data=view.to_bytes())


def copy_to_s3_text(value: object, *, allocator: object | None = None) -> DynamicText:
    """Copy a UTF-8 Python or ABI view into S3-owned text storage."""

    if isinstance(value, ABIByteView):
        return DynamicText(allocator=allocator, _bytes=value.to_bytes())
    with adapt_python_buffer(value) as view:
        return DynamicText(allocator=allocator, _bytes=view.to_bytes())


def _failure(status: ABIStatus, error: BaseException) -> ABIResult:
    code = getattr(error, "code", type(error).__name__)
    message = str(error).strip() or type(error).__name__
    return ABIResult(status, error=ABIErrorPayload(str(code), message))


def _status_for(error: BaseException) -> ABIStatus:
    if isinstance(error, BufferReleasedError):
        return ABIStatus.BORROW_CLOSED
    if isinstance(error, BufferReadOnlyError):
        return ABIStatus.READ_ONLY
    if isinstance(error, BorrowConflictError):
        return ABIStatus.BORROW_CONFLICT
    if isinstance(error, BufferViewError):
        return ABIStatus.INVALID_BUFFER
    if isinstance(error, BufferRuntimeError):
        return ABIStatus.BUFFER_ERROR
    return ABIStatus.INTERNAL_ERROR


def call_with_python_buffer(
    value: object,
    callback: Callable[[ABIByteView], Any],
    *,
    writable: bool = False,
) -> ABIResult:
    """Run one callback with a released-once Python view and closed errors."""

    try:
        with adapt_python_buffer(value, writable=writable) as view:
            return ABIResult(ABIStatus.OK, value=callback(view))
    except BaseException as error:
        return _failure(_status_for(error), error)


def call_with_s3_bytes(
    owner: DynamicBytes | DynamicText,
    callback: Callable[[ABIByteView], Any],
    *,
    writable: bool = False,
) -> ABIResult:
    """Run one callback against S3-owned bytes under the borrow contract."""

    try:
        with _borrowed_s3_view(owner, writable=writable) as view:
            return ABIResult(ABIStatus.OK, value=callback(view))
    except BaseException as error:
        return _failure(_status_for(error), error)


def abi_manifest(signatures: Sequence[FFISignature] = ()) -> dict[str, object]:
    """Return the canonical machine-readable M1.47 ABI manifest."""

    validated = sorted((validate_signature(signature) for signature in signatures), key=lambda item: item.symbol)
    if len({signature.symbol for signature in validated}) != len(validated):
        raise BufferABIError("ABI symbols must be unique")
    return {
        "schema_version": "s3.python-buffer-abi.v1",
        "descriptor": {
            "format": "little-endian i32 fields",
            "fields": ["offset", "length", "capacity"],
            "size": 12,
            "alignment": 4,
        },
        "ownership": "S3-owned; Python view call-scoped; exact release once",
        "buffer_profile": "one-dimensional byte-format C-contiguous views",
        "statuses": [status.name for status in ABIStatus],
        "signatures": [
            {
                "symbol": signature.symbol,
                "parameters": [parameter.value for parameter in signature.parameters],
                "result": signature.result.value,
                "abi_classes": [parameter.abi_class for parameter in signature.parameters],
            }
            for signature in validated
        ],
    }


def render_abi_manifest(signatures: Sequence[FFISignature] = ()) -> str:
    return json.dumps(abi_manifest(signatures), indent=2, sort_keys=True) + "\n"


_C_TYPES = {
    FFIType.TRIT: "int32_t",
    FFIType.TRYTE: "int32_t",
    FFIType.I64: "int64_t",
    FFIType.F64: "double",
    FFIType.BYTES_VIEW: "s3_bytes_view_v1",
    FFIType.TEXT_VIEW: "s3_text_view_v1",
}


def render_c_header(signatures: Sequence[FFISignature] = ()) -> str:
    """Render a deterministic C header for the closed M1.47 surface."""

    manifest = abi_manifest(signatures)
    declarations = [
        "#ifndef S3_PYTHON_BUFFER_ABI_V1_H",
        "#define S3_PYTHON_BUFFER_ABI_V1_H",
        "",
        "#include <stdint.h>",
        "",
        "typedef struct {",
        "    int32_t offset;",
        "    int32_t length;",
        "    int32_t capacity;",
        "} s3_bytes_view_v1;",
        "",
        "typedef s3_bytes_view_v1 s3_text_view_v1;",
        "",
        "typedef enum {",
        "    S3_STATUS_OK = 0,",
        "    S3_STATUS_INVALID_BUFFER = 1,",
        "    S3_STATUS_READ_ONLY = 2,",
        "    S3_STATUS_BORROW_CLOSED = 3,",
        "    S3_STATUS_BORROW_CONFLICT = 4,",
        "    S3_STATUS_BUFFER_ERROR = 5,",
        "    S3_STATUS_INTERNAL_ERROR = 6",
        "} s3_status_v1;",
        "",
        "typedef struct {",
        "    int32_t code;",
        "    const char *message;",
        "    int32_t message_length;",
        "} s3_error_v1;",
        "",
        "#ifndef S3_API",
        "#define S3_API",
        "#endif",
        "",
    ]
    for signature in manifest["signatures"]:
        parameters = signature["parameters"]
        parameter_text = ", ".join(
            f"{_C_TYPES[FFIType(parameter)]} arg{index}"
            for index, parameter in enumerate(parameters)
        ) or "void"
        declarations.append(
            f"S3_API {_C_TYPES[FFIType(signature['result'])]} {signature['symbol']}({parameter_text});"
        )
    declarations.extend(["", "#endif", ""])
    return "\n".join(declarations)
