from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import DiagnosticCode, LexError, ParseError
from bootstrap.s3.lexer import SyntaxMode, TokenKind, tokenize
from bootstrap.s3.parser import parse


SOURCE = """\
fn main() -> tryte {
    // Negative values are two tokens.
    tryte a = -10;
    return a <=> (~a + 1);
}
"""


def test_lexer_recognizes_tokens_and_tracks_locations() -> None:
    tokens = tokenize(SOURCE, mode=SyntaxMode.V0_5)
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
        tokenize("fn\n    @", mode=SyntaxMode.V0_5)


def test_lexer_recognizes_string_literal_as_reserved_token() -> None:
    tokens = tokenize(
        'fn main() -> tryte:\n    return "hello"\n',
        mode=SyntaxMode.V0_6,
    )

    string_token = next(
        token for token in tokens if token.kind is TokenKind.STRING_LITERAL
    )
    assert string_token.text == '"hello"'
    assert (string_token.line, string_token.column) == (2, 12)


def test_parser_preserves_string_literal_as_front_end_node() -> None:
    program = parse(
        'fn main() -> tryte:\n    return "hello"\n',
        mode=SyntaxMode.V0_6,
    )

    statement = program.functions[0].body.statements[0]
    assert isinstance(statement, ast.ReturnStatement)
    assert isinstance(statement.expression, ast.StringLiteral)
    assert statement.expression.value == "hello"
    assert (statement.expression.location.line, statement.expression.location.column) == (
        2,
        12,
    )


def test_unterminated_string_literal_reports_lexical_error() -> None:
    with pytest.raises(LexError) as captured:
        tokenize(
            'fn main() -> tryte:\n    return "hello\n',
            mode=SyntaxMode.V0_6,
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.LEX_UNTERMINATED_STRING_LITERAL
    )
    assert "unterminated string literal" in captured.value.message


def test_parser_builds_typed_ast_and_operator_precedence() -> None:
    program = parse(SOURCE, mode=SyntaxMode.V0_5)
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
        parse(
            "fn main() -> tryte { return 0 }",
            mode=SyntaxMode.V0_5,
        )
