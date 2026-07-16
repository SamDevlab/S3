"""Deterministic static text helpers for front-end string literals."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


class StaticTextDecodeError(ValueError):
    """Raised when a static string literal uses an unsupported escape."""


@dataclass(frozen=True, slots=True)
class StaticTextMetadata:
    byte_count: int
    line_count: int
    sha256: str


def decode_static_text(value: str) -> str:
    """Decode the supported static string literal escapes deterministically."""

    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        escape_offset = index
        index += 1
        if index >= len(value):
            raise StaticTextDecodeError("unterminated static text escape")
        escaped = value[index]
        if escaped == "\\":
            result.append("\\")
        elif escaped == '"':
            result.append('"')
        elif escaped == "n":
            result.append("\n")
        else:
            raise StaticTextDecodeError(
                f"unsupported static text escape '\\{escaped}' at offset {escape_offset}"
            )
        index += 1

    return normalize_static_text_newlines("".join(result))


def normalize_static_text_newlines(text: str) -> str:
    """Normalize all static text newlines to LF for platform-stable bytes."""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def encode_static_text(value: str) -> bytes:
    return decode_static_text(value).encode("utf-8")


def static_text_metadata(value: str) -> StaticTextMetadata:
    data = encode_static_text(value)
    text = data.decode("utf-8")
    line_count = 0 if text == "" else len(text.splitlines())
    return StaticTextMetadata(
        byte_count=len(data),
        line_count=line_count,
        sha256=hashlib.sha256(data).hexdigest(),
    )
