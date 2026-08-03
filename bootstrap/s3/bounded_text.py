"""Pure bounded ASCII text reference for self-hosting differential tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


BOUNDED_TEXT_CAPACITY = 364


class TextErrorCode(IntEnum):
    INVALID_LENGTH = 1
    INVALID_CODE_UNIT = 2
    INVALID_PADDING = 3
    INVALID_CURSOR = 4
    END_OF_INPUT = 5
    INVALID_SPAN = 6
    LOOKAHEAD_OUT_OF_BOUNDS = 7


@dataclass(frozen=True, slots=True)
class TextCursor:
    position: int


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class TextError:
    code: TextErrorCode
    span: SourceSpan
    detail: int = 0


@dataclass(frozen=True, slots=True)
class BoundedText:
    length: int
    units: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BoundedTextEncodeResult:
    text: BoundedText | None = None
    error: TextError | None = None


@dataclass(frozen=True, slots=True)
class TextReadResult:
    kind: str
    cursor: TextCursor
    code_unit: int | None = None
    error: TextError | None = None


@dataclass(frozen=True, slots=True)
class TextAdvanceResult:
    cursor: TextCursor | None = None
    error: TextError | None = None


@dataclass(frozen=True, slots=True)
class TextCompareResult:
    equal: bool | None = None
    error: TextError | None = None


@dataclass(frozen=True, slots=True)
class DecimalDigitResult:
    value: int | None = None


def is_supported_code_unit(value: int) -> bool:
    return value in (9, 10, 13) or 32 <= value <= 126


def encode_ascii(value: str) -> BoundedTextEncodeResult:
    units = tuple(ord(character) for character in value)
    if len(units) > BOUNDED_TEXT_CAPACITY:
        return BoundedTextEncodeResult(
            error=TextError(
                TextErrorCode.INVALID_LENGTH,
                SourceSpan(0, 0),
                BOUNDED_TEXT_CAPACITY,
            )
        )
    for index, unit in enumerate(units):
        if not is_supported_code_unit(unit):
            return BoundedTextEncodeResult(
                error=TextError(
                    TextErrorCode.INVALID_CODE_UNIT,
                    SourceSpan(index, index + 1),
                    unit,
                )
            )
    return BoundedTextEncodeResult(
        text=BoundedText(
            len(units),
            (*units, *(0 for _ in range(BOUNDED_TEXT_CAPACITY - len(units)))),
        )
    )


def validate_text(text: BoundedText) -> TextError | None:
    if not 0 <= text.length <= BOUNDED_TEXT_CAPACITY:
        return TextError(
            TextErrorCode.INVALID_LENGTH,
            SourceSpan(0, 0),
            text.length,
        )
    if len(text.units) != BOUNDED_TEXT_CAPACITY:
        return TextError(
            TextErrorCode.INVALID_LENGTH,
            SourceSpan(0, 0),
            min(len(text.units), BOUNDED_TEXT_CAPACITY),
        )
    for index, unit in enumerate(text.units):
        if index < text.length:
            if not is_supported_code_unit(unit):
                return TextError(
                    TextErrorCode.INVALID_CODE_UNIT,
                    SourceSpan(index, index + 1),
                    unit,
                )
        elif unit != 0:
            return TextError(
                TextErrorCode.INVALID_PADDING,
                SourceSpan(index, index + 1),
                unit,
            )
    return None


def text_length(text: BoundedText) -> int:
    return text.length


def text_is_empty(text: BoundedText) -> bool:
    return text.length == 0


def cursor_start() -> TextCursor:
    return TextCursor(0)


def cursor_position(cursor: TextCursor) -> int:
    return cursor.position


def cursor_is_end(text: BoundedText, cursor: TextCursor) -> TextCompareResult:
    if not 0 <= cursor.position <= text.length:
        return TextCompareResult(error=_cursor_error(cursor))
    return TextCompareResult(equal=cursor.position == text.length)


def read_current(text: BoundedText, cursor: TextCursor) -> TextReadResult:
    if not 0 <= cursor.position <= text.length:
        return TextReadResult("error", cursor, error=_cursor_error(cursor))
    if cursor.position == text.length:
        return TextReadResult("end", cursor)
    unit = text.units[cursor.position]
    if not is_supported_code_unit(unit):
        return TextReadResult(
            "error",
            cursor,
            error=TextError(
                TextErrorCode.INVALID_CODE_UNIT,
                SourceSpan(cursor.position, cursor.position + 1),
                unit,
            ),
        )
    return TextReadResult("unit", cursor, code_unit=unit)


def advance(text: BoundedText, cursor: TextCursor) -> TextAdvanceResult:
    if not 0 <= cursor.position <= text.length:
        return TextAdvanceResult(error=_cursor_error(cursor))
    if cursor.position == text.length:
        return TextAdvanceResult(
            error=TextError(
                TextErrorCode.END_OF_INPUT,
                SourceSpan(cursor.position, cursor.position),
            )
        )
    return TextAdvanceResult(cursor=TextCursor(cursor.position + 1))


def peek(text: BoundedText, cursor: TextCursor, offset: int) -> TextReadResult:
    if not 0 <= cursor.position <= text.length:
        return TextReadResult("error", cursor, error=_cursor_error(cursor))
    if offset < 0:
        return TextReadResult(
            "error",
            cursor,
            error=TextError(
                TextErrorCode.LOOKAHEAD_OUT_OF_BOUNDS,
                SourceSpan(cursor.position, cursor.position),
                offset,
            ),
        )
    remaining = text.length - cursor.position
    if offset > remaining:
        return TextReadResult(
            "error",
            cursor,
            error=TextError(
                TextErrorCode.LOOKAHEAD_OUT_OF_BOUNDS,
                SourceSpan(cursor.position, cursor.position),
                offset,
            ),
        )
    return read_current(text, TextCursor(cursor.position + offset))


def compare_code_unit(
    text: BoundedText,
    cursor: TextCursor,
    expected: int,
) -> TextCompareResult:
    result = read_current(text, cursor)
    if result.error is not None:
        return TextCompareResult(error=result.error)
    if result.kind == "end":
        return TextCompareResult(
            error=TextError(
                TextErrorCode.END_OF_INPUT,
                SourceSpan(cursor.position, cursor.position),
            )
        )
    return TextCompareResult(equal=result.code_unit == expected)


def starts_with(
    text: BoundedText,
    cursor: TextCursor,
    prefix: BoundedText,
) -> TextCompareResult:
    if not 0 <= cursor.position <= text.length:
        return TextCompareResult(error=_cursor_error(cursor))
    if prefix.length > text.length - cursor.position:
        return TextCompareResult(equal=False)
    for index in range(prefix.length):
        if text.units[cursor.position + index] != prefix.units[index]:
            return TextCompareResult(equal=False)
    return TextCompareResult(equal=True)


def span_length(span: SourceSpan) -> int:
    return span.end - span.start


def span_is_empty(span: SourceSpan) -> bool:
    return span.start == span.end


def span_is_valid(text: BoundedText, span: SourceSpan) -> bool:
    return 0 <= span.start <= span.end <= text.length


def classify_decimal_digit(code_unit: int) -> DecimalDigitResult:
    if 48 <= code_unit <= 57:
        return DecimalDigitResult(code_unit - 48)
    return DecimalDigitResult()


def classify_identifier_start(code_unit: int) -> bool:
    return (
        65 <= code_unit <= 90
        or 97 <= code_unit <= 122
        or code_unit == 95
    )


def classify_identifier_continue(code_unit: int) -> bool:
    return classify_identifier_start(code_unit) or 48 <= code_unit <= 57


def _cursor_error(cursor: TextCursor) -> TextError:
    position = min(max(cursor.position, 0), BOUNDED_TEXT_CAPACITY)
    return TextError(
        TextErrorCode.INVALID_CURSOR,
        SourceSpan(position, position),
        min(max(cursor.position, -BOUNDED_TEXT_CAPACITY), BOUNDED_TEXT_CAPACITY),
    )
