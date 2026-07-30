from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze
from bootstrap.s3.ternary import TRIT_MAX, TRYTE_MAX


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def _initializer(program: ast.Program, index: int) -> ast.Expression:
    declaration = program.functions[0].body.statements[index]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert not isinstance(declaration.initializer, ast.ArrayLiteral)
    return declaration.initializer


def test_semantic_constant_arithmetic_simple() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    a: tryte = 10 + 5\n"
        "    b: tryte = 10 - 5\n"
        "    c: tryte = -10\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == 15
    assert model.constant_value_of(_initializer(program, 1)) == 5
    assert model.constant_value_of(_initializer(program, 2)) == -10


def test_semantic_constant_arithmetic_compound() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    a: tryte = (10 + 5) - (2 + 3)\n"
        "    b: tryte = -(-10 + 5)\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == 10
    assert model.constant_value_of(_initializer(program, 1)) == 5


def test_semantic_constant_arithmetic_mixed_with_comparisons() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    a: trit = (10 > 5) + (10 == 5)\n"
        "    b: trit = (10 == 10) - (5 == 5)\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == 0


def test_semantic_partially_constant_arithmetic_not_folded() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    a: tryte = x + 10\n"
        "    b: tryte = -x\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 1)) is None
    assert model.constant_value_of(_initializer(program, 2)) is None


def test_semantic_constant_arithmetic_overflow_error() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        f"    a: tryte = {TRYTE_MAX} + 1\n"
        "    return 0\n"
    )
    with pytest.raises(SemanticError, match=r"tryte overflow"):
        analyze(program)


def test_semantic_trit_arithmetic_overflow_error() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        f"    a: trit = {TRIT_MAX} + 1\n"
        "    return 0\n"
    )
    with pytest.raises(SemanticError, match=r"trit overflow"):
        analyze(program)
