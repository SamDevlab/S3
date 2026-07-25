from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def test_parse_match_expression_in_variable_declaration() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    val: tryte = match 0:\n"
        "        -1: 10\n"
        "        0: 20\n"
        "        1: 30\n"
        "    return val\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.VariableDeclaration)
    assert isinstance(stmt.initializer, ast.MatchExpression)
    match_expr = stmt.initializer
    assert isinstance(match_expr.selector, ast.IntegerLiteral)
    assert match_expr.selector.value == 0
    assert len(match_expr.cases) == 3
    assert match_expr.cases[0].label == -1
    assert match_expr.cases[1].label == 0
    assert match_expr.cases[2].label == 1


def test_parse_match_expression_in_return() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    return match 1 <=> 2:\n"
        "        -1: -100\n"
        "        0: 0\n"
        "        1: 100\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.ReturnStatement)
    assert isinstance(stmt.expression, ast.MatchExpression)


def test_parse_match_expression_nested() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    val: tryte = match 0:\n"
        "        -1: 1\n"
        "        0: match 1:\n"
        "            -1: 10\n"
        "            0: 20\n"
        "            1: 30\n"
        "        1: 2\n"
        "    return val\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.VariableDeclaration)
    assert isinstance(stmt.initializer, ast.MatchExpression)
    inner = stmt.initializer.cases[1].expression
    assert isinstance(inner, ast.MatchExpression)


def test_parse_match_statement_vs_expression_distinction() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    match 0:\n"
        "        -1:\n"
        "            return -1\n"
        "        0:\n"
        "            return 0\n"
        "        1:\n"
        "            return 1\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.SwitchStatement)
