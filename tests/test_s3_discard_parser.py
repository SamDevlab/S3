from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def test_parse_discard_statement() -> None:
    source = (
        "fn helper(x: tryte) -> tryte:\n"
        "    return x + 1\n"
        "fn main() -> tryte:\n"
        "    discard helper(10)\n"
        "    return 0\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    main_fn = program.functions[1]
    stmt = main_fn.body.statements[0]
    assert isinstance(stmt, ast.DiscardStatement)
    assert isinstance(stmt.expression, ast.CallExpression)
    assert stmt.expression.function_name == "helper"
