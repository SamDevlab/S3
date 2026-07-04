"""Lexer for the initial S3 language subset."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .diagnostics import LexError, SourceLocation


class TokenKind(Enum):
    FN = auto()
    RETURN = auto()
    SWITCH = auto()
    MUT = auto()
    TRIT = auto()
    TRYTE = auto()
    IDENTIFIER = auto()
    INTEGER = auto()
    ARROW = auto()
    COMPARE = auto()
    TILDE = auto()
    AMPERSAND = auto()
    PIPE = auto()
    PLUS = auto()
    MINUS = auto()
    EQUAL = auto()
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    COLON = auto()
    SEMICOLON = auto()
    COMMA = auto()
    EOF = auto()


KEYWORDS = {
    "fn": TokenKind.FN,
    "return": TokenKind.RETURN,
    "switch": TokenKind.SWITCH,
    "mut": TokenKind.MUT,
    "trit": TokenKind.TRIT,
    "tryte": TokenKind.TRYTE,
}


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    column: int
    position: int

    @property
    def location(self) -> SourceLocation:
        return SourceLocation(self.position, self.line, self.column)

    def to_dict(self) -> dict[str, str | int]:
        return {
            "type": self.kind.name,
            "text": self.text,
            "line": self.line,
            "column": self.column,
            "position": self.position,
        }


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.line = 1
        self.column = 1

    def tokenize(self) -> tuple[Token, ...]:
        tokens: list[Token] = []
        while not self._at_end:
            char = self._peek()
            if char in " \t\r\n":
                self._skip_whitespace()
                continue
            if char == "/" and self._peek(1) == "/":
                self._skip_comment()
                continue
            if self._is_identifier_start(char):
                tokens.append(self._identifier())
                continue
            if char.isdigit():
                tokens.append(self._integer())
                continue
            tokens.append(self._operator_or_punctuation())
        tokens.append(Token(TokenKind.EOF, "", self.line, self.column, self.position))
        return tuple(tokens)

    @property
    def _at_end(self) -> bool:
        return self.position >= len(self.source)

    def _peek(self, distance: int = 0) -> str:
        index = self.position + distance
        return "\0" if index >= len(self.source) else self.source[index]

    def _advance(self) -> str:
        char = self.source[self.position]
        self.position += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _skip_whitespace(self) -> None:
        while not self._at_end and self._peek() in " \t\r\n":
            self._advance()

    def _skip_comment(self) -> None:
        self._advance()
        self._advance()
        while not self._at_end and self._peek() != "\n":
            self._advance()

    def _identifier(self) -> Token:
        start = self.position
        line = self.line
        column = self.column
        while self._is_identifier_continue(self._peek()):
            self._advance()
        text = self.source[start:self.position]
        return Token(KEYWORDS.get(text, TokenKind.IDENTIFIER), text, line, column, start)

    @staticmethod
    def _is_identifier_start(char: str) -> bool:
        return char.isascii() and (char.isalpha() or char == "_")

    @classmethod
    def _is_identifier_continue(cls, char: str) -> bool:
        return cls._is_identifier_start(char) or (
            char.isascii() and char.isdigit()
        )

    def _integer(self) -> Token:
        start = self.position
        line = self.line
        column = self.column
        while self._peek().isdigit():
            self._advance()
        text = self.source[start:self.position]
        return Token(TokenKind.INTEGER, text, line, column, start)

    def _operator_or_punctuation(self) -> Token:
        start = self.position
        line = self.line
        column = self.column
        three = self.source[start : start + 3]
        if three == "<=>":
            self._advance()
            self._advance()
            self._advance()
            return Token(TokenKind.COMPARE, three, line, column, start)
        two = self.source[start : start + 2]
        if two == "->":
            self._advance()
            self._advance()
            return Token(TokenKind.ARROW, two, line, column, start)
        single_tokens = {
            "~": TokenKind.TILDE,
            "&": TokenKind.AMPERSAND,
            "|": TokenKind.PIPE,
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "=": TokenKind.EQUAL,
            "(": TokenKind.LEFT_PAREN,
            ")": TokenKind.RIGHT_PAREN,
            "{": TokenKind.LEFT_BRACE,
            "}": TokenKind.RIGHT_BRACE,
            "[": TokenKind.LEFT_BRACKET,
            "]": TokenKind.RIGHT_BRACKET,
            ":": TokenKind.COLON,
            ";": TokenKind.SEMICOLON,
            ",": TokenKind.COMMA,
        }
        char = self._peek()
        kind = single_tokens.get(char)
        if kind is None:
            display = char.encode("unicode_escape").decode("ascii")
            raise LexError(
                f"invalid character '{display}'",
                SourceLocation(start, line, column),
            )
        self._advance()
        return Token(kind, char, line, column, start)


def tokenize(source: str) -> tuple[Token, ...]:
    return Lexer(source).tokenize()
