from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def _analyze(source: str):
    return analyze(parse(source, mode=SyntaxMode.V0_6))


def test_match_expression_semantic_valid_tryte() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    mut sel: trit = 0\n"
        "    val: tryte = match sel:\n"
        "        -1: 10\n"
        "        0: 20\n"
        "        1: 30\n"
        "    return val\n"
    )
    assert model is not None


def test_match_expression_semantic_valid_trit() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    mut sel: trit = 0\n"
        "    val: trit = match sel:\n"
        "        -1: -1\n"
        "        0: 0\n"
        "        1: 1\n"
        "    return 0\n"
    )
    assert model is not None


def test_match_expression_selector_must_be_trit() -> None:
    with pytest.raises(SemanticError, match="has type tryte; expected trit"):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut sel: tryte = 0\n"
            "    val: tryte = match sel:\n"
            "        -1: 10\n"
            "        0: 20\n"
            "        1: 30\n"
            "    return val\n"
        )


def test_match_expression_mismatched_arm_types_rejected() -> None:
    with pytest.raises(SemanticError, match="has type trit; expected tryte"):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut sel: trit = 0\n"
            "    mut b: trit = 1\n"
            "    val: tryte = match sel:\n"
            "        -1: 10\n"
            "        0: b\n"
            "        1: 30\n"
            "    return val\n"
        )


def test_match_expression_non_exhaustive_rejected() -> None:
    with pytest.raises(SemanticError, match="match expression arms must exhaustively cover"):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut sel: trit = 0\n"
            "    val: tryte = match sel:\n"
            "        -1: 10\n"
            "        0: 20\n"
            "        0: 30\n"
            "    return val\n"
        )


def test_match_expression_static_validation_in_all_arms() -> None:
    with pytest.raises(SemanticError, match="undeclared variable 'unknown'"):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut sel: trit = 0\n"
            "    val: tryte = match sel:\n"
            "        -1: 10\n"
            "        0: 20\n"
            "        1: unknown\n"
            "    return val\n"
        )
