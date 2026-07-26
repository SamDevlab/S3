from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def test_parse_compound_assignment_scalar() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    x += 5\n"
        "    return x\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmts = program.functions[0].body.statements
    assert isinstance(stmts[1], ast.CompoundAssignmentStatement)
    assert stmts[1].operator == ast.BinaryOperator.ADD


def test_parse_compound_assignment_indexed() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut arr: tryte[3] = [1, 2, 3]\n"
        "    arr[0] += 10\n"
        "    return arr[0]\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    stmts = program.functions[0].body.statements
    assert isinstance(stmts[1], ast.CompoundAssignmentStatement)
    assert isinstance(stmts[1].target, ast.IndexTarget)
    assert stmts[1].operator == ast.BinaryOperator.ADD
