"""Semantic analysis tests for match statement and match expression fallback in S3 0.52."""

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def test_semantic_match_totality_by_fallback():
    program = parse("""
fn main() -> tryte:
    match 0:
        1:
            return 10
        else:
            return 20
""")
    model = analyze(program)
    assert model is not None


def test_semantic_match_expression_totality_by_fallback():
    program = parse("""
fn main() -> tryte:
    x: tryte = match 0:
        -1: -10
        else: 100
    return x
""")
    model = analyze(program)
    assert model is not None


def test_semantic_match_expression_type_mismatch():
    program = parse("""
fn main() -> tryte:
    x: trit = match 0:
        0: 1
        else: 200
    return x
""")
    with pytest.raises(SemanticError, match="literal 200 is outside trit range"):
        analyze(program)


def test_semantic_match_expression_partial_without_fallback():
    program = parse("""
fn main() -> tryte:
    x: tryte = match 0:
        0: 10
        1: 20
    return x
""")
    with pytest.raises(SemanticError, match="match expression is missing case\\(s\\): -1"):
        analyze(program)


def test_semantic_match_redundant_fallback():
    program = parse("""
fn main() -> tryte:
    match 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
        else:
            return 99
""")
    with pytest.raises(SemanticError, match="redundant fallback arm in match statement"):
        analyze(program)


def test_semantic_match_duplicate_cases():
    program = parse("""
fn main() -> tryte:
    match 0:
        0:
            return 0
        0:
            return 1
        else:
            return 2
""")
    with pytest.raises(SemanticError, match="duplicate ternary case 0"):
        analyze(program)
