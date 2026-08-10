"""Closed scalar FFI signature contracts for the M1.34 boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FFIError(ValueError):
    """Raised when an external signature is outside the supported contract."""


class FFIType(Enum):
    """Scalar types with an explicit native ABI class."""

    TRIT = "trit"
    TRYTE = "tryte"
    I64 = "i64"
    F64 = "f64"

    @property
    def abi_class(self) -> str:
        return "float" if self is FFIType.F64 else "integer"


_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class FFISignature:
    """A named, scalar-only external function signature."""

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


def validate_signature(signature: FFISignature) -> FFISignature:
    """Return a validated signature for callers that accept user data."""

    if not isinstance(signature, FFISignature):
        raise FFIError("expected FFISignature")
    return signature
