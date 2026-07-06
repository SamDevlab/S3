"""Pure statistical helpers shared by S3 benchmark surfaces."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


def calc_stats(samples: Sequence[int]) -> dict[str, int | float]:
    if not samples:
        raise ValueError("Empty collection")
    return {
        "minimum": calc_min(samples),
        "maximum": calc_max(samples),
        "mean": calc_mean(samples),
        "median": calc_median(samples),
        "p95": calc_p95(samples),
    }


def calc_min(samples: Sequence[int]) -> int:
    if not samples:
        raise ValueError("Empty collection")
    return min(samples)


def calc_max(samples: Sequence[int]) -> int:
    if not samples:
        raise ValueError("Empty collection")
    return max(samples)


def calc_mean(samples: Sequence[int]) -> float:
    if not samples:
        raise ValueError("Empty collection")
    mean_val = sum(samples) / len(samples)
    if math.isnan(mean_val) or math.isinf(mean_val):
        raise ValueError("Invalid mean")
    return mean_val


def calc_median(samples: Sequence[int]) -> float:
    if not samples:
        raise ValueError("Empty collection")
    ordered = sorted(samples)
    sample_count = len(ordered)
    midpoint = sample_count // 2
    if sample_count % 2 == 0:
        return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0
    return float(ordered[midpoint])


def calc_p95(samples: Sequence[int]) -> int:
    if not samples:
        raise ValueError("Empty collection")
    ordered = sorted(samples)
    rank = math.ceil(0.95 * len(ordered))
    return ordered[rank - 1]


@dataclass(frozen=True, slots=True)
class TimingStatistics:
    """Aggregate statistics for validated timing samples."""

    sample_count: int
    unit: str
    minimum: int
    maximum: int
    mean: float
    median: float
    p95: int


def summarize_samples(samples: Sequence[int]) -> TimingStatistics:
    """Validate and summarize non-negative integer nanosecond samples."""
    validated_samples = tuple(samples)
    if not validated_samples:
        raise ValueError("timing samples must not be empty")
    for index, sample in enumerate(validated_samples, start=1):
        if isinstance(sample, bool) or not isinstance(sample, int):
            raise TypeError(
                f"timing sample {index} must be an integer, "
                f"got {type(sample).__name__}"
            )
        if sample < 0:
            raise ValueError(f"timing sample {index} must be non-negative")

    return TimingStatistics(
        sample_count=len(validated_samples),
        unit="ns",
        minimum=calc_min(validated_samples),
        maximum=calc_max(validated_samples),
        mean=calc_mean(validated_samples),
        median=calc_median(validated_samples),
        p95=calc_p95(validated_samples),
    )
