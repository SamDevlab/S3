"""Closed scalar FFI signature contracts for the M1.34 boundary."""

from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


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


def build_shared_library(
    source: str,
    output: Path,
    *,
    extra_objects: tuple[Path, ...] = (),
    keep_assembly: Path | None = None,
) -> Path:
    """Compile ordinary S3 source into a real Linux FFI shared object."""

    from .backends.x86_64 import NativeToolchain, generate_ffi_assembly
    from .pipeline import compile_source

    result = compile_source(source)
    _, ordinary_assembly = result.require_ordinary_artifacts()
    assembly = generate_ffi_assembly(ordinary_assembly)
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
