from __future__ import annotations

import pytest

from tools.benchmark_native_kernel_scope import (
    classify_paired_speedup,
    expected_result,
    summarize,
)


def test_kernel_reference_checksum_is_deterministic() -> None:
    assert expected_result(1) == 18.078125
    assert expected_result(1_000) == 18_078.125


def test_timing_summary_records_median_cv_and_p95() -> None:
    summary = summarize([10, 20, 30, 40, 50])
    assert summary["sample_count"] == 5
    assert summary["median_ns"] == 30
    assert summary["p95_ns"] == 50
    assert summary["coefficient_of_variation"] > 0


def test_paired_comparison_does_not_promote_indistinguishable_samples() -> None:
    result = classify_paired_speedup([100] * 21, [100] * 21)
    assert result["classification"] == "NEUTRAL"
    assert result["paired_bootstrap_95_percent_interval"] == [1.0, 1.0]


def test_paired_comparison_marks_clear_regression() -> None:
    result = classify_paired_speedup([80] * 21, [100] * 21)
    assert result["classification"] == "REGRESSION"


def test_paired_comparison_requires_complete_pairs() -> None:
    with pytest.raises(ValueError, match="same length"):
        classify_paired_speedup([100, 110, 120], [100, 110])
