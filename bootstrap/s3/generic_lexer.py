"""Independent generic lexer that writes TokenArena directly.

The lexer mirrors the current lexical contract but does not call
bootstrap.s3.lexer.Lexer or bootstrap.s3.lexer.tokenize.  It shares only the
stable TokenKind/SyntaxMode enums so the parser and differential oracle speak
the same token vocabulary.
"""

from __future__ import annotations

from .diagnostics import (
    DiagnosticCode,
    IndentationError,
    LexError,
    SourceLocation,
)
from .frontend_token_arena import TokenArena, TokenRecord, TokenSpan
from .lexer import SyntaxMode, TokenKind


_V0_5_KEYWORDS: dict[str, TokenKind] = {
    "fn": TokenKind.FN,
    "return": TokenKind.RETURN,
    "switch": TokenKind.SWITCH,
    "while": TokenKind.WHILE,
    "mut": TokenKind.MUT,
    "trit": TokenKind.TRIT,
    "tryte": TokenKind.TRYTE,
    "i64": TokenKind.I64,
    "f64": TokenKind.F64,
    "else": TokenKind.ELSE,
}

_V0_6_KEYWORDS: dict[str, TokenKind] = {
    **_V0_5_KEYWORDS,
    "module": TokenKind.MODULE,
    "from": TokenKind.FROM,
    "import": TokenKind.IMPORT,
    "as": TokenKind.AS,
    "export": TokenKind.EXPORT,
    "foreign": TokenKind.FOREIGN,
    "record": TokenKind.RECORD,
    "enum": TokenKind.ENUM,
    "match": TokenKind.MATCH,
    "select": TokenKind.SELECT,
    "case": TokenKind.CASE,
    "break": TokenKind.BREAK,
    "continue": TokenKind.CONTINUE,
    "for": TokenKind.FOR,
    "in": TokenKind.IN,
    "range": TokenKind.RANGE,
    "len": TokenKind.LEN,
    "discard": TokenKind.DISCARD,
    "else": TokenKind.ELSE,
}

_SINGLE_TOKENS: dict[str, TokenKind] = {
    "~": TokenKind.TILDE,
    "&": TokenKind.AMPERSAND,
    "|": TokenKind.PIPE,
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "/": TokenKind.SLASH,
    "=": TokenKind.EQUAL,
    "<": TokenKind.LESS,
    ">": TokenKind.GREATER,
    "(": TokenKind.LEFT_PAREN,
    ")": TokenKind.RIGHT_PAREN,
    "{": TokenKind.LEFT_BRACE,
    "}": TokenKind.RIGHT_BRACE,
    "[": TokenKind.LEFT_BRACKET,
    "]": TokenKind.RIGHT_BRACKET,
    ":": TokenKind.COLON,
    ";": TokenKind.SEMICOLON,
    ",": TokenKind.COMMA,
    ".": TokenKind.DOT,
}

_TWO_TOKENS: dict[str, TokenKind] = {
    "->": TokenKind.ARROW,
    "==": TokenKind.EQUAL_EQUAL,
    "!=": TokenKind.NOT_EQUAL,
    "<=": TokenKind.LESS_EQUAL,
    ">=": TokenKind.GREATER_EQUAL,
    "+=": TokenKind.PLUS_EQUAL,
    "*=": TokenKind.STAR_EQUAL,
}


