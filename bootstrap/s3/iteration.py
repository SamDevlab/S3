"""Closed deterministic iteration primitives for M1.63."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .numeric import I64_MAX, I64_MIN, validate_i64


@dataclass(frozen=True, slots=True)
class I64Range:
    """A half-open checked i64 range with an explicit non-zero step."""

    start: int
    end: int
    step: int = 1

    def __post_init__(self) -> None:
        validate_i64(self.start)
        validate_i64(self.end)
        validate_i64(self.step)
        if self.step == 0:
            raise ValueError("range step cannot be zero")

    def __iter__(self) -> Iterator[int]:
        current = self.start
        if self.step > 0:
            while current < self.end:
                yield current
                if current > I64_MAX - self.step:
                    raise OverflowError("i64 range step overflows")
                current += self.step
        else:
            while current > self.end:
                yield current
                if current < I64_MIN - self.step:
                    raise OverflowError("i64 range step overflows")
                current += self.step


def deterministic_range(start: int, end: int, step: int = 1) -> I64Range:
    """Construct a checked half-open range without materializing values."""

    return I64Range(start, end, step)
