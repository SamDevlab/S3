from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.bounded_text import (
    BOUNDED_TEXT_CAPACITY,
    BoundedText,
    SourceSpan,
    TextCursor,
    TextErrorCode,
    advance,
    classify_decimal_digit,
    classify_identifier_continue,
    classify_identifier_start,
    compare_code_unit,
    cursor_is_end,
    cursor_start,
    encode_ascii,
    peek,
    read_current,
    span_is_empty,
    span_is_valid,
    span_length,
    starts_with,
    text_is_empty,
    text_length,
    validate_text,
)
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_sources


ROOT = Path(__file__).resolve().parents[1]
TYPES_SOURCE = (ROOT / "selfhost/text/bounded_text_types.s3").read_text(
    encoding="utf-8"
)
PRIMITIVES_SOURCE = (
    ROOT / "selfhost/text/bounded_text_primitives.s3"
).read_text(encoding="utf-8")


def _encoded(value: str) -> BoundedText:
    result = encode_ascii(value)
    assert result.error is None
    assert result.text is not None
    return result.text


def _units_literal(value: str) -> str:
    units = [*(ord(character) for character in value)]
    units.extend(0 for _ in range(BOUNDED_TEXT_CAPACITY - len(units)))
    return "[" + ", ".join(str(unit) for unit in units) + "]"


def _program(body: str, *, values: tuple[tuple[str, str], ...]) -> str:
    declarations: list[str] = []
    for name, value in values:
        declarations.extend(
            (
                f"    {name}_units: tryte[364] = {_units_literal(value)}",
                (
                    f"    {name}: BoundedText = "
                    f"BoundedText(length={len(value)}, units={name}_units)"
                ),
            )
        )
    return (
        "module main\n"
        "from bounded_text_types import BoundedText\n"
        "from bounded_text_types import DecimalDigitResult\n"
        "from bounded_text_types import SourceSpan\n"
        "from bounded_text_types import TextAdvanceResult\n"
        "from bounded_text_types import TextCompareResult\n"
        "from bounded_text_types import TextCursor\n"
        "from bounded_text_types import TextReadResult\n"
        "from bounded_text_primitives import advance\n"
        "from bounded_text_primitives import classify_decimal_digit\n"
        "from bounded_text_primitives import classify_identifier_continue\n"
        "from bounded_text_primitives import classify_identifier_start\n"
        "from bounded_text_primitives import cursor_is_end\n"
        "from bounded_text_primitives import peek\n"
        "from bounded_text_primitives import read_current\n"
        "from bounded_text_primitives import span_is_empty\n"
        "from bounded_text_primitives import span_is_valid\n"
        "from bounded_text_primitives import span_length\n"
        "from bounded_text_primitives import starts_with\n"
        "from bounded_text_primitives import text_is_empty\n"
        "from bounded_text_primitives import text_length\n"
        "from bounded_text_primitives import validate_text\n"
        "fn main() -> tryte:\n"
        + "\n".join(declarations)
        + "\n"
        + body
        + "\n"
    )


def _execute(source: str, optimization: str) -> int:
    compilation = compile_sources(
        {
            "main.s3": source,
            "bounded_text_types.s3": TYPES_SOURCE,
            "bounded_text_primitives.s3": PRIMITIVES_SOURCE,
        },
        optimization,
    )
    return Emulator().execute(compilation.assembly)


def test_python_reference_empty_single_and_full_capacity() -> None:
    empty = _encoded("")
    one = _encoded("A")
    full = _encoded("x" * BOUNDED_TEXT_CAPACITY)

    assert text_length(empty) == 0
    assert text_is_empty(empty)
    assert cursor_start() == TextCursor(0)
    assert text_length(one) == 1
    assert not text_is_empty(one)
    assert text_length(full) == BOUNDED_TEXT_CAPACITY
    assert validate_text(empty) is None
    assert validate_text(one) is None
    assert validate_text(full) is None


def test_python_reference_rejects_length_code_unit_and_padding() -> None:
    invalid_length = BoundedText(-1, (0,) * BOUNDED_TEXT_CAPACITY)
    invalid_unit = BoundedText(
        1,
        (1, *(0 for _ in range(BOUNDED_TEXT_CAPACITY - 1))),
    )
    invalid_padding = BoundedText(
        0,
        (65, *(0 for _ in range(BOUNDED_TEXT_CAPACITY - 1))),
    )

    assert validate_text(invalid_length).code is TextErrorCode.INVALID_LENGTH
    assert validate_text(invalid_unit).code is TextErrorCode.INVALID_CODE_UNIT
    assert validate_text(invalid_padding).code is TextErrorCode.INVALID_PADDING


