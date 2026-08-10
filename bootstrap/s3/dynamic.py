"""Explicit tagged scalar values for the M1.35 dynamic boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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
