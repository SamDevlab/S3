"""Tests for match statement and match expression fallback parsing in S3 0.52."""

import pytest

from bootstrap.s3.ast import MatchExpression, SwitchStatement
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def test_parse_match_statement_one_case_and_fallback():
    program = parse("""
fn main() -> tryte:
    match 0:
        0:
            return 10
        else:
            return 20
""")
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, SwitchStatement)
    assert len(stmt.cases) == 2
    assert stmt.cases[0].label == 0
    assert stmt.cases[1].label is None


def test_parse_match_statement_two_cases_and_fallback():
    program = parse("""
fn main() -> tryte:
    match 0:
        -1:
            return -10
        1:
            return 10
        else:
            return 0
""")
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, SwitchStatement)
    assert len(stmt.cases) == 3
    assert stmt.cases[0].label == -1
    assert stmt.cases[1].label == 1
    assert stmt.cases[2].label is None


def test_parse_match_expression_one_case_and_fallback():
    program = parse("""
fn main() -> tryte:
    x: tryte = match 0:
        1: 100
        else: 200
    return x
""")
    decl = program.functions[0].body.statements[0]
    expr = decl.initializer
    assert isinstance(expr, MatchExpression)
    assert len(expr.cases) == 2
    assert expr.cases[0].label == 1
    assert expr.cases[1].label is None


def test_parse_match_expression_two_cases_and_fallback():
    program = parse("""
fn main() -> tryte:
    x: tryte = match 0:
        -1: -1
        0: 0
        else: 1
    return x
""")
    decl = program.functions[0].body.statements[0]
    expr = decl.initializer
    assert isinstance(expr, MatchExpression)
    assert len(expr.cases) == 3
    assert expr.cases[0].label == -1
    assert expr.cases[1].label == 0
    assert expr.cases[2].label is None


def test_parse_match_fallback_invalid_arm_order():
    # fallback before explicit arm in statement
    with pytest.raises(ParseError):
        parse("""
fn main() -> tryte:
    match 0:
        else:
            return 0
        1:
            return 1
""")


def test_parse_match_v0_5_compatibility_preserved():
    program = parse("""
fn main() -> tryte {
    switch (0) {
        -1: { return -1; }
        0: { return 0; }
        1: { return 1; }
    }
}
""", mode=SyntaxMode.V0_5)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, SwitchStatement)
    assert len(stmt.cases) == 3
