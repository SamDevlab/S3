"""Closed scalar FFI signature contracts for the M1.34 boundary."""

from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from threading import Lock


class FFIError(ValueError):
    """Raised when an external signature is outside the supported contract."""


class FFIType(Enum):
    """Closed foreign types with an explicit native ABI class."""

    TRIT = "trit"
    TRYTE = "tryte"
    I64 = "i64"
    F64 = "f64"
    BYTES_VIEW = "bytes_view"
    TEXT_VIEW = "text_view"

    @property
    def abi_class(self) -> str:
        if self is FFIType.F64:
            return "float"
        if self in (FFIType.BYTES_VIEW, FFIType.TEXT_VIEW):
            return "memory"
        return "integer"

    @property
    def is_buffer_view(self) -> bool:
        return self in (FFIType.BYTES_VIEW, FFIType.TEXT_VIEW)


_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ABI_VERSION = re.compile(r"^s3-ffi/[0-9]+\.[0-9]+$")


@dataclass(frozen=True, slots=True)
class FFISignature:
    """A named external function signature over the closed FFI type set."""

    symbol: str
    parameters: tuple[FFIType, ...]
    result: FFIType

    def __post_init__(self) -> None:
        if not _SYMBOL.fullmatch(self.symbol):
            raise FFIError(f"invalid external symbol {self.symbol!r}")
        if not isinstance(self.result, FFIType):
            raise FFIError("external result must be an FFIType")
        if any(not isinstance(parameter, FFIType) for parameter in self.parameters):
            raise FFIError("external parameters must be scalar FFI types")

    @property
    def integer_parameter_count(self) -> int:
        return sum(parameter.abi_class == "integer" for parameter in self.parameters)

    @property
    def float_parameter_count(self) -> int:
        return sum(parameter.abi_class == "float" for parameter in self.parameters)

    @property
    def buffer_parameter_count(self) -> int:
        return sum(parameter.is_buffer_view for parameter in self.parameters)


@dataclass(frozen=True, slots=True)
class FFIContract:
    """Explicit ABI envelope; it does not expose raw pointers to S3 code."""

    version: str = "s3-ffi/1.0"
    calling_convention: str = "sysv-amd64"
    integer_widths: tuple[tuple[str, int], ...] = (("i64", 64), ("trit", 8), ("tryte", 64))
    boolean_representation: str = "i8-0-or-1"
    return_convention: str = "scalar-or-explicit-status"
    struct_layout: str = "abi-marked-only"
    error_convention: str = "explicit-status"
    buffer_convention: str = "pointer-plus-length-call-scoped"
    ownership_transfer: str = "caller-retains-unless-explicit"
    raw_pointers_contained: bool = True

    def __post_init__(self) -> None:
        if _ABI_VERSION.fullmatch(self.version) is None:
            raise FFIError("FFI contract version is invalid")
        if self.calling_convention not in {"sysv-amd64", "c-platform-default"}:
            raise FFIError("unsupported FFI calling convention")
        if not self.raw_pointers_contained:
            raise FFIError("raw pointers must remain contained inside the FFI boundary")
        if tuple(sorted(self.integer_widths)) != self.integer_widths or any(width <= 0 for _, width in self.integer_widths):
            raise FFIError("integer widths must be sorted and positive")

    @property
    def payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "calling_convention": self.calling_convention,
            "integer_widths": dict(self.integer_widths),
            "boolean_representation": self.boolean_representation,
            "return_convention": self.return_convention,
            "struct_layout": self.struct_layout,
            "error_convention": self.error_convention,
            "buffer_convention": self.buffer_convention,
            "ownership_transfer": self.ownership_transfer,
            "raw_pointers_contained": self.raw_pointers_contained,
        }


def validate_contract(signature: FFISignature, contract: FFIContract | None = None) -> FFIContract:
    """Validate the closed signature and return the explicit ABI contract."""

    validate_signature(signature)
    resolved = contract or FFIContract()
    if signature.buffer_parameter_count and resolved.buffer_convention != "pointer-plus-length-call-scoped":
        raise FFIError("buffer signatures require the bounded call-scoped convention")
    return resolved


def build_shared_library(
    source: str,
    output: Path,
    *,
    extra_objects: tuple[Path, ...] = (),
    keep_assembly: Path | None = None,
    native_policy: str | None = None,
) -> Path:
    """Compile ordinary S3 source into a real Linux FFI shared object."""

    from .backends.x86_64 import NativeToolchain, generate_ffi_assembly
    from .pipeline import compile_source

    result = compile_source(source)
    _, ordinary_assembly = result.require_ordinary_artifacts()
    assembly = generate_ffi_assembly(ordinary_assembly, native_policy=native_policy)
    return NativeToolchain.detect().build_shared(
        assembly,
        output,
        extra_objects=extra_objects,
        keep_assembly=keep_assembly,
    )


def validate_signature(signature: FFISignature) -> FFISignature:
    """Return a validated signature for callers that accept user data."""

    if not isinstance(signature, FFISignature):
        raise FFIError("expected FFISignature")
    return signature


@dataclass(frozen=True, slots=True)
class FFIHandle:
    """Opaque, process-local handle; its integer is not a native pointer."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int) or self.value <= 0:
            raise FFIError("FFI handle must be a positive opaque integer")


class FFIBufferRegistry:
    """Bounded ownership registry for call-scoped FFI byte buffers."""

    def __init__(self, *, max_buffers: int = 256, max_bytes: int = 1 << 20) -> None:
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (max_buffers, max_bytes)):
            raise ValueError("FFI buffer bounds must be positive integers")
        self.max_buffers = max_buffers
        self.max_bytes = max_bytes
        self._buffers: dict[FFIHandle, bytearray] = {}
        self._next = 1
        self._lock = Lock()

    def acquire(self, data: bytes | bytearray) -> FFIHandle:
        if not isinstance(data, (bytes, bytearray)):
            raise FFIError("FFI buffer data must be bytes")
        if len(data) > self.max_bytes:
            raise FFIError("FFI buffer exceeds bound")
        with self._lock:
            if len(self._buffers) >= self.max_buffers:
                raise FFIError("FFI buffer count exceeds bound")
            handle = FFIHandle(self._next)
            self._next += 1
            self._buffers[handle] = bytearray(data)
            return handle

    def view(self, handle: FFIHandle) -> bytes:
        with self._lock:
            try:
                return bytes(self._buffers[handle])
            except KeyError as error:
                raise FFIError("FFI handle is closed or unknown") from error

    def write(self, handle: FFIHandle, data: bytes | bytearray) -> None:
        if not isinstance(data, (bytes, bytearray)) or len(data) > self.max_bytes:
            raise FFIError("FFI buffer data exceeds bound")
        with self._lock:
            if handle not in self._buffers:
                raise FFIError("FFI handle is closed or unknown")
            self._buffers[handle] = bytearray(data)

    def release(self, handle: FFIHandle) -> None:
        with self._lock:
            if self._buffers.pop(handle, None) is None:
                raise FFIError("FFI handle is closed or unknown")
