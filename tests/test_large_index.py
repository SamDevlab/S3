from __future__ import annotations

import pytest

from bootstrap.s3.large_index import LargeIndex, SliceBounds, validate_large_length
from bootstrap.s3.numeric import I64_MAX, NumericError


def test_large_index_accepts_i64_domain_values() -> None:
    assert LargeIndex(0).value == 0
    assert validate_large_length(I64_MAX) == I64_MAX


def test_large_index_rejects_negative_values_and_overflow() -> None:
    with pytest.raises(NumericError):
        LargeIndex(-1)
    with pytest.raises(NumericError):
        LargeIndex(I64_MAX + 1)


def test_large_index_has_explicit_bounds_and_checked_addition() -> None:
    index = LargeIndex(4)
    assert index.fits_length(LargeIndex(5))
    assert not index.fits_length(LargeIndex(4))
    assert index.checked_add(3) == LargeIndex(7)
    with pytest.raises(NumericError):
        LargeIndex(I64_MAX).checked_add(1)


def test_slice_bounds_are_half_open_and_use_large_index_domain() -> None:
    bounds = SliceBounds.from_values(2, 5)
    assert bounds.length == LargeIndex(3)
    assert bounds.contains(LargeIndex(2))
    assert bounds.contains(LargeIndex(4))
    assert not bounds.contains(LargeIndex(5))


def test_slice_bounds_reject_reverse_or_negative_ranges() -> None:
    with pytest.raises(NumericError, match="exceeds end"):
        SliceBounds.from_values(5, 2)
    with pytest.raises(NumericError):
        SliceBounds.from_values(-1, 2)
