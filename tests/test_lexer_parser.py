from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import LexError, ParseError
from bootstrap.s3.lexer import TokenKind, tokenize
from bootstrap.s3.parser import parse


SOURCE = """\
fn main() -> tryte {
    // Negative values are two tokens.
    tryte a = -10;
    return a <=> (~a + 1);
}
"""


def test_lexer_recognizes_tokens_and_tracks_locations() -> None:
    tokens = tokenize(SOURCE)
    kinds = [token.kind for token in tokens]
    assert kinds == [
        TokenKind.FN,
        TokenKind.IDENTIFIER,
        TokenKind.LEFT_PAREN,
        TokenKind.RIGHT_PAREN,
        TokenKind.ARROW,
        TokenKind.TRYTE,
        TokenKind.LEFT_BRACE,
        TokenKind.TRYTE,
        TokenKind.IDENTIFIER,
        TokenKind.EQUAL,
        TokenKind.MINUS,
        TokenKind.INTEGER,
        TokenKind.SEMICOLON,
        TokenKind.RETURN,
        TokenKind.IDENTIFIER,
        TokenKind.COMPARE,
        TokenKind.LEFT_PAREN,
        TokenKind.TILDE,
        TokenKind.IDENTIFIER,
        TokenKind.PLUS,
        TokenKind.INTEGER,
        TokenKind.RIGHT_PAREN,
        TokenKind.SEMICOLON,
        TokenKind.RIGHT_BRACE,
        TokenKind.EOF,
    ]
    minus = tokens[10]
    integer = tokens[11]
    assert (minus.text, integer.text) == ("-", "10")
    assert (minus.line, minus.column, minus.position) == (3, 15, 74)


def test_invalid_character_reports_location() -> None:
    with pytest.raises(LexError, match=r"2:5: lexical error.*invalid character"):
        tokenize("fn\n    @")


def test_parser_builds_typed_ast_and_operator_precedence() -> None:
    program = parse(SOURCE)
    function = program.functions[0]
    assert function.name == "main"
    assert function.return_type is ast.TypeName.TRYTE
    declaration = function.body.statements[0]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert isinstance(declaration.initializer, ast.UnaryExpression)
    assert declaration.initializer.operator is ast.UnaryOperator.NEGATE
    return_statement = function.body.statements[1]
    assert isinstance(return_statement, ast.ReturnStatement)
    assert isinstance(return_statement.expression, ast.BinaryExpression)
    assert return_statement.expression.operator is ast.BinaryOperator.COMPARE


def test_parser_rejects_missing_semicolon() -> None:
    with pytest.raises(ParseError, match="expected ';'"):
        parse("fn main() -> tryte { return 0 }")
