"""Incremental bounded S3 Assembly tokenizer reference."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .bounded_text import BoundedText, SourceSpan, TextCursor


class AssemblyTokenKind(IntEnum):
    VERSION_DIRECTIVE = 1
    DIRECTIVE = 2
    VERSION_NUMBER = 3
    IDENTIFIER = 4
    VALUE_NAME = 5
    REGISTER_NAME = 6
    INTEGER = 7
    COLON = 8
    COMMA = 9
    EQUALS = 10
    LEFT_BRACKET = 11
    RIGHT_BRACKET = 12
    LEFT_PARENTHESIS = 13
    RIGHT_PARENTHESIS = 14
    NEWLINE = 15
    COMMENT = 16


class AssemblyTokenErrorCode(IntEnum):
    UNEXPECTED_CODE_UNIT = 1
    MALFORMED_INTEGER = 2
    INTEGER_OVERFLOW = 3
    INVALID_DIRECTIVE = 4
    INVALID_IDENTIFIER = 5
    INVALID_VALUE_NAME = 6
    INVALID_REGISTER_NAME = 7
    CURSOR_OUT_OF_BOUNDS = 8
    TRUNCATED_TOKEN = 9
    UNSUPPORTED_TOKEN = 10


@dataclass(frozen=True, slots=True)
class AssemblyToken:
    kind: AssemblyTokenKind
    span: SourceSpan
    next_cursor: TextCursor
    scalar_value: int = 0


@dataclass(frozen=True, slots=True)
class AssemblyTokenError:
    code: AssemblyTokenErrorCode
    span: SourceSpan
    detail: int = 0


@dataclass(frozen=True, slots=True)
class AssemblyTokenResult:
    variant: str
    token: AssemblyToken | None = None
    cursor: TextCursor | None = None
    error: AssemblyTokenError | None = None


DIRECTIVE_IDS = {
    ".function": 1,
    ".param": 2,
    ".register": 3,
    ".memory": 4,
    ".label": 5,
    ".data": 6,
    ".end": 7,
}


def next_assembly_token(text: BoundedText, cursor: TextCursor) -> AssemblyTokenResult:
    if not 0 <= cursor.position <= text.length:
        error_position = min(max(cursor.position, 0), text.length)
        return AssemblyTokenResult(
            "error",
            error=AssemblyTokenError(
                AssemblyTokenErrorCode.CURSOR_OUT_OF_BOUNDS,
                SourceSpan(error_position, error_position),
                cursor.position,
            ),
        )

    position = _skip_horizontal_whitespace(text, cursor.position)
    if position == text.length:
        return AssemblyTokenResult("end", cursor=TextCursor(position))

    unit = text.units[position]
    if unit == 10:
        return _token(AssemblyTokenKind.NEWLINE, position, position + 1)
    if unit == 13:
        if position + 1 < text.length and text.units[position + 1] == 10:
            return _token(AssemblyTokenKind.NEWLINE, position, position + 2)
        return _error(
            AssemblyTokenErrorCode.TRUNCATED_TOKEN,
            position,
            min(position + 1, text.length),
            unit,
        )
    if unit == 59:
        return _scan_comment(text, position)
    if unit == 46:
        return _scan_directive_or_version(text, position)
    if unit == 45 or _is_digit(unit):
        return _scan_number(text, position)
    if unit == 58:
        return _token(AssemblyTokenKind.COLON, position, position + 1)
    if unit == 44:
        return _token(AssemblyTokenKind.COMMA, position, position + 1)
    if unit == 61:
        return _token(AssemblyTokenKind.EQUALS, position, position + 1)
    if unit == 91:
        return _token(AssemblyTokenKind.LEFT_BRACKET, position, position + 1)
    if unit == 93:
        return _token(AssemblyTokenKind.RIGHT_BRACKET, position, position + 1)
    if unit == 40:
        return _token(AssemblyTokenKind.LEFT_PARENTHESIS, position, position + 1)
    if unit == 41:
        return _token(AssemblyTokenKind.RIGHT_PARENTHESIS, position, position + 1)
    if _is_identifier_start(unit):
        return _scan_name(text, position)
    if unit == 34:
        return _error(
            AssemblyTokenErrorCode.UNSUPPORTED_TOKEN,
            position,
            position + 1,
            unit,
        )
    return _error(
        AssemblyTokenErrorCode.UNEXPECTED_CODE_UNIT,
        position,
        position + 1,
        unit,
    )


def _skip_horizontal_whitespace(text: BoundedText, position: int) -> int:
    while position < text.length and text.units[position] in (9, 32):
        position += 1
    return position


def _scan_comment(text: BoundedText, start: int) -> AssemblyTokenResult:
    position = start
    while position < text.length and text.units[position] not in (10, 13):
        position += 1
    return _token(AssemblyTokenKind.COMMENT, start, position)


def _scan_directive_or_version(text: BoundedText, start: int) -> AssemblyTokenResult:
    position = start + 1
    while position < text.length and _is_identifier_continue(text.units[position]):
        position += 1
    spelling = _slice_ascii(text, start, position)
    if spelling == ".s3asm":
        return _token(AssemblyTokenKind.VERSION_DIRECTIVE, start, position)
    directive_id = DIRECTIVE_IDS.get(spelling)
    if directive_id is not None:
        return _token(AssemblyTokenKind.DIRECTIVE, start, position, directive_id)
    if position == start + 1:
        return _error(AssemblyTokenErrorCode.TRUNCATED_TOKEN, start, position, 46)
    if ".s3asm".startswith(spelling):
        return _error(AssemblyTokenErrorCode.TRUNCATED_TOKEN, start, position, 46)
    return _error(AssemblyTokenErrorCode.INVALID_DIRECTIVE, start, position, 46)


def _scan_name(text: BoundedText, start: int) -> AssemblyTokenResult:
    position = start + 1
    while position < text.length and _is_identifier_continue(text.units[position]):
        position += 1
    spelling = _slice_ascii(text, start, position)
    if spelling[0] == "r" and len(spelling) > 1 and spelling[1:].isdigit():
        return _name_with_numeric_suffix(
            AssemblyTokenKind.REGISTER_NAME,
            AssemblyTokenErrorCode.INVALID_REGISTER_NAME,
            spelling,
            start,
            position,
        )
    if spelling[0] in ("m", "s") and len(spelling) > 1 and spelling[1:].isdigit():
        return _name_with_numeric_suffix(
            AssemblyTokenKind.VALUE_NAME,
            AssemblyTokenErrorCode.INVALID_VALUE_NAME,
            spelling,
            start,
            position,
        )
    return _token(AssemblyTokenKind.IDENTIFIER, start, position)


def _name_with_numeric_suffix(
    kind: AssemblyTokenKind,
    error_code: AssemblyTokenErrorCode,
    spelling: str,
    start: int,
    end: int,
) -> AssemblyTokenResult:
    value = _parse_non_negative_decimal(spelling[1:])
    if value > 364:
        return _error(error_code, start, end, 364)
    return _token(kind, start, end, value)


def _scan_number(text: BoundedText, start: int) -> AssemblyTokenResult:
    position = start
    sign = 1
    if text.units[position] == 45:
        sign = -1
        position += 1
        if position == text.length or not _is_digit(text.units[position]):
            return _error(
                AssemblyTokenErrorCode.MALFORMED_INTEGER,
                start,
                position,
                45,
            )

    value = 0
    while position < text.length and _is_digit(text.units[position]):
        value = value * 10 + (text.units[position] - 48)
        position += 1

    if position < text.length and text.units[position] == 46:
        return _scan_version_number(text, start)
    if position < text.length and not _is_delimiter(text.units[position]):
        detail = text.units[position]
        while position < text.length and not _is_delimiter(text.units[position]):
            position += 1
        return _error(
            AssemblyTokenErrorCode.MALFORMED_INTEGER,
            start,
            position,
            detail,
        )

    signed = value * sign
    if signed < -364 or signed > 364:
        return _error(AssemblyTokenErrorCode.INTEGER_OVERFLOW, start, position, 364)
    return _token(AssemblyTokenKind.INTEGER, start, position, signed)


def _scan_version_number(text: BoundedText, start: int) -> AssemblyTokenResult:
    position = start
    parts: list[int] = []
    for part_index in range(3):
        if position == text.length or not _is_digit(text.units[position]):
            return _error(AssemblyTokenErrorCode.TRUNCATED_TOKEN, start, position)
        value = 0
        while position < text.length and _is_digit(text.units[position]):
            value = value * 10 + (text.units[position] - 48)
            position += 1
        parts.append(value)
        if part_index < 2:
            if position == text.length or text.units[position] != 46:
                return _error(AssemblyTokenErrorCode.TRUNCATED_TOKEN, start, position)
            position += 1
    if position < text.length and not _is_delimiter(text.units[position]):
        while position < text.length and not _is_delimiter(text.units[position]):
            position += 1
        return _error(AssemblyTokenErrorCode.TRUNCATED_TOKEN, start, position)
    if any(part > 9 for part in parts):
        return _error(AssemblyTokenErrorCode.UNSUPPORTED_TOKEN, start, position)
    return _token(
        AssemblyTokenKind.VERSION_NUMBER,
        start,
        position,
        parts[0] * 100 + parts[1] * 10 + parts[2],
    )


def _parse_non_negative_decimal(value: str) -> int:
    result = 0
    for character in value:
        result = result * 10 + ord(character) - 48
    return result


def _token(
    kind: AssemblyTokenKind,
    start: int,
    end: int,
    scalar_value: int = 0,
) -> AssemblyTokenResult:
    return AssemblyTokenResult(
        "token",
        token=AssemblyToken(
            kind,
            SourceSpan(start, end),
            TextCursor(end),
            scalar_value,
        ),
    )


def _error(
    code: AssemblyTokenErrorCode,
    start: int,
    end: int,
    detail: int = 0,
) -> AssemblyTokenResult:
    return AssemblyTokenResult(
        "error",
        error=AssemblyTokenError(code, SourceSpan(start, end), detail),
    )


def _point_span(position: int) -> SourceSpan:
    return SourceSpan(position, position)


def _clamp_position(position: int) -> int:
    return min(max(position, 0), 364)


def _slice_ascii(text: BoundedText, start: int, end: int) -> str:
    return "".join(chr(text.units[index]) for index in range(start, end))


def _is_digit(unit: int) -> bool:
    return 48 <= unit <= 57


def _is_identifier_start(unit: int) -> bool:
    return unit == 95 or 65 <= unit <= 90 or 97 <= unit <= 122


def _is_identifier_continue(unit: int) -> bool:
    return _is_identifier_start(unit) or _is_digit(unit)


def _is_delimiter(unit: int) -> bool:
    return unit in (9, 10, 13, 32, 40, 41, 44, 58, 59, 61, 91, 93)
