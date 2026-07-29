from __future__ import annotations

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def _initializer(source: str) -> ast.Expression:
    program = parse(source, mode=SyntaxMode.V0_6)
    declaration = program.functions[0].body.statements[0]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert not isinstance(declaration.initializer, ast.ArrayLiteral)
    return declaration.initializer


def test_parser_builds_literal_static_text_index_expression() -> None:
    expression = _initializer(
        "fn main() -> tryte:\n"
        '    letter: string = "abc"[0]\n'
        "    return 0\n"
    )

    assert isinstance(expression, ast.IndexExpression)
    assert isinstance(expression.target, ast.StringLiteral)
    assert isinstance(expression.index, ast.IntegerLiteral)
    assert expression.index.value == 0


def test_parser_builds_binding_static_text_index_expression() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        '    message: string = "abc"\n'
        "    letter: string = message[1]\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    declaration = program.functions[0].body.statements[1]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert isinstance(declaration.initializer, ast.IndexExpression)
    assert isinstance(declaration.initializer.target, ast.Identifier)
    assert declaration.initializer.array_name == "message"


def test_parser_indexes_grouped_concatenation() -> None:
    expression = _initializer(
        "fn main() -> tryte:\n"
        '    letter: string = ("a" + "b")[1]\n'
        "    return 0\n"
    )

    assert isinstance(expression, ast.IndexExpression)
    assert isinstance(expression.target, ast.BinaryExpression)


def test_parser_preserves_indexing_precedence_for_concat_and_equality() -> None:
    concat = _initializer(
        "fn main() -> tryte:\n"
        '    value: string = "a" + "b"[0]\n'
        "    return 0\n"
    )
    assert isinstance(concat, ast.BinaryExpression)
    assert isinstance(concat.right, ast.IndexExpression)

    program = parse(
        "fn main() -> trit:\n"
        '    return "abc"[1] == "b"\n',
        mode=SyntaxMode.V0_6,
    )
    returned = program.functions[0].body.statements[0]
    assert isinstance(returned, ast.ReturnStatement)
    assert isinstance(returned.expression, ast.BinaryExpression)
    assert isinstance(returned.expression.left, ast.IndexExpression)


def test_parser_allows_indexing_inside_len() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        '    return len("abc"[1])\n',
        mode=SyntaxMode.V0_6,
    )
    returned = program.functions[0].body.statements[0]
    assert isinstance(returned, ast.ReturnStatement)
    assert isinstance(returned.expression, ast.LenExpression)
    assert isinstance(returned.expression.argument, ast.IndexExpression)
