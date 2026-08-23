"""M2.63 bounded canonical AST candidate differential contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.ast_candidate import (
    ASTCandidateError,
    candidate_ast_fingerprint,
    reference_ast_fingerprint,
    run_ast_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/frontend/ast_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn canonical_ast_fingerprint" in SELFHOST_SOURCE
    assert "tryte[64]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    "source",
    [
        "fn main() -> tryte:\n    return 7\n",
        "fn value() -> f64:\n    return 12.5\n",
        'fn text() -> tryte:\n    return "hello"\n',
    ],
)
def test_candidate_matches_canonical_python_ast(source: str) -> None:
    evidence = run_ast_differential(source)
    assert evidence.reference_fingerprint == reference_ast_fingerprint(source)
    assert evidence.candidate_fingerprint == candidate_ast_fingerprint(source)
    assert evidence.match is True


def test_canonical_ast_ignores_layout_but_preserves_value() -> None:
    compact = "fn main() -> tryte:\n    return 7\n"
    wider_indent = "fn main() -> tryte:\n        return 7\n"
    changed = "fn main() -> tryte:\n    return 8\n"
    assert reference_ast_fingerprint(compact) == reference_ast_fingerprint(wider_indent)
    assert reference_ast_fingerprint(compact) != reference_ast_fingerprint(changed)
    assert candidate_ast_fingerprint(compact) == candidate_ast_fingerprint(wider_indent)


def test_candidate_rejects_expression_outside_bounded_ast_shape() -> None:
    source = "fn main() -> tryte:\n    return 7 + 1\n"
    with pytest.raises(ASTCandidateError, match="bounded grammar"):
        candidate_ast_fingerprint(source)
