"""Canonical, token-preserving source formatting for S3."""

from __future__ import annotations

import hashlib
from pathlib import Path


class FormatterError(ValueError):
    """Raised when formatter input or output paths are invalid."""


def format_source(source: str) -> str:
    """Normalize line endings and trailing horizontal whitespace only.

    The conservative policy intentionally keeps indentation, comments and Unicode
    code points untouched so formatting cannot silently change program tokens.
    """

    if not isinstance(source, str):
        raise FormatterError("source must be text")
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip(" \t") for line in lines).rstrip("\n") + "\n"


def format_file(path: str | Path) -> str:
    file_path = Path(path)
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise FormatterError(f"cannot read source file {file_path}") from error
    formatted = format_source(source)
    try:
        file_path.write_text(formatted, encoding="utf-8", newline="\n")
    except OSError as error:
        raise FormatterError(f"cannot write source file {file_path}") from error
    return formatted


def source_digest(source: str) -> str:
    return hashlib.sha256(format_source(source).encode("utf-8")).hexdigest()