def test_python_reference_cursor_read_advance_peek_and_overrun() -> None:
    text = _encoded("ab")
    start = TextCursor(0)

    assert cursor_is_end(text, start).equal is False
    assert read_current(text, start).code_unit == 97
    second = advance(text, start).cursor
    assert second == TextCursor(1)
    assert read_current(text, second).code_unit == 98
    assert peek(text, start, 1).code_unit == 98
    end = advance(text, second).cursor
    assert end == TextCursor(2)
    assert read_current(text, end).kind == "end"
    assert advance(text, end).error.code is TextErrorCode.END_OF_INPUT
    assert peek(text, start, 3).error.code is TextErrorCode.LOOKAHEAD_OUT_OF_BOUNDS
    assert read_current(text, TextCursor(-1)).error.code is TextErrorCode.INVALID_CURSOR
    assert peek(text, TextCursor(-1), 1).error.code is TextErrorCode.INVALID_CURSOR
    assert peek(text, TextCursor(3), 0).error.code is TextErrorCode.INVALID_CURSOR


def test_python_reference_spans_prefix_and_classification() -> None:
    text = _encoded("alpha9")
    prefix = _encoded("alp")

    assert starts_with(text, TextCursor(0), prefix).equal is True
    assert starts_with(text, TextCursor(1), prefix).equal is False
    assert compare_code_unit(text, TextCursor(0), 97).equal is True
    assert span_length(SourceSpan(1, 4)) == 3
    assert span_is_empty(SourceSpan(2, 2))
    assert span_is_valid(text, SourceSpan(0, 6))
    assert not span_is_valid(text, SourceSpan(4, 3))
    assert classify_decimal_digit(57).value == 9
    assert classify_decimal_digit(65).value is None
    assert classify_identifier_start(95)
    assert classify_identifier_start(65)
    assert not classify_identifier_start(45)
    assert classify_identifier_continue(57)


@pytest.mark.parametrize("optimization", ("O0", "O1"))
def test_s3_bounded_text_read_and_advance_match_python(optimization: str) -> None:
    source = _program(
        "    first: TextReadResult = read_current(text, TextCursor(position=0))\n"
        "    match first:\n"
        "        TextReadResult.Unit(code_unit, cursor):\n"
        "            next: TextAdvanceResult = advance(text, cursor)\n"
        "            match next:\n"
        "                TextAdvanceResult.Advanced(cursor):\n"
        "                    second: TextReadResult = read_current(text, cursor)\n"
        "                    match second:\n"
        "                        TextReadResult.Unit(code_unit, cursor):\n"
        "                            return code_unit\n"
        "                        TextReadResult.End(cursor):\n"
        "                            return -1\n"
        "                        TextReadResult.Error(error):\n"
        "                            return 0 - error.code\n"
        "                TextAdvanceResult.Error(error):\n"
        "                    return 0 - error.code\n"
        "        TextReadResult.End(cursor):\n"
        "            return -1\n"
        "        TextReadResult.Error(error):\n"
        "            return 0 - error.code",
        values=(("text", "AZ"),),
    )

    expected = read_current(_encoded("AZ"), TextCursor(1)).code_unit

    assert _execute(source, optimization) == expected


@pytest.mark.parametrize("optimization", ("O0", "O1"))
def test_s3_prefix_span_digit_and_identifier_operations(optimization: str) -> None:
    source = _program(
        "    match starts_with(text, TextCursor(position=0), prefix):\n"
        "        TextCompareResult.Compared(equal):\n"
        "            match equal:\n"
        "                -1:\n"
        "                    span: SourceSpan = SourceSpan(start=1, end=4)\n"
        "                    digit: DecimalDigitResult = classify_decimal_digit(57)\n"
        "                    match digit:\n"
        "                        DecimalDigitResult.Digit(value):\n"
        "                            return span_length(span) + value\n"
        "                        DecimalDigitResult.NotDigit:\n"
        "                            return -1\n"
        "                0:\n"
        "                    return -2\n"
        "                1:\n"
        "                    return -3\n"
        "        TextCompareResult.Error(error):\n"
        "            return 0 - error.code",
        values=(("text", "alpha9"), ("prefix", "alp")),
    )

    text = _encoded("alpha9")
    prefix = _encoded("alp")
    prefix_matches = starts_with(text, TextCursor(0), prefix).equal
    digit = classify_decimal_digit(57).value
    assert digit is not None
    expected = span_length(SourceSpan(1, 4)) + digit if prefix_matches else -2

    assert _execute(source, optimization) == expected


def test_python_reference_repeated_calls_are_deterministic() -> None:
    text = _encoded("repeat9")
    cursor = TextCursor(6)

    assert read_current(text, cursor) == read_current(text, cursor)
    assert advance(text, cursor) == advance(text, cursor)
    assert peek(text, TextCursor(0), 3) == peek(text, TextCursor(0), 3)


def test_s3_component_is_deterministic_under_source_unit_permutations() -> None:
    source = _program(
        "    return text_length(text)",
        values=(("text", "deterministic"),),
    )
    first = (
        ("main.s3", source),
        ("bounded_text_types.s3", TYPES_SOURCE),
        ("bounded_text_primitives.s3", PRIMITIVES_SOURCE),
    )
    second = tuple(reversed(first))

    first_ir = compile_sources(first, "O0").ir.to_dict()
    second_ir = compile_sources(second, "O0").ir.to_dict()

    assert first_ir == second_ir
