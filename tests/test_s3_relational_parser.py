from __future__ import annotations

import pytest

pytestmark = pytest.mark.s3_fast

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def test_parse_relational_equal() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        "    mut x: trit = 1 == 2\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.VariableDeclaration)
    assert isinstance(stmt.initializer, ast.BinaryExpression)
    assert stmt.initializer.operator is ast.BinaryOperator.EQUAL


def test_parse_relational_not_equal() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        "    mut x: trit = 1 != 2\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.VariableDeclaration)
    assert isinstance(stmt.initializer, ast.BinaryExpression)
    assert stmt.initializer.operator is ast.BinaryOperator.NOT_EQUAL


def test_parse_relational_less_and_less_equal() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        "    mut a: trit = 1 < 2\n"
        "    mut b: trit = 1 <= 2\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    stmts = program.functions[0].body.statements
    assert isinstance(stmts[0].initializer, ast.BinaryExpression)
    assert stmts[0].initializer.operator is ast.BinaryOperator.LESS
    assert isinstance(stmts[1].initializer, ast.BinaryExpression)
    assert stmts[1].initializer.operator is ast.BinaryOperator.LESS_EQUAL


def test_parse_relational_greater_and_greater_equal() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        "    mut a: trit = 2 > 1\n"
        "    mut b: trit = 2 >= 1\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    stmts = program.functions[0].body.statements
    assert isinstance(stmts[0].initializer, ast.BinaryExpression)
    assert stmts[0].initializer.operator is ast.BinaryOperator.GREATER
    assert isinstance(stmts[1].initializer, ast.BinaryExpression)
    assert stmts[1].initializer.operator is ast.BinaryOperator.GREATER_EQUAL


def test_parse_relational_precedence_over_compare() -> None:
    # 1 <=> 2 < 3 => (1 <=> 2) < 3
    program = parse(
        "fn main() -> tryte:\n"
        "    mut res: trit = 1 <=> 2 < 3\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    stmt = program.functions[0].body.statements[0]
    expr = stmt.initializer
    assert isinstance(expr, ast.BinaryExpression)
    assert expr.operator is ast.BinaryOperator.LESS
    assert isinstance(expr.left, ast.BinaryExpression)
    assert expr.left.operator is ast.BinaryOperator.COMPARE
