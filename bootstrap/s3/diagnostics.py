"""Shared source locations and user-facing diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A zero-based code-point offset and one-based line/column."""

    offset: int
    line: int
    column: int

    def to_dict(self) -> dict[str, int]:
        return {
            "offset": self.offset,
            "line": self.line,
            "column": self.column,
        }


class S3Error(Exception):
    """Base class for source diagnostics intended for command-line users."""

    category = "S3 error"

    def __init__(self, message: str, location: SourceLocation | None = None):
        self.message = message
        self.location = location
        if location is None:
            rendered = f"{self.category}: {message}"
        else:
            rendered = (
                f"{location.line}:{location.column}: "
                f"{self.category}: {message}"
            )
        super().__init__(rendered)


class LexError(S3Error):
    category = "lexical error"


class ParseError(S3Error):
    category = "parse error"


class SemanticError(S3Error):
    category = "semantic error"


class LoweringError(S3Error):
    category = "lowering error"
