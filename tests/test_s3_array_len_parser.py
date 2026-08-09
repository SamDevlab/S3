from __future__ import annotations

import pytest

pytestmark = pytest.mark.s3_fast

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def test_parse_len_expression_in_variable_declaration() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
        "    size: tryte = len(values)\n"
        "    return size\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[1]
    assert isinstance(stmt, ast.VariableDeclaration)
    assert isinstance(stmt.initializer, ast.LenExpression)
    assert isinstance(stmt.initializer.argument, ast.Identifier)
    assert stmt.initializer.argument.name == "values"


def test_parse_len_expression_in_for_range() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(0, len(values)):\n"
        "        total = total + values[i]\n"
        "    return total\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[2]
    assert isinstance(stmt, ast.ForStatement)
    assert isinstance(stmt.end_expression, ast.LenExpression)


def test_parse_len_expression_missing_paren_raises() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
        "    size: tryte = len values\n"
        "    return size\n"
    )
    with pytest.raises(ParseError, match="expected '\\(' after 'len'"):
        parse(source, mode=SyntaxMode.V0_6)
