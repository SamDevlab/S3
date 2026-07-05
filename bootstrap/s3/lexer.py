"""Lexer for the initial S3 language subset."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .diagnostics import (
    DiagnosticCode,
    IndentationError,
    LexError,
    SourceLocation,
)


class SyntaxMode(Enum):
    V0_5 = auto()
    V0_6 = auto()


class TokenKind(Enum):
    FN = auto()
    RETURN = auto()
    SWITCH = auto()
    MATCH = auto()
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
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
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
    def __init__(self, source: str, *, mode: SyntaxMode = SyntaxMode.V0_6):
        self.source = source
        self.mode = mode
        self.position = 0
        self.line = 1
        self.column = 1

        self.indent_stack = [0]
        self.delimiter_stack: list[TokenKind] = []

    def tokenize(self) -> tuple[Token, ...]:
        tokens: list[Token] = []
        at_line_start = True

        while not self._at_end:
            if self.mode == SyntaxMode.V0_6 and at_line_start:
                consumed_empty_line = self._process_indentation(tokens)
                if consumed_empty_line:
                    continue
                at_line_start = False

            char = self._peek()

            if self.mode == SyntaxMode.V0_6:
                if char in "\r\n":
                    loc_pos, loc_line, loc_col = self.position, self.line, self.column
                    if char == "\r" and self._peek(1) == "\n":
                        self._advance()
                    self._advance()
                    if not self.delimiter_stack:
                        tokens.append(Token(TokenKind.NEWLINE, "", loc_line, loc_col, loc_pos))
                        at_line_start = True
                    continue
                if char in " \t":
                    self._advance()
                    continue
                if char == "#":
                    self._skip_comment_v0_6()
                    continue
            else:
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

        if self.mode == SyntaxMode.V0_6:
            if not at_line_start and not self.delimiter_stack:
                tokens.append(Token(TokenKind.NEWLINE, "", self.line, self.column, self.position))

            while len(self.indent_stack) > 1:
                self.indent_stack.pop()
                tokens.append(Token(TokenKind.DEDENT, "", self.line, self.column, self.position))

        tokens.append(Token(TokenKind.EOF, "", self.line, self.column, self.position))
        return tuple(tokens)

    def _process_indentation(self, tokens: list[Token]) -> bool:
        start_pos, start_line, start_col = self.position, self.line, self.column
        spaces = 0
        has_tab = False
        mixed = False

        while not self._at_end:
            c = self._peek()
            if c == " ":
                if has_tab:
                    mixed = True
                spaces += 1
                self._advance()
            elif c == "\t":
                has_tab = True
                if spaces > 0:
                    mixed = True
                self._advance()
            else:
                break

        current_pos, current_line, current_col = self.position, self.line, self.column

        c = self._peek()
        if c in "\r\n\0" or c == "#":
            if c == "#":
                self._skip_comment_v0_6()
            if not self._at_end and self._peek() in "\r\n":
                if self._peek() == "\r" and self._peek(1) == "\n":
                    self._advance()
                self._advance()
            return True

        if self.delimiter_stack:
            return False

        if has_tab or mixed:
            if mixed:
                raise IndentationError(
                    "mixed tabs and spaces in indentation",
                    SourceLocation(start_pos, start_line, start_col),
                    diagnostic_code=DiagnosticCode.LEX_MIXED_INDENTATION
                )
            else:
                raise IndentationError(
                    "tab used in indentation",
                    SourceLocation(start_pos, start_line, start_col),
                    diagnostic_code=DiagnosticCode.LEX_TAB_INDENTATION
                )

        current_indent = self.indent_stack[-1]
        if spaces > current_indent:
            self.indent_stack.append(spaces)
            tokens.append(Token(TokenKind.INDENT, "", current_line, current_col, current_pos))
        elif spaces < current_indent:
            while len(self.indent_stack) > 1 and spaces < self.indent_stack[-1]:
                self.indent_stack.pop()
                tokens.append(Token(TokenKind.DEDENT, "", current_line, current_col, current_pos))
            if spaces != self.indent_stack[-1]:
                raise IndentationError(
                    "unindent does not match any outer indentation level",
                    SourceLocation(current_pos, current_line, current_col),
                    diagnostic_code=DiagnosticCode.LEX_INVALID_DEDENT
                )

        return False

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

    def _skip_comment_v0_6(self) -> None:
        self._advance()
        while not self._at_end and self._peek() not in "\r\n":
            self._advance()

    def _identifier(self) -> Token:
        start = self.position
        line = self.line
        column = self.column
        while self._is_identifier_continue(self._peek()):
            self._advance()
        text = self.source[start:self.position]
        kind = KEYWORDS.get(text, TokenKind.IDENTIFIER)
        if self.mode == SyntaxMode.V0_6 and text == "match":
            kind = TokenKind.MATCH
        return Token(kind, text, line, column, start)

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

        if self.mode == SyntaxMode.V0_6:
            if kind in (TokenKind.LEFT_PAREN, TokenKind.LEFT_BRACKET):
                self.delimiter_stack.append(kind)
            elif kind == TokenKind.RIGHT_PAREN:
                if self.delimiter_stack and self.delimiter_stack[-1] == TokenKind.LEFT_PAREN:
                    self.delimiter_stack.pop()
            elif kind == TokenKind.RIGHT_BRACKET:
                if self.delimiter_stack and self.delimiter_stack[-1] == TokenKind.LEFT_BRACKET:
                    self.delimiter_stack.pop()

        return Token(kind, char, line, column, start)


def tokenize(source: str, *, mode: SyntaxMode = SyntaxMode.V0_6) -> tuple[Token, ...]:
    return Lexer(source, mode=mode).tokenize()
