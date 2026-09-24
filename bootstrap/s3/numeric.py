"""Canonical scalar domains for the numeric M1.32 capability."""

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
    """Validate binary64 input while preserving IEEE-754 NaN/Inf/signed zero.

    Python floats are IEEE-754 binary64 on supported S3 hosts. The language
    contract intentionally does not reject non-finite values: NaN, positive
    and negative infinity, and signed zero are all valid f64 values.
    """

    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise NumericError(f"f64 requires a real number, got {value!r}")
    return float(value)


def sqrt_f64(value: float | int) -> float:
    """Return the IEEE-754 binary64 square root used by all backends."""

    value = validate_f64(value)
    if math.isnan(value):
        return value
    if value < 0.0:
        return float("nan")
    return math.sqrt(value)


def checked_i64_add(left: int, right: int) -> int:
    return validate_i64(validate_i64(left) + validate_i64(right))


def checked_i64_sub(left: int, right: int) -> int:
    return validate_i64(validate_i64(left) - validate_i64(right))


def checked_i64_mul(left: int, right: int) -> int:
    return validate_i64(validate_i64(left) * validate_i64(right))


def checked_i64_neg(value: int) -> int:
    return validate_i64(-validate_i64(value))


def checked_i64_div(left: int, right: int) -> int:
    """Checked signed i64 division truncated toward zero."""

    left = validate_i64(left)
    right = validate_i64(right)
    if right == 0:
        raise NumericError("i64 division by zero")
    if left == I64_MIN and right == -1:
        raise NumericError("i64 division overflow: INT64_MIN / -1")
    quotient = abs(left) // abs(right)
    if (left < 0) != (right < 0):
        quotient = -quotient
    return validate_i64(quotient)


def checked_i64_to_tryte(value: int) -> int:
    """Checked conversion to the six-trit balanced-ternary tryte domain."""

    value = validate_i64(value)
    if not -364 <= value <= 364:
        raise NumericError("i64 value is outside tryte range [-364, 364]")
    return value


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
            return NumericValue.i64(checked_i64_add(int(self.value), int(other.value)))
        return NumericValue.f64(float(self.value) + float(other.value))

    def subtract(self, other: NumericValue) -> NumericValue:
        self._require_same_type(other)
        if self.type is NumericType.I64:
            return NumericValue.i64(checked_i64_sub(int(self.value), int(other.value)))
        return NumericValue.f64(float(self.value) - float(other.value))

    def multiply(self, other: NumericValue) -> NumericValue:
        self._require_same_type(other)
        if self.type is NumericType.I64:
            return NumericValue.i64(checked_i64_mul(int(self.value), int(other.value)))
        return NumericValue.f64(float(self.value) * float(other.value))

    def divide(self, other: NumericValue) -> NumericValue:
        self._require_same_type(other)
        if self.type is NumericType.I64:
            return NumericValue.i64(checked_i64_div(int(self.value), int(other.value)))

        left = float(self.value)
        right = float(other.value)
        if right == 0.0:
            if left == 0.0:
                return NumericValue.f64(float("nan"))
            sign = math.copysign(1.0, left) * math.copysign(1.0, right)
            return NumericValue.f64(float("-inf") if sign < 0.0 else float("inf"))
        return NumericValue.f64(left / right)

    def negate(self) -> NumericValue:
        if self.type is NumericType.I64:
            return NumericValue.i64(checked_i64_neg(int(self.value)))
        return NumericValue.f64(-float(self.value))

    def _require_same_type(self, other: NumericValue) -> None:
        if self.type is not other.type:
            raise NumericError(
                f"cannot combine {self.type.value} with {other.type.value}"
            )
