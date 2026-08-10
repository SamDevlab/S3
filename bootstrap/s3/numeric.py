"""Canonical scalar domains for the numeric M1.32 foundation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1


class NumericError(ValueError):
    """Base error for numeric-domain violations."""


class NumericType(Enum):
    I64 = "i64"
    F64 = "f64"


def validate_i64(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise NumericError(f"i64 requires an integer, got {value!r}")
    if not I64_MIN <= value <= I64_MAX:
        raise NumericError(f"i64 value {value} is outside [{I64_MIN}, {I64_MAX}]")
    return value


def validate_f64(value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise NumericError(f"f64 requires a real number, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise NumericError(f"f64 requires a finite value, got {value!r}")
    return result


@dataclass(frozen=True, slots=True)
class NumericValue:
    type: NumericType
    value: int | float

    def __post_init__(self) -> None:
        if self.type is NumericType.I64:
            object.__setattr__(self, "value", validate_i64(self.value))
        elif self.type is NumericType.F64:
            object.__setattr__(self, "value", validate_f64(self.value))
        else:
            raise NumericError(f"unsupported numeric type {self.type!r}")

    @classmethod
    def i64(cls, value: int) -> NumericValue:
        return cls(NumericType.I64, value)

    @classmethod
    def f64(cls, value: float | int) -> NumericValue:
        return cls(NumericType.F64, value)

    def add(self, other: NumericValue) -> NumericValue:
        self._require_same_type(other)
        if self.type is NumericType.I64:
            return NumericValue.i64(validate_i64(self.value + other.value))
        return NumericValue.f64(validate_f64(self.value + other.value))

    def _require_same_type(self, other: NumericValue) -> None:
        if self.type is not other.type:
            raise NumericError(
                f"cannot combine {self.type.value} with {other.type.value}"
            )
