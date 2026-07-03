from __future__ import annotations

import pytest

from bootstrap.s3.ternary import (
    TRYTE_MAX,
    TRYTE_MIN,
    TernaryRangeError,
    add_tryte,
    compare_tryte,
    decimal_to_trits,
    invert_trit,
    invert_tryte,
    max_trit,
    max_tryte,
    min_trit,
    min_tryte,
    trits_to_decimal,
    validate_trit,
    validate_tryte,
)


TRITS = range(-1, 2)
TRYTES = range(TRYTE_MIN, TRYTE_MAX + 1)


def test_trit_inversion_is_exhaustive_and_involutive() -> None:
    assert [invert_trit(value) for value in TRITS] == [1, 0, -1]
    assert all(invert_trit(invert_trit(value)) == value for value in TRITS)


def test_tryte_conversion_round_trips_exhaustively() -> None:
    for value in TRYTES:
        digits = decimal_to_trits(value)
        assert len(digits) == 6
        assert all(digit in TRITS for digit in digits)
        assert trits_to_decimal(digits) == value


def test_tryte_additive_and_inversion_laws_exhaustively() -> None:
    for value in TRYTES:
        assert add_tryte(value, 0) == value
        assert add_tryte(value, invert_tryte(value)) == 0
        assert invert_tryte(invert_tryte(value)) == value


def test_comparison_laws_exhaustively() -> None:
    for left in TRYTES:
        assert compare_tryte(left, left) == 0
        for right in TRYTES:
            assert compare_tryte(left, right) == invert_trit(
                compare_tryte(right, left)
            )


def test_tritwise_min_and_max_are_commutative_for_all_trits() -> None:
    for left in TRITS:
        for right in TRITS:
            assert min_trit(left, right) == min_trit(right, left)
            assert max_trit(left, right) == max_trit(right, left)


def test_tryte_min_and_max_are_commutative_on_boundary_matrix() -> None:
    representatives = (
        TRYTE_MIN,
        -243,
        -10,
        -1,
        0,
        1,
        10,
        243,
        TRYTE_MAX,
    )
    for left in representatives:
        for right in TRYTES:
            assert min_tryte(left, right) == min_tryte(right, left)
            assert max_tryte(left, right) == max_tryte(right, left)


@pytest.mark.parametrize("value", (-2, 2))
def test_invalid_trit_is_rejected(value: int) -> None:
    with pytest.raises(TernaryRangeError, match="trit value"):
        validate_trit(value)


@pytest.mark.parametrize("value", (TRYTE_MIN - 1, TRYTE_MAX + 1))
def test_invalid_tryte_is_rejected(value: int) -> None:
    with pytest.raises(TernaryRangeError, match="tryte value"):
        validate_tryte(value)


def test_tryte_overflow_is_detected() -> None:
    with pytest.raises(TernaryRangeError, match="overflow"):
        add_tryte(TRYTE_MAX, 1)

