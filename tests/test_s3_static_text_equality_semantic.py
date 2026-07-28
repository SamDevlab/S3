from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def test_static_text_equality_result_has_trit_type() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    same: trit = "abc" == "abc"\n'
        "    return 0\n"
    )
    model = analyze(program)
    declaration = program.functions[0].body.statements[0]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert isinstance(declaration.initializer, ast.BinaryExpression)
    assert model.type_of(declaration.initializer) is ast.TypeName.TRIT


@pytest.mark.parametrize(
    "expression",
    [
        '"" == ""',
        '"abc" == "abc"',
        '"abc" != "xyz"',
        '"a" + "b" == "ab"',
        '("a" + "b") != ("a" + "c")',
        r'"\n" == "\n"',
        '"é" == "é"',
    ],
)
def test_static_text_equality_accepts_compile_time_text(expression: str) -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        f"    same: trit = {expression}\n"
        "    return 0\n"
    )
    assert model is not None


def test_static_text_equality_can_be_used_in_match() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        '    match "a" + "b" == "ab":\n'
        "        -1:\n"
        "            return 1\n"
        "        0:\n"
        "            return 0\n"
        "        1:\n"
        "            return -1\n"
    )
    assert model is not None


@pytest.mark.parametrize(
    "expression",
    [
        'value == "abc"',
        '"abc" == value',
    ],
)
def test_static_text_equality_rejects_bindings(expression: str) -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn main() -> tryte:\n"
            '    value: string = "abc"\n'
            f"    same: trit = {expression}\n"
            "    return 0\n"
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )
    assert (
        captured.value.message
        == "string equality requires compile-time static text expressions"
    )


def test_static_text_equality_rejects_string_call() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn identity(value: string) -> string:\n"
            "    return value\n"
            "fn main() -> tryte:\n"
            '    same: trit = identity("abc") == "abc"\n'
            "    return 0\n"
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )
    assert (
        captured.value.message
        == "string equality requires compile-time static text expressions"
    )


@pytest.mark.parametrize("expression", ['"abc" == 1', '1 == "abc"'])
def test_static_text_equality_rejects_mixed_types(expression: str) -> None:
    with pytest.raises(SemanticError, match="comparison operands"):
        _analyze(
            "fn main() -> tryte:\n"
            f"    same: trit = {expression}\n"
            "    return 0\n"
        )


def test_static_text_equality_rejects_string_ordering() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn main() -> tryte:\n"
            '    ordered: trit = "a" < "b"\n'
            "    return 0\n"
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )
    assert captured.value.message == "operator '<' is not supported for string values"


def test_numeric_equality_is_preserved() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    same: trit = 1 == 1\n"
        "    return 0\n"
    )
    assert model is not None
