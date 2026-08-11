from __future__ import annotations

import math

import pytest

from bootstrap.s3.numeric import (
    I64_MAX,
    I64_MIN,
    NumericError,
    NumericType,
    NumericValue,
    validate_f64,
    validate_i64,
)


def test_i64_accepts_full_signed_domain() -> None:
    assert validate_i64(I64_MIN) == I64_MIN
    assert validate_i64(I64_MAX) == I64_MAX
    assert NumericValue.i64(I64_MAX).type is NumericType.I64


def test_i64_rejects_overflow_and_non_integer_values() -> None:
    with pytest.raises(NumericError):
        validate_i64(I64_MAX + 1)
    with pytest.raises(NumericError):
        validate_i64(True)  # type: ignore[arg-type]


def test_f64_preserves_ieee754_domain() -> None:
    assert validate_f64(1) == 1.0
    assert NumericValue.f64(1.25) == NumericValue(NumericType.F64, 1.25)
    assert math.isinf(validate_f64(math.inf))
    assert math.isnan(validate_f64(math.nan))
    negative_zero = validate_f64(-0.0)
    assert negative_zero == 0.0
    assert math.copysign(1.0, negative_zero) == -1.0


def test_numeric_addition_is_typed_and_checked() -> None:
    assert NumericValue.i64(2).add(NumericValue.i64(3)).value == 5
    assert NumericValue.f64(0.5).add(NumericValue.f64(0.25)).value == 0.75
    with pytest.raises(NumericError):
        NumericValue.i64(1).add(NumericValue.f64(1.0))
    with pytest.raises(NumericError):
        NumericValue.i64(I64_MAX).add(NumericValue.i64(1))
