"""Shared token-arena contract for the hosted and independent frontends.

This module contains only token records, stable storage, and deterministic
serialization.  It deliberately does not import the reference lexer or
parser implementation; the reference compatibility constructor remains in
``source_frontend`` while the generic lexer can depend on this contract
directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .compiler_substrate import StableArena
from .lexer import SyntaxMode, TokenKind


@dataclass(frozen=True, slots=True)
class TokenSpan:
    file_id: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class TokenRecord:
    id: int
    kind: TokenKind
    text: str
    span: TokenSpan
    line: int
    column: int
    source_position: int


class TokenArena:
    """Direct-ID token storage over normalized source text."""

    POSITION_AUTHORITY = "normalized_utf8_bytes"

    def __init__(
        self,
        *,
        file_id: int,
        source: str,
        mode: SyntaxMode,
        lexer_backend: str = "python_reference",
    ) -> None:
        if isinstance(file_id, bool) or not isinstance(file_id, int) or file_id < 0:
            raise ValueError("file_id must be a non-negative integer")
        if not isinstance(lexer_backend, str) or not lexer_backend:
            raise ValueError("lexer_backend must be a non-empty string")
        self.file_id = file_id
        self.source = source
        self.mode = mode
        self.lexer_backend = lexer_backend
        self.tokens: StableArena[TokenRecord] = StableArena()

    @staticmethod
    def normalize_source(source: str) -> str:
        return source.replace("\r\n", "\n").replace("\r", "\n")

    @classmethod
    def from_source_independent(
        cls,
        source: str,
        *,
        file_id: int = 0,
        mode: SyntaxMode = SyntaxMode.V0_6,
    ) -> "TokenArena":
        from .generic_lexer import tokenize_to_arena

        return tokenize_to_arena(source, file_id=file_id, mode=mode)

    def __len__(self) -> int:
        return len(self.tokens)

    def token(self, token_id: int) -> TokenRecord:
        return self.tokens.get(token_id)

    def to_reference_tokens(self) -> tuple[object, ...]:
        from .lexer import Token

        return tuple(
            Token(
                record.kind,
                record.text,
                record.line,
                record.column,
                record.source_position,
            )
            for _, record in self.tokens.items()
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "position_authority": self.POSITION_AUTHORITY,
            "file_id": self.file_id,
            "mode": self.mode.name,
            "tokens": [
                {
                    "id": record.id,
                    "kind": record.kind.name,
                    "text": record.text,
                    "span": {
                        "file_id": record.span.file_id,
                        "start": record.span.start,
                        "end": record.span.end,
                    },
                    "line": record.line,
                    "column": record.column,
                }
                for _, record in self.tokens.items()
            ],
        }

    def structural_digest(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(payload).hexdigest()


def codepoint_to_byte_offsets(source: str) -> tuple[int, ...]:
    result = [0]
    total = 0
    for character in source:
        total += len(character.encode("utf-8"))
        result.append(total)
    return tuple(result)


__all__ = [
    "TokenArena",
    "TokenRecord",
    "TokenSpan",
    "codepoint_to_byte_offsets",
]
