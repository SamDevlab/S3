from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def test_parse_for_statement_valid() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 0\n"
        "    for i: tryte in range(0, 10):\n"
        "        sum = sum + i\n"
        "    return sum\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[1]
    assert isinstance(stmt, ast.ForStatement)
    assert stmt.variable_name == "i"
    assert stmt.variable_type == ast.TypeName.TRYTE
    assert isinstance(stmt.start_expression, ast.IntegerLiteral)
    assert stmt.start_expression.value == 0
    assert isinstance(stmt.end_expression, ast.IntegerLiteral)
    assert stmt.end_expression.value == 10
    assert len(stmt.body.statements) == 1


def test_parse_for_statement_with_break_continue() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    for i: tryte in range(0, 10):\n"
        "        while i == 5:\n"
        "            continue\n"
        "        break\n"
        "    return 0\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.ForStatement)


def test_parse_for_statement_missing_in_raises() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    for i: tryte range(0, 10):\n"
        "        sum = sum + i\n"
        "    return 0\n"
    )
    with pytest.raises(ParseError, match="expected 'in'"):
        parse(source, mode=SyntaxMode.V0_6)
