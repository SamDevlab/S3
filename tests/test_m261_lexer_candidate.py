"""M2.61 bounded S3 lexer candidate differential contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.lexer import TokenKind, SyntaxMode, tokenize
from bootstrap.s3.lexer_candidate import (
    LexerCandidateError,
    candidate_fingerprint,
    reference_fingerprint,
    run_lexer_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/frontend/lexer_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn lexer_fingerprint" in SELFHOST_SOURCE
    assert "tryte[96]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    "source",
    [
        "alpha + 3",
        "fn main() -> tryte { return 7; }",
        "value = 12.5 // comment\n",
        "mut value = (1 <= 2);",
    ],
)
def test_candidate_matches_python_reference(source: str) -> None:
    evidence = run_lexer_differential(source)
    assert evidence.reference_fingerprint == reference_fingerprint(source)
    assert evidence.candidate_fingerprint == candidate_fingerprint(source)
    assert evidence.match is True


def test_reference_fingerprint_is_token_order_sensitive() -> None:
    first = reference_fingerprint("alpha + 3")
    second = reference_fingerprint("3 + alpha")
    assert first != second
    assert tokenize("alpha + 3", mode=SyntaxMode.V0_5)[0].kind is TokenKind.IDENTIFIER


def test_candidate_rejects_non_ascii_and_oversized_input() -> None:
    with pytest.raises(LexerCandidateError, match="ASCII"):
        candidate_fingerprint("ação")
    with pytest.raises(LexerCandidateError, match="bounded"):
        candidate_fingerprint("a" * 97)
