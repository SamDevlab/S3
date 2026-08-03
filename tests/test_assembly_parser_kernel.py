from __future__ import annotations

from pathlib import Path

from bootstrap.s3.assembly_parser_kernel import (
    AssemblyParserErrorCode,
    AssemblyParserEventKind,
    initial_parser_state,
    next_assembly_event,
)
from bootstrap.s3.assembly_tokenizer import AssemblyTokenKind, next_assembly_token
from bootstrap.s3.bounded_text import BoundedText, TextCursor, encode_ascii


FINAL_VALIDATION_STATUS = "EXECUTED DURING CONSOLIDATED CAMPAIGN VALIDATION"

ROOT = Path(__file__).resolve().parents[1]
BOUNDED_TYPES_SOURCE = (
    ROOT / "selfhost/text/bounded_text_types.s3"
).read_text(encoding="utf-8")
TOKENIZER_TYPES_SOURCE = (
    ROOT / "selfhost/assembly/tokenizer_types.s3"
).read_text(encoding="utf-8")
TOKENIZER_SOURCE = (
    ROOT / "selfhost/assembly/assembly_tokenizer.s3"
).read_text(encoding="utf-8")
PARSER_TYPES_SOURCE = (
    ROOT / "selfhost/assembly/parser_types.s3"
).read_text(encoding="utf-8")
PARSER_SOURCE = (
    ROOT / "selfhost/assembly/assembly_parser.s3"
).read_text(encoding="utf-8")


VALID_ASSEMBLY = """.s3asm 0.6.0

.function main -> [tryte, trit]
    .param r0, tryte
    .register r1, tryte
.label entry
    TCALL  [r0, r1], pair
    TRET   [r0, r1]
.end
"""


def _encoded(value: str) -> BoundedText:
    result = encode_ascii(value)
    assert result.error is None
    assert result.text is not None
    return result.text


def test_tests_are_part_of_consolidated_campaign_validation() -> None:
    assert FINAL_VALIDATION_STATUS == (
        "EXECUTED DURING CONSOLIDATED CAMPAIGN VALIDATION"
    )


def test_tokenizer_recognizes_function_arrow_boundary() -> None:
    result = next_assembly_token(_encoded("-> tryte"), TextCursor(0))

    assert result.variant == "token"
    assert result.token is not None
    assert result.token.kind is AssemblyTokenKind.ARROW
    assert result.token.span.start == 0
    assert result.token.span.end == 2
    assert result.token.next_cursor.position == 2


def test_python_parser_kernel_emits_incremental_events() -> None:
    text = _encoded(VALID_ASSEMBLY)
    state = initial_parser_state()
    observed: list[AssemblyParserEventKind] = []
    widths: list[int] = []

    while True:
        result = next_assembly_event(text, state)
        if result.variant == "end":
            break
        assert result.variant == "event", result.error
        assert result.event is not None
        observed.append(result.event.kind)
        widths.append(result.event.result_width)
        state = result.state

    assert observed == [
        AssemblyParserEventKind.VERSION,
        AssemblyParserEventKind.FUNCTION_HEADER,
        AssemblyParserEventKind.DECLARATION,
        AssemblyParserEventKind.DECLARATION,
        AssemblyParserEventKind.BLOCK_LABEL,
        AssemblyParserEventKind.CALL,
        AssemblyParserEventKind.RETURN,
        AssemblyParserEventKind.END_FUNCTION,
    ]
    assert widths[1] == 2
    assert widths[5] == 2
    assert state.function_count == 1
    assert state.block_count == 1
    assert state.call_count == 1
    assert state.return_count == 1
    assert state.max_result_width == 2


def test_python_parser_kernel_rejects_unsupported_version() -> None:
    text = _encoded(".s3asm 0.7.0\n")
    result = next_assembly_event(text, initial_parser_state())

    assert result.variant == "error"
    assert result.error is not None
    assert result.error.code is AssemblyParserErrorCode.UNSUPPORTED_VERSION


def test_python_parser_kernel_requires_function_arrow() -> None:
    text = _encoded(".s3asm 0.6.0\n.function main tryte\n")
    state = initial_parser_state()
    version = next_assembly_event(text, state)
    assert version.variant == "event"

    result = next_assembly_event(text, version.state)
    assert result.variant == "error"
    assert result.error is not None
    assert result.error.code is AssemblyParserErrorCode.EXPECTED_ARROW


def test_s3_parser_sources_are_available_for_deferred_differential_coverage() -> None:
    assert "export fn initial_assembly_parser_state" in PARSER_SOURCE
    assert "export fn next_assembly_parser_event" in PARSER_SOURCE
    assert "export enum AssemblyParserResult" in PARSER_TYPES_SOURCE
    assert "selfhost.assembly.assembly_tokenizer" in PARSER_SOURCE
    assert "AssemblyTokenResult" in TOKENIZER_TYPES_SOURCE
    assert "next_assembly_token" in TOKENIZER_SOURCE
    assert "record BoundedText" in BOUNDED_TYPES_SOURCE
