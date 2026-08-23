"""M2.71 bounded self-hosted symbol table contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.symbol_table_candidate import (
    SymbolTableCandidateError,
    candidate_symbol_lookup,
    reference_symbol_lookup,
    run_symbol_table_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/semantic/symbol_table_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn symbol_table_lookup" in SELFHOST_SOURCE
    assert "tryte[8]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (11, 9),
        (22, 18),
        (33, 27),
        (99, 0),
    ],
)
def test_candidate_matches_reference_lookup(query: int, expected: int) -> None:
    entries = [(11, 1), (22, 2), (33, 3)]
    evidence = run_symbol_table_differential(entries, query)
    assert evidence.reference_result == expected
    assert evidence.candidate_result == expected
    assert evidence.match is True


def test_insertion_order_is_semantically_visible_in_slot_encoding() -> None:
    first = [(11, 1), (22, 2)]
    second = [(22, 2), (11, 1)]
    assert reference_symbol_lookup(first, 11) == 9
    assert reference_symbol_lookup(second, 11) == 17
    assert candidate_symbol_lookup(first, 11) == 9
    assert candidate_symbol_lookup(second, 11) == 17


def test_empty_table_returns_missing_without_error() -> None:
    assert reference_symbol_lookup([], 7) == 0
    assert candidate_symbol_lookup([], 7) == 0


def test_duplicate_symbol_ids_fail_closed_in_both_paths() -> None:
    entries = [(11, 1), (11, 2)]
    with pytest.raises(SymbolTableCandidateError, match="duplicate"):
        reference_symbol_lookup(entries, 11)
    with pytest.raises(SymbolTableCandidateError, match="rejected"):
        candidate_symbol_lookup(entries, 11)


def test_invalid_symbol_kind_fails_closed_in_both_paths() -> None:
    entries = [(11, 5)]
    with pytest.raises(SymbolTableCandidateError, match="kind range"):
        reference_symbol_lookup(entries, 11)
    with pytest.raises(SymbolTableCandidateError, match="rejected"):
        candidate_symbol_lookup(entries, 11)


def test_symbol_bound_is_enforced_before_execution() -> None:
    entries = [(index, 1) for index in range(9)]
    with pytest.raises(SymbolTableCandidateError, match="symbol bound"):
        candidate_symbol_lookup(entries, 0)
