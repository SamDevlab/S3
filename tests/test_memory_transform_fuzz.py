from __future__ import annotations

from tools.s3_memory_transform_fuzz import SEEDS, run_corpus


def test_seeded_memory_transform_fuzz_and_independent_write_reordering() -> None:
    result = run_corpus()

    assert result["cases_expected"] == len(SEEDS) * 2
    assert result["cases_completed"] == result["cases_expected"]
    assert result["paired_metamorphic_cases"] == len(SEEDS)
    assert result["failures"] == []
    assert result["passed"] is True
