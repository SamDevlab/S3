from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def _initializer(source: str) -> ast.Expression:
    program = parse(source, mode=SyntaxMode.V0_6)
    declaration = program.functions[0].body.statements[0]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert not isinstance(declaration.initializer, ast.ArrayLiteral)
    return declaration.initializer


def test_parser_builds_static_text_slice_expression() -> None:
    expression = _initializer(
        "fn main() -> tryte:\n"
        '    part: string = "hello"[1:4]\n'
        "    return 0\n"
    )

    assert isinstance(expression, ast.SliceExpression)
    assert isinstance(expression.target, ast.StringLiteral)
    assert isinstance(expression.start, ast.IntegerLiteral)
    assert expression.start.value == 1
    assert isinstance(expression.end, ast.IntegerLiteral)
    assert expression.end.value == 4


def test_parser_preserves_slice_precedence() -> None:
    concat = _initializer(
        "fn main() -> tryte:\n"
        '    value: string = "x" + "hello"[1:4]\n'
        "    return 0\n"
    )
    assert isinstance(concat, ast.BinaryExpression)
    assert isinstance(concat.right, ast.SliceExpression)

    program = parse(
        "fn main() -> trit:\n"
        '    return "hello"[1:4] == "ell"\n',
        mode=SyntaxMode.V0_6,
    )
    returned = program.functions[0].body.statements[0]
    assert isinstance(returned, ast.ReturnStatement)
    assert isinstance(returned.expression, ast.BinaryExpression)
    assert isinstance(returned.expression.left, ast.SliceExpression)


def test_parser_builds_static_text_query_calls() -> None:
    for name in ("contains", "starts_with", "ends_with", "find"):
        expression = _initializer(
            "fn main() -> tryte:\n"
            f'    result: tryte = {name}("hello", "ll")\n'
            "    return 0\n"
        )
        assert isinstance(expression, ast.CallExpression)
        assert expression.function_name == name
        assert len(expression.arguments) == 2


@pytest.mark.parametrize(
    "source,message",
    [
        ('    part: string = "hello"[:4]\n', "expected expression"),
        ('    part: string = "hello"[1:]\n', "expected expression"),
        ('    part: string = "hello"[1:4:1]\n', "expected ']' after slice"),
    ],
)
def test_parser_rejects_unsupported_slice_shapes(
    source: str,
    message: str,
) -> None:
    with pytest.raises(ParseError, match=message):
        parse("fn main() -> tryte:\n" + source + "    return 0\n", mode=SyntaxMode.V0_6)
