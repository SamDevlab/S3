"""Focused contracts for the bounded native policy search harness."""

from __future__ import annotations

import json

import pytest

from tools.native_policy_search import (
    MAX_CANDIDATES,
    _portfolio_features,
    _portfolio_report,
    build_corpus,
    run_search,
)


pytestmark = [pytest.mark.s3_fast, pytest.mark.s3_contract]


def test_corpus_has_disjoint_discovery_and_holdout_groups() -> None:
    corpus = build_corpus()
    discovery = {case.case_id for case in corpus if case.group == "discovery"}
    synthetic_holdout = {case.case_id for case in corpus if case.group == "holdout"}
    existing_holdout = {case.case_id for case in corpus if case.group == "holdout-existing"}

    assert discovery == {f"D{index:02d}" for index in range(1, 21)}
    assert synthetic_holdout == {f"H{index:02d}" for index in range(1, 7)}
    assert existing_holdout == {"E01", "E02", "E03"}
    assert not discovery & synthetic_holdout
    assert not discovery & existing_holdout


def test_portfolio_reads_main_function_features_not_helper_identity() -> None:
    case = next(case for case in build_corpus() if case.case_id == "D08")
    features = _portfolio_features(case)
    assert features["has_call"] is True
    assert features["number_of_calls"] == 1


def test_portfolio_leave_family_out_is_deterministic_and_generic() -> None:
    report = _portfolio_report(build_corpus())
    assert report["status"] == "RESEARCH_ONLY_NOT_PRODUCTION_INTEGRATED"
    assert report["forbidden_inputs"] == [
        "source_filename", "benchmark_name", "fixture_name", "semantic_identity",
    ]
    assert set(report["leave_family_out"]) == {
        "loops", "calls", "indexed_memory", "references",
    }
    assert all(
        item["selection_stable"]
        for item in report["leave_family_out"].values()
    )


def test_search_is_bounded_and_records_incomplete_external_holdout(tmp_path) -> None:
    result = run_search(tmp_path / "native-policy-search")
    assert result["total_candidates"] <= MAX_CANDIDATES
    assert result["baseline_policy_output_identical"] is True
    assert result["production_candidate"] == "NONE"
    assert result["production_policy_changed"] == "NO"
    assert result["global_holdout_pass"] == "INCOMPLETE_EXTERNAL_CORPUS"
    assert result["native_speedup_claim"] == "NO"

    final = json.loads((tmp_path / "native-policy-search" / "final.json").read_text())
    baseline_analysis = tmp_path / "native-policy-search" / "baseline-analysis.json"
    assert baseline_analysis.is_file()
    assert final["benchmark_reference"]["read_only"] is True
    assert final["benchmark_reference"]["p7_p8_p9_executed_against_experiment"] is False