class GenericLexer:
    """Deterministic lexer over normalized source text."""

    def __init__(
        self,
        source: str,
        *,
        file_id: int = 0,
        mode: SyntaxMode = SyntaxMode.V0_6,
    ) -> None:
        if isinstance(file_id, bool) or not isinstance(file_id, int) or file_id < 0:
            raise ValueError("file_id must be a non-negative integer")
        self.source = TokenArena.normalize_source(source)
        self.file_id = file_id
        self.mode = mode
        self.position = 0
        self.line = 1
        self.column = 1
        self.indent_stack = [0]
        self.delimiter_stack: list[TokenKind] = []
        self.byte_offsets = _codepoint_to_byte_offsets(self.source)
        self.arena = TokenArena(
            file_id=file_id,
            source=self.source,
            mode=mode,
            lexer_backend="independent_generic",
        )

    def tokenize(self) -> TokenArena:
        at_line_start = True

        while not self._at_end:
            if self.mode is SyntaxMode.V0_6 and at_line_start:
                if self._process_indentation():
                    continue
                at_line_start = False

            char = self._peek()

            if self.mode is SyntaxMode.V0_6:
                if char in "\r\n":
                    start = self._mark()
                    if char == "\r" and self._peek(1) == "\n":
                        self._advance()
                    self._advance()
                    if not self.delimiter_stack:
                        self._emit(TokenKind.NEWLINE, "", start)
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
                    self._skip_comment_v0_5()
                    continue

            if _is_identifier_start(char):
                self._identifier()
                continue
            if char.isdigit():
                self._number()
                continue
            if char == '"':
                self._string_literal()
                continue
            self._operator_or_punctuation()

        if self.mode is SyntaxMode.V0_6:
            if not at_line_start and not self.delimiter_stack:
                self._emit(TokenKind.NEWLINE, "", self._mark())

            while len(self.indent_stack) > 1:
                self.indent_stack.pop()
                self._emit(TokenKind.DEDENT, "", self._mark())

        self._emit(TokenKind.EOF, "", self._mark())
        return self.arena

    # ------------------------------------------------------------------
    # Indentation/newlines
    # ------------------------------------------------------------------

    def _process_indentation(self) -> bool:
        start = self._mark()
        spaces = 0
        has_tab = False
        mixed = False

        while not self._at_end:
            char = self._peek()
            if char == " ":
                if has_tab:
                    mixed = True
                spaces += 1
                self._advance()
            elif char == "\t":
                has_tab = True
                if spaces > 0:
                    mixed = True
                self._advance()
            else:
                break

        current = self._mark()
        char = self._peek()
        if char in "\r\n" or char == "#":
            if char == "#":
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
                    self._location(start),
                    diagnostic_code=DiagnosticCode.LEX_MIXED_INDENTATION,
                )
            raise IndentationError(
                "tab used in indentation",
                self._location(start),
                diagnostic_code=DiagnosticCode.LEX_TAB_INDENTATION,
            )

        current_indent = self.indent_stack[-1]
        if spaces > current_indent:
            self.indent_stack.append(spaces)
            self._emit(TokenKind.INDENT, "", current)
        elif spaces < current_indent:
            while len(self.indent_stack) > 1 and spaces < self.indent_stack[-1]:
                self.indent_stack.pop()
                self._emit(TokenKind.DEDENT, "", current)
            if spaces != self.indent_stack[-1]:
                raise IndentationError(
                    "unindent does not match any outer indentation level",
                    self._location(current),
                    diagnostic_code=DiagnosticCode.LEX_INVALID_DEDENT,
                )
        return False

    # ------------------------------------------------------------------
    # Lexemes
    # ------------------------------------------------------------------

    def _identifier(self) -> None:
        start = self._mark()
        while _is_identifier_continue(self._peek()):
            self._advance()
        text = self.source[start[0] : self.position]
        keywords = _V0_6_KEYWORDS if self.mode is SyntaxMode.V0_6 else _V0_5_KEYWORDS
        self._emit(keywords.get(text, TokenKind.IDENTIFIER), text, start)

    def _number(self) -> None:
        start = self._mark()
        while self._peek().isdigit():
            self._advance()
        kind = TokenKind.INTEGER
        if self._peek() == "." and self._peek(1).isdigit():
            kind = TokenKind.FLOAT
            self._advance()
            while self._peek().isdigit():
                self._advance()
        self._emit(kind, self.source[start[0] : self.position], start)

    def _string_literal(self) -> None:
        start = self._mark()
        self._advance()

        while not self._at_end:
            char = self._peek()
            if char == '"':
                self._advance()
                self._emit(
                    TokenKind.STRING_LITERAL,
                    self.source[start[0] : self.position],
                    start,
                )
                return
            if char in "\r\n":
                break
            if char == "\\":
                self._advance()
                if self._at_end or self._peek() in "\r\n":
                    break
            self._advance()

        raise LexError(
            "unterminated string literal",
            self._location(start),
            diagnostic_code=DiagnosticCode.LEX_UNTERMINATED_STRING_LITERAL,
        )

    def _operator_or_punctuation(self) -> None:
        start = self._mark()

        three = self.source[self.position : self.position + 3]
        if three == "<=>":
            self._advance()
            self._advance()
            self._advance()
            self._emit(TokenKind.COMPARE, three, start)
            return

        two = self.source[self.position : self.position + 2]
        kind = _TWO_TOKENS.get(two)
        if kind is not None:
            self._advance()
            self._advance()
            self._emit(kind, two, start)
            return

        char = self._peek()
        kind = _SINGLE_TOKENS.get(char)
        if kind is None:
            display = char.encode("unicode_escape").decode("ascii")
            raise LexError(
                f"invalid character '{display}'",
                self._location(start),
            )

        self._advance()
        if self.mode is SyntaxMode.V0_6:
            if kind in (TokenKind.LEFT_PAREN, TokenKind.LEFT_BRACKET):
                self.delimiter_stack.append(kind)
            elif kind is TokenKind.RIGHT_PAREN:
                if (
                    self.delimiter_stack
                    and self.delimiter_stack[-1] is TokenKind.LEFT_PAREN
                ):
                    self.delimiter_stack.pop()
            elif kind is TokenKind.RIGHT_BRACKET:
                if (
                    self.delimiter_stack
                    and self.delimiter_stack[-1] is TokenKind.LEFT_BRACKET
                ):
                    self.delimiter_stack.pop()

        self._emit(kind, char, start)

    # ------------------------------------------------------------------
    # Cursor and emission
    # ------------------------------------------------------------------

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

    def _skip_comment_v0_5(self) -> None:
        self._advance()
        self._advance()
        while not self._at_end and self._peek() != "\n":
            self._advance()

    def _skip_comment_v0_6(self) -> None:
        self._advance()
        while not self._at_end and self._peek() not in "\r\n":
            self._advance()

    def _mark(self) -> tuple[int, int, int]:
        return self.position, self.line, self.column

    @staticmethod
    def _location(mark: tuple[int, int, int]) -> SourceLocation:
        return SourceLocation(mark[0], mark[1], mark[2])

    def _emit(
        self,
        kind: TokenKind,
        text: str,
        mark: tuple[int, int, int],
    ) -> int:
        source_position, line, column = mark
        end_position = min(len(self.source), source_position + len(text))
        token_id = self.arena.tokens.checkpoint()
        return self.arena.tokens.append(
            TokenRecord(
                token_id,
                kind,
                text,
                TokenSpan(
                    self.file_id,
                    self.byte_offsets[source_position],
                    self.byte_offsets[end_position],
                ),
                line,
                column,
                source_position,
            )
        )


def _codepoint_to_byte_offsets(source: str) -> tuple[int, ...]:
    result = [0]
    total = 0
    for character in source:
        total += len(character.encode("utf-8"))
        result.append(total)
    return tuple(result)


def _is_identifier_start(char: str) -> bool:
    return char.isascii() and (char.isalpha() or char == "_")


def _is_identifier_continue(char: str) -> bool:
    return _is_identifier_start(char) or (
        char.isascii() and char.isdigit()
    )


def tokenize_to_arena(
    source: str,
    *,
    file_id: int = 0,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> TokenArena:
    """Tokenize without bootstrap.s3.lexer.Lexer/tokenize."""

    return GenericLexer(source, file_id=file_id, mode=mode).tokenize()


__all__ = [
    "GenericLexer",
    "tokenize_to_arena",
]
