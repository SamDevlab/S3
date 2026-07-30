from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def test_semantic_constant_simplification_addition() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    a: tryte = x + 0\n"
        "    b: tryte = 0 + x\n"
        "    return a + b\n"
    )
    model = analyze(program)
    stmt_a = program.functions[0].body.statements[1]
    stmt_b = program.functions[0].body.statements[2]
    assert isinstance(stmt_a, ast.VariableDeclaration)
    assert isinstance(stmt_b, ast.VariableDeclaration)
    assert model.simplified_expression_of(stmt_a.initializer) is not None
    assert model.simplified_expression_of(stmt_b.initializer) is not None


def test_semantic_constant_simplification_subtraction() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    a: tryte = x - 0\n"
        "    return a\n"
    )
    model = analyze(program)
    stmt_a = program.functions[0].body.statements[1]
    assert isinstance(stmt_a, ast.VariableDeclaration)
    assert model.simplified_expression_of(stmt_a.initializer) is not None


def test_semantic_constant_simplification_logical_identities() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 1\n"
        "    a: tryte = x + 0\n"
        "    b: tryte = x - 0\n"
        "    return 0\n"
    )
    model = analyze(program)
    stmt_a = program.functions[0].body.statements[1]
    stmt_b = program.functions[0].body.statements[2]
    assert isinstance(stmt_a, ast.VariableDeclaration)
    assert isinstance(stmt_b, ast.VariableDeclaration)
    assert model.simplified_expression_of(stmt_a.initializer) is not None
    assert model.simplified_expression_of(stmt_b.initializer) is not None


def test_semantic_constant_simplification_double_unary() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    a: tryte = -(-x)\n"
        "    return a\n"
    )
    model = analyze(program)
    stmt_a = program.functions[0].body.statements[1]
    assert isinstance(stmt_a, ast.VariableDeclaration)
    assert model.simplified_expression_of(stmt_a.initializer) is not None
