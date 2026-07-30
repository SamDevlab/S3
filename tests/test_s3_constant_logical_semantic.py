from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import SemanticError
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


def test_semantic_logical_and_folding() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    t_and_t: tryte = -1 & -1\n"
        "    t_and_f: tryte = -1 & 0\n"
        "    f_and_f: tryte = 0 & 0\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == -1
    assert model.constant_value_of(_initializer(program, 2)) == 0


def test_semantic_logical_or_folding() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    t_or_f: tryte = -1 | 0\n"
        "    f_or_f: tryte = 0 | 0\n"
        "    t_or_t: tryte = -1 | -1\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == 0
    assert model.constant_value_of(_initializer(program, 1)) == 0
    assert model.constant_value_of(_initializer(program, 2)) == -1


def test_semantic_logical_not_folding() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    not_t: tryte = ~(-1)\n"
        "    not_f: tryte = ~0\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == 1
    assert model.constant_value_of(_initializer(program, 1)) == 0


def test_semantic_logical_compound_expressions() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    c1: trit = (10 == 10) & (5 < 10)\n"
        "    c2: trit = ~(10 == 10)\n"
        "    c3: tryte = (-1 & 0) | (~(-1))\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == 1
    assert model.constant_value_of(_initializer(program, 2)) == 1


def test_semantic_partially_constant_logical_expressions_not_folded() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 1\n"
        "    p1: tryte = x & -1\n"
        "    p2: tryte = x | 0\n"
        "    p3: tryte = ~x\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 1)) is None
    assert model.constant_value_of(_initializer(program, 2)) is None
    assert model.constant_value_of(_initializer(program, 3)) is None


def test_semantic_logical_incompatible_types_string_error() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    s: string = "hello"\n'
        "    res: string = ~s\n"
        "    return 0\n"
    )
    with pytest.raises(
        SemanticError,
        match=r"operator '~' is not supported for string values",
    ):
        analyze(program)


def test_semantic_logical_binary_string_error() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    s: string = "hello"\n'
        "    res: string = s & \"world\"\n"
        "    return 0\n"
    )
    with pytest.raises(
        SemanticError,
        match=r"operator '&' is not supported for string values",
    ):
        analyze(program)
