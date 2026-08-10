"""Checked large scalar indices and lengths for the numeric M1.32 domain."""

from __future__ import annotations

from dataclasses import dataclass

from .numeric import I64_MAX, NumericError, validate_i64


@dataclass(frozen=True, slots=True)
class LargeIndex:
    """A non-negative i64 index or collection length."""

    value: int

    def __post_init__(self) -> None:
        value = validate_i64(self.value)
        if value < 0:
            raise NumericError(f"large index must be non-negative, got {value}")
        object.__setattr__(self, "value", value)

    @classmethod
    def zero(cls) -> LargeIndex:
        return cls(0)

    def checked_add(self, amount: int) -> LargeIndex:
        return LargeIndex(self.value + validate_i64(amount))

    def fits_length(self, length: LargeIndex) -> bool:
        return self.value < length.value


@dataclass(frozen=True, slots=True)
class SliceBounds:
    """A checked half-open range over the large index domain."""

    start: LargeIndex
    end: LargeIndex

    def __post_init__(self) -> None:
        if self.start.value > self.end.value:
            raise NumericError(
                f"slice start {self.start.value} exceeds end {self.end.value}"
            )

    @classmethod
    def from_values(cls, start: int, end: int) -> SliceBounds:
        return cls(LargeIndex(start), LargeIndex(end))

    @property
    def length(self) -> LargeIndex:
        return LargeIndex(self.end.value - self.start.value)

    def contains(self, index: LargeIndex) -> bool:
        return self.start.value <= index.value < self.end.value


def validate_large_length(value: int) -> int:
    """Validate a non-negative i64 collection length."""

    return LargeIndex(value).value


MAX_LARGE_LENGTH = I64_MAX
