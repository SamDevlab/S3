"""Focused V2.4 corpus and frozen-canary contracts."""

from __future__ import annotations

from tools.native_policy_search_v24 import (
    MODES,
    _new_cases,
    _rule_hash,
    build_v24_corpus,
)
from bootstrap.s3.backends.x86_64.experimental_policy import resolve_experimental_policies
from bootstrap.s3.backends.x86_64.features import extract_function_features


def test_v24_corpus_has_distinct_high_information_cases() -> None:
    cases = _new_cases()
    assert len(cases) == 12
    assert len({case.case_id for case in cases}) == len(cases)
    assert all(case.source for case in cases)


def test_v24_corpus_extends_historical_corpus_without_replacing_it() -> None:
    cases = build_v24_corpus()
    assert len(cases) == 103
    assert {case.case_id for case in _new_cases()} <= {case.case_id for case in cases}


def test_v24_rule_hash_is_stable_and_modes_are_explicit() -> None:
    assert len(_rule_hash()) == 64
    assert MODES == ("off", "shadow", "compact-ea-canary")


def test_v24_positive_and_negative_selection_is_fail_closed() -> None:
    cases = {case.case_id: case for case in _new_cases()}
    positive = resolve_experimental_policies(cases["V24-01"].program, "compact-ea-canary")["main"]
    call_negative = resolve_experimental_policies(cases["V24-04"].program, "compact-ea-canary")["main"]
    reference_negative = resolve_experimental_policies(cases["V24-09"].program, "compact-ea-canary")["main"]
    assert positive.applied is True
    assert call_negative.applied is False
    assert reference_negative.applied is False


def test_v24_sites_are_counted_separately_from_function_decisions() -> None:
    cases = _new_cases()
    functions = [next(function for function in case.program.functions if function.name == "main") for case in cases]
    site_count = sum(extract_function_features(function).indexed_memory_ops for function in functions)
    function_count = sum(bool(extract_function_features(function).indexed_memory_ops) for function in functions)
    assert site_count > function_count
    assert site_count >= 12
