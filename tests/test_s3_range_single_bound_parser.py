from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def test_parse_single_bound_range() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(5):\n"
        "        total += i\n"
        "    return total\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    for_stmt = program.functions[0].body.statements[1]
    assert isinstance(for_stmt, ast.ForStatement)
    assert isinstance(for_stmt.start_expression, ast.IntegerLiteral)
    assert for_stmt.start_expression.value == 0
    assert isinstance(for_stmt.end_expression, ast.IntegerLiteral)
    assert for_stmt.end_expression.value == 5
