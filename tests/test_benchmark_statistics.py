from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

import tools.benchmark as benchmark
from tools.benchmark_statistics import (
    TimingStatistics,
    calc_max,
    calc_mean,
    calc_median,
    calc_min,
    calc_p95,
    calc_stats,
    summarize_samples,
)


@pytest.mark.parametrize(
    "function",
    (calc_min, calc_max, calc_mean, calc_median, calc_p95, calc_stats),
)
def test_empty_collections_keep_the_legacy_value_error(function) -> None:
    with pytest.raises(ValueError, match="Empty collection"):
        function([])


@pytest.mark.parametrize(
    ("samples", "expected_minimum", "expected_maximum", "expected_mean", "expected_median"),
    (
        ([42], 42, 42, 42.0, 42.0),
        ([3, 1, 5], 1, 5, 3.0, 3.0),
        ([7, 1, 5, 3], 1, 7, 4.0, 4.0),
        ([4, 4, 4], 4, 4, 4.0, 4.0),
        ([10**12 + 2, 10**12], 10**12, 10**12 + 2, 10**12 + 1.0, 10**12 + 1.0),
    ),
)
def test_basic_statistics_cover_min_max_mean_and_median(
    samples,
    expected_minimum,
    expected_maximum,
    expected_mean,
    expected_median,
) -> None:
    assert calc_min(samples) == expected_minimum
    assert calc_max(samples) == expected_maximum
    assert calc_mean(samples) == expected_mean
    assert calc_median(samples) == expected_median


@pytest.mark.parametrize(
    ("sample_count", "samples"),
    (
        (1, (11,)),
        (2, (22, 11)),
        (10, tuple(range(10, 0, -1))),
        (20, tuple(range(20, 0, -1))),
        (100, tuple(range(100, 0, -1))),
    ),
)
def test_calc_p95_uses_nearest_rank_for_multiple_collection_sizes(
    sample_count,
    samples,
) -> None:
    ordered = sorted(samples)
    expected_index = math.ceil(0.95 * sample_count) - 1
    assert calc_p95(samples) == ordered[expected_index]


def test_calc_stats_preserves_the_legacy_shape_and_values() -> None:
    samples = [9, 1, 4, 4]

    assert calc_stats(samples) == {
        "minimum": 1,
        "maximum": 9,
        "mean": 4.5,
        "median": 4.0,
        "p95": 9,
    }
    assert samples == [9, 1, 4, 4]


def test_legacy_stat_symbols_remain_available_through_tools_benchmark() -> None:
    samples = [8, 2, 2, 10]

    assert benchmark.calc_min(samples) == 2
    assert benchmark.calc_max(samples) == 10
    assert benchmark.calc_mean(samples) == 5.5
    assert benchmark.calc_median(samples) == 5.0
    assert benchmark.calc_p95(samples) == 10
    assert benchmark.calc_stats(samples) == {
        "minimum": 2,
        "maximum": 10,
        "mean": 5.5,
        "median": 5.0,
        "p95": 10,
    }


def test_summarize_samples_returns_immutable_timing_statistics() -> None:
    samples = [10, 30, 20, 100, 40]
    original = samples.copy()

    summary = summarize_samples(samples)

    assert isinstance(summary, TimingStatistics)
    assert summary == TimingStatistics(
        sample_count=5,
        unit="ns",
        minimum=10,
        maximum=100,
        mean=40.0,
        median=30.0,
        p95=100,
    )
    assert summary.sample_count == 5
    assert summary.unit == "ns"
    assert summary.minimum == 10
    assert summary.maximum == 100
    assert summary.mean == 40.0
    assert summary.median == 30.0
    assert summary.p95 == 100
    assert samples == original

    with pytest.raises(FrozenInstanceError):
        summary.sample_count = 99


def test_summarize_samples_accepts_tuple_inputs() -> None:
    summary = summarize_samples((3, 1, 2))

    assert isinstance(summary, TimingStatistics)
    assert summary == TimingStatistics(
        sample_count=3,
        unit="ns",
        minimum=1,
        maximum=3,
        mean=2.0,
        median=2.0,
        p95=3,
    )


@pytest.mark.parametrize(
    ("samples", "expected_exception", "message"),
    (
        ([], ValueError, "timing samples must not be empty"),
        ([-1], ValueError, "timing sample 1 must be non-negative"),
        ([1.0], TypeError, "timing sample 1 must be an integer, got float"),
        ([True], TypeError, "timing sample 1 must be an integer, got bool"),
    ),
)
def test_summarize_samples_rejects_invalid_inputs(
    samples,
    expected_exception,
    message,
) -> None:
    with pytest.raises(expected_exception, match=message):
        summarize_samples(samples)
