"""M2.62 bounded S3 parser candidate differential contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.parser_candidate import (
    ParserCandidateError,
    candidate_parser_fingerprint,
    reference_parser_fingerprint,
    run_parser_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/frontend/parser_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn parser_fingerprint" in SELFHOST_SOURCE
    assert "tryte[64]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    "source",
    [
        "fn main() -> tryte:\n    return 7\n",
        "fn entry() -> trit:\n    return 0\n",
        "fn value() -> f64:\n    return 12.5\n",
    ],
)
def test_candidate_matches_python_parser_reference(source: str) -> None:
    evidence = run_parser_differential(source)
    assert evidence.reference_fingerprint == reference_parser_fingerprint(source)
    assert evidence.candidate_fingerprint == candidate_parser_fingerprint(source)
    assert evidence.match is True


def test_candidate_rejects_valid_but_out_of_subset_expression() -> None:
    source = "fn main() -> tryte:\n    return 7 + 1\n"
    assert reference_parser_fingerprint(source) >= 0
    with pytest.raises(ParserCandidateError, match="bounded grammar"):
        candidate_parser_fingerprint(source)


def test_candidate_rejects_token_stream_above_bound() -> None:
    source = "fn f() -> tryte:\n    return 7\n" * 6
    with pytest.raises(ParserCandidateError, match="token bound"):
        candidate_parser_fingerprint(source)
