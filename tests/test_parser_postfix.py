from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


def _return_expression(expression: str) -> ast.Expression:
    program = parse(
        f"fn main() -> tryte:\n    return {expression}\n",
        mode=SyntaxMode.V0_6,
    )
    statement = program.functions[0].body.statements[0]
    assert isinstance(statement, ast.ReturnStatement)
    return statement.expression


def _first_statement(source: str) -> ast.Statement:
    program = parse(source, mode=SyntaxMode.V0_6)
    return program.functions[0].body.statements[0]


def _identifier(expression: ast.Expression, name: str) -> None:
    assert isinstance(expression, ast.Identifier)
    assert expression.name == name


def _field(expression: ast.Expression, name: str) -> ast.FieldAccessExpression:
    assert isinstance(expression, ast.FieldAccessExpression)
    assert expression.field_name == name
    return expression


def _call(expression: ast.Expression) -> ast.CallExpression:
    assert isinstance(expression, ast.CallExpression)
    return expression


def _index(expression: ast.Expression) -> ast.IndexExpression:
    assert isinstance(expression, ast.IndexExpression)
    return expression


def test_postfix_basic_forms() -> None:
    call = _call(_return_expression("f()"))
    _identifier(call.callee, "f")
    assert call.function_name == "f"
    assert call.arguments == ()

    call = _call(_return_expression("f(a, b)"))
    _identifier(call.callee, "f")
    assert [argument.expression.name for argument in call.arguments if isinstance(argument.expression, ast.Identifier)] == [
        "a",
        "b",
    ]

    index = _index(_return_expression("a[0]"))
    _identifier(index.target, "a")
    assert isinstance(index.index, ast.IntegerLiteral)
    assert index.index.value == 0

    field = _field(_return_expression("a.b"), "b")
    _identifier(field.target, "a")

    parenthesized = _field(_return_expression("(a).b"), "b")
    _identifier(parenthesized.target, "a")


@pytest.mark.parametrize(
    "source",
    [
        "f().value",
        "pkg.function()",
        "values[0].field",
        "object.values[0]",
        "factory()[0]",
        "functions[0]()",
        "pkg.Enum.Variant",
        "pkg.factory(values[0]).result",
        "consume(pkg.make().value)",
        "(a).b",
    ],
)
def test_postfix_compositions_parse(source: str) -> None:
    _return_expression(source)


def test_call_over_member_has_member_callee() -> None:
    call = _call(_return_expression("pkg.function()"))
    field = _field(call.callee, "function")
    _identifier(field.target, "pkg")


def test_call_over_index_has_index_callee() -> None:
    call = _call(_return_expression("functions[0]()"))
    index = _index(call.callee)
    _identifier(index.target, "functions")


def test_nested_qualified_member_chain_is_left_associative() -> None:
    expression = _field(_return_expression("pkg.Enum.Variant"), "Variant")
    middle = _field(expression.target, "Enum")
    _identifier(middle.target, "pkg")


def test_mixed_postfix_chain_is_left_associative() -> None:
    expression = _index(_return_expression("a[0].b(c)[1]"))
    assert isinstance(expression.index, ast.IntegerLiteral)
    call = _call(expression.target)
    field = _field(call.callee, "b")
    index = _index(field.target)
    _identifier(index.target, "a")
    _identifier(call.arguments[0].expression, "c")


def test_call_after_member_chain_is_left_associative() -> None:
    call = _call(_return_expression("a.b.c()"))
    field = _field(call.callee, "c")
    parent = _field(field.target, "b")
    _identifier(parent.target, "a")


def test_postfix_binds_tighter_than_binary_and_unary() -> None:
    binary = _return_expression("a.b + c")
    assert isinstance(binary, ast.BinaryExpression)
    assert binary.operator is ast.BinaryOperator.ADD
    _field(binary.left, "b")
    _identifier(binary.right, "c")

    field_binary = _return_expression("f(x).field + y")
    assert isinstance(field_binary, ast.BinaryExpression)
    _field(field_binary.left, "field")
    _identifier(field_binary.right, "y")

    equality = _return_expression("a[0] == b.field")
    assert isinstance(equality, ast.BinaryExpression)
    assert equality.operator is ast.BinaryOperator.EQUAL
    _index(equality.left)
    _field(equality.right, "field")

    unary = _return_expression("-a.b")
    assert isinstance(unary, ast.UnaryExpression)
    assert unary.operator is ast.UnaryOperator.NEGATE
    _field(unary.operand, "b")

    parenthesized = _return_expression("(a + b).field")
    field = _field(parenthesized, "field")
    assert isinstance(field.target, ast.BinaryExpression)


def test_postfix_in_return_condition_and_parenthesized_contexts() -> None:
    returned = _first_statement(
        "fn main() -> tryte:\n"
        "    return pkg.make().value\n"
    )
    assert isinstance(returned, ast.ReturnStatement)
    _field(returned.expression, "value")

    statement = _first_statement(
        "fn main() -> tryte:\n"
        "    while object.ready:\n"
        "        return object.value\n"
    )
    assert isinstance(statement, ast.WhileStatement)
    _field(statement.condition, "ready")

    expression = _return_expression("(factory())[0]")
    index = _index(expression)
    assert isinstance(index.target, ast.CallExpression)


def test_postfix_locations_use_chain_start() -> None:
    expression = _field(_return_expression("alpha.beta.gamma"), "gamma")
    assert expression.location.line == 2
    assert expression.location.column == 12
    parent = _field(expression.target, "beta")
    assert parent.location.line == 2
    assert parent.location.column == 12

    call = _call(_return_expression("pkg.function()"))
    assert call.location.line == 2
    assert call.location.column == 12

    index = _index(_return_expression("pkg.values[0]"))
    assert index.location.line == 2
    assert index.location.column == 12


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("a.", "expected member name after '.'"),
        ("a..b", "expected member name after '.'"),
        (".a", "expected expression"),
        ("a.(b)", "expected member name after '.'"),
        ("a.0", "expected member name after '.'"),
        ("a.[0]", "expected member name after '.'"),
        ("f(1", "expected ')' after arguments"),
        ("a[0", "expected ']' after index"),
        ("f(a,)", "expected argument after ','"),
    ],
)
def test_invalid_postfix_suffixes_are_parse_errors(
    expression: str,
    message: str,
) -> None:
    with pytest.raises(ParseError) as error:
        _return_expression(expression)
    assert message in str(error.value)
