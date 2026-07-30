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


def test_semantic_tryte_equality_and_inequality() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    e1: trit = 10 == 10\n"
        "    e2: trit = 10 == 5\n"
        "    ne1: trit = 10 != 5\n"
        "    ne2: trit = 10 != 10\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == 0
    assert model.constant_value_of(_initializer(program, 2)) == -1
    assert model.constant_value_of(_initializer(program, 3)) == 0


def test_semantic_tryte_relational() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    gt: trit = 10 > 5\n"
        "    lt: trit = 10 < 5\n"
        "    le: trit = 5 <= 5\n"
        "    ge: trit = 10 >= 10\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == 0
    assert model.constant_value_of(_initializer(program, 2)) == -1
    assert model.constant_value_of(_initializer(program, 3)) == -1


def test_semantic_trit_equality_and_relational() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    e: trit = -1 == -1\n"
        "    ne: trit = -1 != 1\n"
        "    lt: trit = -1 < 0\n"
        "    gt: trit = 1 > 0\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == -1
    assert model.constant_value_of(_initializer(program, 2)) == -1
    assert model.constant_value_of(_initializer(program, 3)) == -1


def test_semantic_string_equality_and_inequality() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    e1: trit = "abc" == "abc"\n'
        '    e2: trit = "abc" == "xyz"\n'
        '    ne1: trit = "abc" != "xyz"\n'
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == 0
    assert model.constant_value_of(_initializer(program, 2)) == -1


def test_semantic_string_relational() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    lt: trit = "abc" < "def"\n'
        '    gt: trit = "def" > "abc"\n'
        '    le: trit = "abc" <= "abc"\n'
        '    ge: trit = "abc" >= "def"\n'
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == -1
    assert model.constant_value_of(_initializer(program, 2)) == -1
    assert model.constant_value_of(_initializer(program, 3)) == 0


def test_semantic_comparison_with_variable_not_constant() -> None:
    program = _parse(
        "fn check(x: tryte) -> trit:\n"
        "    return x > 2\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )
    model = analyze(program)
    return_stmt = program.functions[0].body.statements[0]
    assert isinstance(return_stmt, ast.ReturnStatement)
    assert model.constant_value_of(return_stmt.expression) is None


def test_semantic_comparison_partially_constant() -> None:
    program = _parse(
        "fn check(x: tryte) -> trit:\n"
        "    return 10 > x\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )
    model = analyze(program)
    return_stmt = program.functions[0].body.statements[0]
    assert isinstance(return_stmt, ast.ReturnStatement)
    assert model.constant_value_of(return_stmt.expression) is None


def test_semantic_incompatible_types_string_and_tryte_comparison_raises() -> None:
    with pytest.raises(SemanticError) as exc_info:
        _analyze(
            "fn main() -> tryte:\n"
            '    res: trit = 10 > "abc"\n'
            "    return 0\n"
        )
    assert "has type" in str(exc_info.value)


def test_semantic_incompatible_types_tryte_and_trit_comparison_raises() -> None:
    with pytest.raises(SemanticError) as exc_info:
        _analyze(
            "fn main() -> tryte:\n"
            "    t: trit = -1\n"
            "    y: tryte = 10\n"
            "    res: trit = y > t\n"
            "    return 0\n"
        )
    assert "has type" in str(exc_info.value)


def test_semantic_constant_bindings_comparison() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    a: tryte = 10\n"
        "    b: tryte = 5\n"
        "    cmp_num: trit = a > b\n"
        '    s: string = "abc"\n'
        '    cmp_str: trit = s == "abc"\n'
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 2)) == -1
    assert model.constant_value_of(_initializer(program, 4)) == -1
