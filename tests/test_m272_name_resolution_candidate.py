"""M2.72 bounded lexical/module name-resolution candidate contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.name_resolution_candidate import (
    NameResolutionCandidateError,
    candidate_name_resolution,
    reference_name_resolution,
    run_name_resolution_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/semantic/name_resolution_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn resolve_visible_symbol" in SELFHOST_SOURCE
    assert "tryte[8]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_root_scope_lookup_matches_exactly() -> None:
    evidence = run_name_resolution_differential(
        [(11, 1, 0), (22, 2, 0)],
        [-1],
        22,
        0,
    )
    assert evidence.reference_result == 18
    assert evidence.candidate_result == 18
    assert evidence.match is True


def test_nearest_shadowing_declaration_wins() -> None:
    entries = [(11, 1, 0), (11, 2, 1), (22, 3, 0)]
    parents = [-1, 0, 1]
    evidence = run_name_resolution_differential(entries, parents, 11, 2)
    assert evidence.reference_result == 18
    assert evidence.candidate_result == 18
    assert evidence.match is True


def test_root_declaration_is_visible_from_nested_scope() -> None:
    entries = [(11, 1, 0), (22, 2, 1)]
    parents = [-1, 0, 1]
    assert reference_name_resolution(entries, parents, 11, 2) == 9
    assert candidate_name_resolution(entries, parents, 11, 2) == 9


def test_sibling_declaration_is_not_visible() -> None:
    entries = [(11, 1, 1)]
    parents = [-1, 0, 0]
    evidence = run_name_resolution_differential(entries, parents, 11, 2)
    assert evidence.reference_result == 0
    assert evidence.candidate_result == 0
    assert evidence.match is True


def test_missing_symbol_returns_zero() -> None:
    entries = [(11, 1, 0)]
    parents = [-1, 0]
    assert reference_name_resolution(entries, parents, 99, 1) == 0
    assert candidate_name_resolution(entries, parents, 99, 1) == 0


def test_duplicate_symbol_in_same_scope_fails_closed() -> None:
    entries = [(11, 1, 0), (11, 2, 0)]
    with pytest.raises(NameResolutionCandidateError, match="duplicate"):
        reference_name_resolution(entries, [-1], 11, 0)
    with pytest.raises(NameResolutionCandidateError, match="duplicate"):
        candidate_name_resolution(entries, [-1], 11, 0)


def test_same_symbol_in_parent_and_child_is_valid_shadowing() -> None:
    entries = [(11, 1, 0), (11, 4, 1)]
    parents = [-1, 0]
    assert reference_name_resolution(entries, parents, 11, 1) == 20
    assert candidate_name_resolution(entries, parents, 11, 1) == 20


def test_malformed_scope_parent_fails_closed_before_execution() -> None:
    with pytest.raises(NameResolutionCandidateError, match="earlier scope"):
        candidate_name_resolution([(11, 1, 0)], [-1, 1], 11, 1)


def test_declaration_scope_outside_tree_fails_closed() -> None:
    with pytest.raises(NameResolutionCandidateError, match="declaration scope"):
        candidate_name_resolution([(11, 1, 2)], [-1, 0], 11, 1)


def test_scope_and_symbol_bounds_are_enforced() -> None:
    with pytest.raises(NameResolutionCandidateError, match="scope bound"):
        candidate_name_resolution([], [-1, 0, 1, 2, 3, 4, 5, 6, 7], 11, 0)
    entries = [(index, 1, 0) for index in range(9)]
    with pytest.raises(NameResolutionCandidateError, match="symbol bound"):
        candidate_name_resolution(entries, [-1], 0, 0)
