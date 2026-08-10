from __future__ import annotations

import math

import pytest

from bootstrap.s3.numeric import (
    I64_MAX,
    I64_MIN,
    NumericError,
    NumericValue,
    checked_i64_add,
    checked_i64_div,
    checked_i64_mul,
    checked_i64_neg,
    checked_i64_sub,
    checked_i64_to_tryte,
    validate_f64,
)


def test_checked_i64_operations_cover_required_machine_domain() -> None:
    assert checked_i64_add(10, 20) == 30
    assert checked_i64_sub(10, 20) == -10
    assert checked_i64_mul(-7, 6) == -42
    assert checked_i64_div(7, 3) == 2
    assert checked_i64_div(-7, 3) == -2
    assert checked_i64_div(7, -3) == -2
    assert checked_i64_neg(7) == -7


@pytest.mark.parametrize(
    "operation",
    [
        lambda: checked_i64_add(I64_MAX, 1),
        lambda: checked_i64_sub(I64_MIN, 1),
        lambda: checked_i64_mul(I64_MAX, 2),
        lambda: checked_i64_neg(I64_MIN),
        lambda: checked_i64_div(I64_MIN, -1),
    ],
)
def test_checked_i64_operations_reject_overflow(operation) -> None:
    with pytest.raises(NumericError):
        operation()


def test_checked_i64_division_rejects_zero() -> None:
    with pytest.raises(NumericError, match="division by zero"):
        checked_i64_div(1, 0)


def test_checked_i64_to_tryte_is_bounded() -> None:
    assert checked_i64_to_tryte(-364) == -364
    assert checked_i64_to_tryte(364) == 364
    with pytest.raises(NumericError, match="tryte range"):
        checked_i64_to_tryte(365)


def test_f64_domain_preserves_ieee_special_values_and_signed_zero() -> None:
    assert math.isnan(validate_f64(float("nan")))
    assert validate_f64(float("inf")) == float("inf")
    assert validate_f64(float("-inf")) == float("-inf")
    negative_zero = validate_f64(-0.0)
    assert negative_zero == 0.0
    assert math.copysign(1.0, negative_zero) == -1.0


def test_numeric_value_exposes_required_f64_arithmetic() -> None:
    left = NumericValue.f64(6.0)
    right = NumericValue.f64(4.0)
    assert left.add(right).value == 10.0
    assert left.subtract(right).value == 2.0
    assert left.multiply(right).value == 24.0
    assert left.divide(right).value == 1.5
    assert left.negate().value == -6.0


def test_f64_division_preserves_ieee_zero_behavior() -> None:
    assert NumericValue.f64(1.0).divide(NumericValue.f64(0.0)).value == float("inf")
    assert NumericValue.f64(-1.0).divide(NumericValue.f64(0.0)).value == float("-inf")
    assert NumericValue.f64(1.0).divide(NumericValue.f64(-0.0)).value == float("-inf")
    assert math.isnan(NumericValue.f64(0.0).divide(NumericValue.f64(0.0)).value)
