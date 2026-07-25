from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode, tokenize, TokenKind
from bootstrap.s3.parser import parse


def _get_while(program: ast.Program, index: int = 0) -> ast.WhileStatement:
    stmts = program.functions[0].body.statements
    while_stmts = [s for s in stmts if isinstance(s, ast.WhileStatement)]
    return while_stmts[index]


def _parse_simple(source: str) -> ast.WhileStatement:
    return _get_while(parse(source, mode=SyntaxMode.V0_6))


def test_while_is_keyword() -> None:
    tokens = tokenize("while 1:\n    return 0\n", mode=SyntaxMode.V0_6)
    kinds = [t.kind for t in tokens]
    assert TokenKind.WHILE in kinds


def test_while_value_is_identifier() -> None:
    tokens = tokenize("mut while_value: tryte = 0\n", mode=SyntaxMode.V0_6)
    kinds = [t.kind for t in tokens]
    assert TokenKind.WHILE not in kinds
    assert TokenKind.IDENTIFIER in kinds


def test_parser_creates_while_statement() -> None:
    stmt = _parse_simple("fn main() -> tryte:\n    while 1:\n        return 0\n")
    assert isinstance(stmt, ast.WhileStatement)


def test_condition_is_preserved() -> None:
    stmt = _parse_simple("fn main() -> tryte:\n    while 0:\n        return 0\n")
    assert isinstance(stmt.condition, ast.IntegerLiteral)
    assert stmt.condition.value == 0


def test_condition_ternary_expression() -> None:
    stmt = _parse_simple("fn main() -> tryte:\n    while 0 <=> 1:\n        return 0\n")
    assert isinstance(stmt.condition, ast.BinaryExpression)
    assert stmt.condition.operator is ast.BinaryOperator.COMPARE


def test_body_is_preserved() -> None:
    stmt = _parse_simple("fn main() -> tryte:\n    while 0 <=> 1:\n        return 42\n")
    ret = stmt.body.statements[0]
    assert isinstance(ret, ast.ReturnStatement)
    assert isinstance(ret.expression, ast.IntegerLiteral)
    assert ret.expression.value == 42


def test_body_multiple_statements() -> None:
    stmt = _parse_simple(
        "fn main() -> tryte:\n"
        "    while 0 <=> 1:\n"
        "        mut x: tryte = 1\n"
        "        return x\n"
    )
    assert len(stmt.body.statements) == 2


def test_missing_colon_rejected() -> None:
    with pytest.raises(ParseError, match="expected ':'"):
        parse("fn main() -> tryte:\n    while 1\n        return 0\n", mode=SyntaxMode.V0_6)


def test_missing_indent_rejected() -> None:
    with pytest.raises(ParseError, match="expected indented block"):
        parse("fn main() -> tryte:\n    while 1:\nreturn 0\n", mode=SyntaxMode.V0_6)


def test_nested_while() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 0\n"
        "    while x <=> 3:\n"
        "        mut y: tryte = 0\n"
        "        while y <=> 2:\n"
        "            y = y + 1\n"
        "        x = x + 1\n"
        "    return x\n",
        mode=SyntaxMode.V0_6,
    )
    outer = _get_while(program, 0)
    inner = outer.body.statements[1]
    assert isinstance(inner, ast.WhileStatement)
    assert isinstance(inner.condition, ast.BinaryExpression)
    assert inner.condition.operator is ast.BinaryOperator.COMPARE


def test_match_inside_while() -> None:
    stmt = _parse_simple(
        "fn main() -> tryte:\n"
        "    while -1:\n"
        "        match -1:\n"
        "            -1:\n"
        "                return 10\n"
        "            0:\n"
        "                return 20\n"
        "            1:\n"
        "                return 30\n"
    )
    body = stmt.body
    match_stmt = body.statements[0]
    assert isinstance(match_stmt, ast.SwitchStatement)
