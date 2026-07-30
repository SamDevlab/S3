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


def _initializer(program: ast.Program, index: int) -> ast.Expression:
    declaration = program.functions[0].body.statements[index]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert not isinstance(declaration.initializer, ast.ArrayLiteral)
    return declaration.initializer


def test_semantic_constant_propagation_numeric_chain() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    a: tryte = 5\n"
        "    b: tryte = a\n"
        "    c: tryte = b + 3\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == 5
    assert model.constant_value_of(_initializer(program, 1)) == 5
    assert model.constant_value_of(_initializer(program, 2)) == 8


def test_semantic_constant_propagation_string_chain() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    s: string = "abc"\n'
        "    t: string = s\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 0)) == "abc"
    assert model.static_text_of(_initializer(program, 1)) == "abc"


def test_semantic_constant_propagation_mutable_does_not_propagate() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    mut a: tryte = 5\n"
        "    b: tryte = a\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 1)) is None


def test_semantic_constant_propagation_scopes() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    a: tryte = 10\n"
        "    match 0:\n"
        "        0:\n"
        "            b: tryte = a + 5\n"
        "        else:\n"
        "            discard 0\n"
        "    c: tryte = a + 1\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == 10
    assert model.constant_value_of(_initializer(program, 2)) == 11
