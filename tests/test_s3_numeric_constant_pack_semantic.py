from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze
from bootstrap.s3.ternary import TRIT_MAX, TRIT_MIN, TRYTE_MAX, TRYTE_MIN


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def _initializer(program: ast.Program, index: int) -> ast.Expression:
    declaration = program.functions[0].body.statements[index]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert not isinstance(declaration.initializer, ast.ArrayLiteral)
    return declaration.initializer


def test_tryte_constants_propagate_through_bindings_len_find_and_arithmetic() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    one: tryte = 1\n"
        "    two: tryte = one + one\n"
        '    size: tryte = len("hello")\n'
        '    position: tryte = find("hello", "ll")\n'
        "    last: tryte = size - one\n"
        "    result: tryte = position + two\n"
        "    return result + last\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == 1
    assert model.constant_value_of(_initializer(program, 1)) == 2
    assert model.constant_value_of(_initializer(program, 2)) == 5
    assert model.constant_value_of(_initializer(program, 3)) == 2
    assert model.constant_value_of(_initializer(program, 4)) == 4
    assert model.constant_value_of(_initializer(program, 5)) == 4


def test_trit_constants_propagate_through_queries_equality_and_bindings() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    found: trit = contains("hello", "ell")\n'
        "    same: trit = found == -1\n"
        "    copy: trit = same\n"
        "    neutral: trit = 0\n"
        "    positive: trit = 1\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == -1
    assert model.constant_value_of(_initializer(program, 1)) == -1
    assert model.constant_value_of(_initializer(program, 2)) == -1
    assert model.constant_value_of(_initializer(program, 3)) == 0
    assert model.constant_value_of(_initializer(program, 4)) == 1


def test_numeric_constant_comparisons_are_recorded() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    equal: trit = 2 == 2\n"
        "    different: trit = 2 != 3\n"
        "    less: trit = 2 < 3\n"
        "    less_equal: trit = 2 <= 2\n"
        "    greater: trit = 3 > 2\n"
        "    greater_equal: trit = 3 >= 3\n"
        "    order: trit = 2 <=> 5\n"
        "    return 0\n"
    )
    model = analyze(program)

    assert [model.constant_value_of(_initializer(program, index)) for index in range(7)] == [
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
    ]


def test_constant_text_index_and_slice_accept_tryte_expressions() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    position: tryte = find("hello", "ll")\n'
        "    letter: string = \"hello\"[position]\n"
        "    start: tryte = 1\n"
        "    end: tryte = start + 3\n"
        "    part: string = \"hello\"[start:end]\n"
        "    size: tryte = len(\"hello\")\n"
        "    last: tryte = size - 1\n"
        "    final: string = \"hello\"[last]\n"
        "    return len(part) + len(letter) + len(final)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 1)) == "l"
    assert model.static_text_of(_initializer(program, 4)) == "ell"
    assert model.static_text_of(_initializer(program, 7)) == "o"


def test_shadowed_scalar_constants_use_the_resolved_binding() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        "    index: tryte = 1\n"
        "    match 0:\n"
        "        -1:\n"
        "            return 0\n"
        "        0:\n"
        "            index: tryte = 2\n"
        "            letter: string = \"abc\"[index]\n"
        "            return len(letter)\n"
        "        1:\n"
        "            letter: string = \"abc\"[index]\n"
        "            return len(letter)\n"
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            '    mut index: tryte = 1\n'
            '    letter: string = "abc"[index]\n',
            "static text index must be a tryte expression known at compile time",
        ),
        (
            "fn first(index: tryte) -> string:\n"
            '    return "abc"[index]\n'
            "fn main() -> tryte:\n"
            "    return 0\n",
            "static text index must be a tryte expression known at compile time",
        ),
        (
            '    found: tryte = find("abc", "x")\n'
            '    letter: string = "abc"[found]\n',
            "static text index must be non-negative",
        ),
        (
            "    index: trit = 1\n"
            '    letter: string = "abc"[index]\n',
            "variable 'index' has type trit; expected tryte",
        ),
        (
            f"    value: tryte = {TRYTE_MAX} + 1\n",
            f"tryte overflow: {TRYTE_MAX} + 1",
        ),
        (
            f"    value: trit = {TRIT_MAX} + 1\n",
            f"trit overflow: {TRIT_MAX} + 1",
        ),
    ],
)
def test_scalar_constant_diagnostics(source: str, message: str) -> None:
    full_source = (
        source
        if source.startswith("fn ")
        else "fn main() -> tryte:\n" + source + "    return 0\n"
    )
    with pytest.raises(SemanticError) as captured:
        _analyze(full_source)
    assert message in str(captured.value)


def test_future_references_remain_invalid() -> None:
    with pytest.raises(SemanticError, match="undeclared variable 'later'"):
        _analyze(
            "fn main() -> tryte:\n"
            "    value: tryte = later\n"
            "    later: tryte = 1\n"
            "    return value\n"
        )


def test_boundary_constants_are_valid() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        f"    low: tryte = {TRYTE_MIN}\n"
        f"    high: tryte = {TRYTE_MAX}\n"
        f"    neg: trit = {TRIT_MIN}\n"
        f"    pos: trit = {TRIT_MAX}\n"
        "    return low + high\n"
    )
