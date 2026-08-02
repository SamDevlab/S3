"""Incremental bounded S3 Assembly parser kernel reference.

The kernel is intentionally small and event-oriented. It recognizes the Assembly
0.6 textual boundary needed by the self-hosting campaign, while the existing
``parse_assembly`` implementation remains the semantic source of truth for whole
program validation and default artifact loading.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .assembly import ASSEMBLY_FORMAT_VERSION, ASSEMBLY_LEGACY_FORMAT_VERSION
from .assembly_tokenizer import (
    AssemblyToken,
    AssemblyTokenError,
    AssemblyTokenKind,
    next_assembly_token,
)
from .bounded_text import BoundedText, SourceSpan, TextCursor


class AssemblyParserEventKind(IntEnum):
    VERSION = 1
    FUNCTION_HEADER = 2
    DECLARATION = 3
    BLOCK_LABEL = 4
    CALL = 5
    RETURN = 6
    END_FUNCTION = 7


class AssemblyParserErrorCode(IntEnum):
    TOKEN_ERROR = 1
    EXPECTED_VERSION_DIRECTIVE = 2
    EXPECTED_VERSION_NUMBER = 3
    UNSUPPORTED_VERSION = 4
    EXPECTED_FUNCTION_DIRECTIVE = 5
    EXPECTED_IDENTIFIER = 6
    EXPECTED_ARROW = 7
    EXPECTED_TYPE_NAME = 8
    EXPECTED_NEWLINE = 9
    EXPECTED_LABEL_DIRECTIVE = 10
    UNKNOWN_OPCODE = 11
    EXPECTED_REGISTER_GROUP = 12
    EXPECTED_CALLEE = 13
    EXPECTED_END_DIRECTIVE = 14
    UNSUPPORTED_SYNTAX = 15


class AssemblyParserPhase(IntEnum):
    START = 1
    AFTER_VERSION = 2
    IN_FUNCTION = 3
    AFTER_END = 4


@dataclass(frozen=True, slots=True)
class AssemblyParserState:
    phase: AssemblyParserPhase
    cursor: TextCursor
    version: int = 0
    function_count: int = 0
    declaration_count: int = 0
    block_count: int = 0
    call_count: int = 0
    return_count: int = 0
    current_result_width: int = 0
    max_result_width: int = 0


@dataclass(frozen=True, slots=True)
class AssemblyParserEvent:
    kind: AssemblyParserEventKind
    span: SourceSpan
    next_cursor: TextCursor
    version: int = 0
    result_width: int = 0
    operand_width: int = 0
    discard_results: bool = False


@dataclass(frozen=True, slots=True)
class AssemblyParserError:
    code: AssemblyParserErrorCode
    span: SourceSpan
    detail: int = 0
    token_error: AssemblyTokenError | None = None


@dataclass(frozen=True, slots=True)
class AssemblyParserResult:
    variant: str
    state: AssemblyParserState
    event: AssemblyParserEvent | None = None
    error: AssemblyParserError | None = None


def initial_parser_state() -> AssemblyParserState:
    return AssemblyParserState(AssemblyParserPhase.START, TextCursor(0))


def next_assembly_event(
    text: BoundedText,
    state: AssemblyParserState,
) -> AssemblyParserResult:
    cursor = _skip_trivia(text, state.cursor)
    if cursor.position >= text.length:
        return AssemblyParserResult("end", _with_cursor(state, cursor))
    if state.phase is AssemblyParserPhase.START:
        return _parse_version(text, state, cursor)
    if state.phase is AssemblyParserPhase.AFTER_VERSION:
        return _parse_function_header(text, state, cursor)
    if state.phase is AssemblyParserPhase.IN_FUNCTION:
        return _parse_function_item(text, state, cursor)
    return AssemblyParserResult("end", _with_cursor(state, cursor))


def parse_all_events(text: BoundedText) -> AssemblyParserResult:
    state = initial_parser_state()
    while True:
        result = next_assembly_event(text, state)
        if result.variant != "event":
            return result
        state = result.state


def _parse_version(
    text: BoundedText,
    state: AssemblyParserState,
    cursor: TextCursor,
) -> AssemblyParserResult:
    first = _expect(text, cursor, AssemblyTokenKind.VERSION_DIRECTIVE)
    if first.error is not None:
        return _failure(state, first.error, AssemblyParserErrorCode.EXPECTED_VERSION_DIRECTIVE)
    second = _expect(text, first.token.next_cursor, AssemblyTokenKind.VERSION_NUMBER)
    if second.error is not None:
        return _failure(state, second.error, AssemblyParserErrorCode.EXPECTED_VERSION_NUMBER)
    assert first.token is not None
    assert second.token is not None
    if second.token.scalar_value not in (_version_value(ASSEMBLY_FORMAT_VERSION), _version_value(ASSEMBLY_LEGACY_FORMAT_VERSION)):
        return _failure_token(state, second.token, AssemblyParserErrorCode.UNSUPPORTED_VERSION)
    end_cursor = _line_end(text, second.token.next_cursor)
    if end_cursor is None:
        return _failure_token(state, second.token, AssemblyParserErrorCode.EXPECTED_NEWLINE)
    next_state = AssemblyParserState(
        AssemblyParserPhase.AFTER_VERSION,
        end_cursor,
        second.token.scalar_value,
    )
    event = AssemblyParserEvent(
        AssemblyParserEventKind.VERSION,
        SourceSpan(first.token.span.start, second.token.span.end),
        end_cursor,
        version=second.token.scalar_value,
    )
    return AssemblyParserResult("event", next_state, event=event)


def _parse_function_header(
    text: BoundedText,
    state: AssemblyParserState,
    cursor: TextCursor,
) -> AssemblyParserResult:
    directive = _expect_directive(text, cursor, 1)
    if directive.error is not None:
        return _failure(state, directive.error, AssemblyParserErrorCode.EXPECTED_FUNCTION_DIRECTIVE)
    name = _expect(text, directive.token.next_cursor, AssemblyTokenKind.IDENTIFIER)
    if name.error is not None:
        return _failure(state, name.error, AssemblyParserErrorCode.EXPECTED_IDENTIFIER)
    arrow = _expect(text, name.token.next_cursor, AssemblyTokenKind.ARROW)
    if arrow.error is not None:
        return _failure(state, arrow.error, AssemblyParserErrorCode.EXPECTED_ARROW)
    width_result = _parse_type_group(text, arrow.token.next_cursor)
    if width_result.error is not None:
        return _failure(state, width_result.error, AssemblyParserErrorCode.EXPECTED_TYPE_NAME)
    end_cursor = _line_end(text, width_result.cursor)
    if end_cursor is None:
        return _failure_token(state, width_result.last_token, AssemblyParserErrorCode.EXPECTED_NEWLINE)
    result_width = width_result.width
    assert directive.token is not None
    next_state = AssemblyParserState(
        AssemblyParserPhase.IN_FUNCTION,
        end_cursor,
        state.version,
        state.function_count + 1,
        state.declaration_count,
        state.block_count,
        state.call_count,
        state.return_count,
        result_width,
        max(state.max_result_width, result_width),
    )
    event = AssemblyParserEvent(
        AssemblyParserEventKind.FUNCTION_HEADER,
        SourceSpan(directive.token.span.start, width_result.last_token.span.end),
        end_cursor,
        version=state.version,
        result_width=result_width,
    )
    return AssemblyParserResult("event", next_state, event=event)


def _parse_function_item(
    text: BoundedText,
    state: AssemblyParserState,
    cursor: TextCursor,
) -> AssemblyParserResult:
    token_result = _next_token(text, cursor)
    if token_result.error is not None:
        return _failure(state, token_result.error, AssemblyParserErrorCode.TOKEN_ERROR)
    token = token_result.token
    assert token is not None
    if token.kind is AssemblyTokenKind.DIRECTIVE:
        if token.scalar_value in (2, 3, 4):
            return _parse_declaration(text, state, token)
        if token.scalar_value == 5:
            return _parse_label(text, state, token)
        if token.scalar_value == 7:
            end_cursor = _line_end(text, token.next_cursor)
            if end_cursor is None:
                return _failure_token(state, token, AssemblyParserErrorCode.EXPECTED_NEWLINE)
            next_state = AssemblyParserState(
                AssemblyParserPhase.AFTER_END,
                end_cursor,
                state.version,
                state.function_count,
                state.declaration_count,
                state.block_count,
                state.call_count,
                state.return_count,
                0,
                state.max_result_width,
            )
            event = AssemblyParserEvent(
                AssemblyParserEventKind.END_FUNCTION,
                token.span,
                end_cursor,
                version=state.version,
            )
            return AssemblyParserResult("event", next_state, event=event)
        return _failure_token(state, token, AssemblyParserErrorCode.UNSUPPORTED_SYNTAX)
    if token.kind is not AssemblyTokenKind.IDENTIFIER:
        return _failure_token(state, token, AssemblyParserErrorCode.UNKNOWN_OPCODE)
    opcode = _slice_ascii(text, token.span.start, token.span.end)
    if opcode == "TCALL":
        return _parse_call(text, state, token)
    if opcode == "TRET":
        return _parse_return(text, state, token)
    return _failure_token(state, token, AssemblyParserErrorCode.UNKNOWN_OPCODE)


def _parse_declaration(
    text: BoundedText,
    state: AssemblyParserState,
    token: AssemblyToken,
) -> AssemblyParserResult:
    end_cursor = _line_end(text, token.next_cursor)
    if end_cursor is None:
        return _failure_token(state, token, AssemblyParserErrorCode.EXPECTED_NEWLINE)
    next_state = AssemblyParserState(
        state.phase,
        end_cursor,
        state.version,
        state.function_count,
        state.declaration_count + 1,
        state.block_count,
        state.call_count,
        state.return_count,
        state.current_result_width,
        state.max_result_width,
    )
    event = AssemblyParserEvent(
        AssemblyParserEventKind.DECLARATION,
        SourceSpan(token.span.start, end_cursor.position),
        end_cursor,
        version=state.version,
    )
    return AssemblyParserResult("event", next_state, event=event)


def _parse_label(
    text: BoundedText,
    state: AssemblyParserState,
    token: AssemblyToken,
) -> AssemblyParserResult:
    name = _expect(text, token.next_cursor, AssemblyTokenKind.IDENTIFIER)
    if name.error is not None:
        return _failure(state, name.error, AssemblyParserErrorCode.EXPECTED_IDENTIFIER)
    end_cursor = _line_end(text, name.token.next_cursor)
    if end_cursor is None:
        return _failure_token(state, name.token, AssemblyParserErrorCode.EXPECTED_NEWLINE)
    next_state = AssemblyParserState(
        state.phase,
        end_cursor,
        state.version,
        state.function_count,
        state.declaration_count,
        state.block_count + 1,
        state.call_count,
        state.return_count,
        state.current_result_width,
        state.max_result_width,
    )
    event = AssemblyParserEvent(
        AssemblyParserEventKind.BLOCK_LABEL,
        SourceSpan(token.span.start, name.token.span.end),
        end_cursor,
        version=state.version,
    )
    return AssemblyParserResult("event", next_state, event=event)


def _parse_call(
    text: BoundedText,
    state: AssemblyParserState,
    token: AssemblyToken,
) -> AssemblyParserResult:
    destinations = _parse_register_group(text, token.next_cursor, allow_empty=True)
    if destinations.error is not None:
        return _failure(state, destinations.error, AssemblyParserErrorCode.EXPECTED_REGISTER_GROUP)
    comma = _expect(text, destinations.cursor, AssemblyTokenKind.COMMA)
    if comma.error is not None:
        return _failure(state, comma.error, AssemblyParserErrorCode.EXPECTED_CALLEE)
    callee = _expect(text, comma.token.next_cursor, AssemblyTokenKind.IDENTIFIER)
    if callee.error is not None:
        return _failure(state, callee.error, AssemblyParserErrorCode.EXPECTED_CALLEE)
    operands = _count_trailing_operands(text, callee.token.next_cursor)
    if operands.error is not None:
        return _failure(state, operands.error, AssemblyParserErrorCode.UNSUPPORTED_SYNTAX)
    end_cursor = _line_end(text, operands.cursor)
    if end_cursor is None:
        return _failure_token(state, operands.last_token, AssemblyParserErrorCode.EXPECTED_NEWLINE)
    next_state = AssemblyParserState(
        state.phase,
        end_cursor,
        state.version,
        state.function_count,
        state.declaration_count,
        state.block_count,
        state.call_count + 1,
        state.return_count,
        state.current_result_width,
        max(state.max_result_width, destinations.width),
    )
    event = AssemblyParserEvent(
        AssemblyParserEventKind.CALL,
        SourceSpan(token.span.start, operands.last_token.span.end),
        end_cursor,
        version=state.version,
        result_width=destinations.width,
        operand_width=operands.width,
        discard_results=destinations.width == 0,
    )
    return AssemblyParserResult("event", next_state, event=event)


def _parse_return(
    text: BoundedText,
    state: AssemblyParserState,
    token: AssemblyToken,
) -> AssemblyParserResult:
    registers = _parse_register_group(text, token.next_cursor, allow_empty=False)
    if registers.error is not None:
        return _failure(state, registers.error, AssemblyParserErrorCode.EXPECTED_REGISTER_GROUP)
    end_cursor = _line_end(text, registers.cursor)
    if end_cursor is None:
        return _failure_token(state, registers.last_token, AssemblyParserErrorCode.EXPECTED_NEWLINE)
    next_state = AssemblyParserState(
        state.phase,
        end_cursor,
        state.version,
        state.function_count,
        state.declaration_count,
        state.block_count,
        state.call_count,
        state.return_count + 1,
        state.current_result_width,
        max(state.max_result_width, registers.width),
    )
    event = AssemblyParserEvent(
        AssemblyParserEventKind.RETURN,
        SourceSpan(token.span.start, registers.last_token.span.end),
        end_cursor,
        version=state.version,
        result_width=registers.width,
    )
    return AssemblyParserResult("event", next_state, event=event)


@dataclass(frozen=True, slots=True)
class _TokenResult:
    token: AssemblyToken | None = None
    error: AssemblyParserError | None = None


@dataclass(frozen=True, slots=True)
class _WidthResult:
    width: int
    cursor: TextCursor
    last_token: AssemblyToken
    error: AssemblyParserError | None = None


def _parse_type_group(text: BoundedText, cursor: TextCursor) -> _WidthResult:
    first = _next_token(text, cursor)
    if first.error is not None:
        return _WidthResult(0, cursor, _dummy_token(cursor), first.error)
    assert first.token is not None
    if first.token.kind is AssemblyTokenKind.LEFT_BRACKET:
        width = 0
        current = first.token.next_cursor
        last = first.token
        while True:
            item = _expect(text, current, AssemblyTokenKind.IDENTIFIER)
            if item.error is not None:
                return _WidthResult(0, current, last, item.error)
            width += 1
            last = item.token
            separator = _next_token(text, item.token.next_cursor)
            if separator.error is not None:
                return _WidthResult(0, item.token.next_cursor, last, separator.error)
            assert separator.token is not None
            if separator.token.kind is AssemblyTokenKind.RIGHT_BRACKET:
                return _WidthResult(width, separator.token.next_cursor, separator.token)
            if separator.token.kind is not AssemblyTokenKind.COMMA:
                return _WidthResult(0, separator.token.next_cursor, separator.token, _error_for_token(separator.token, AssemblyParserErrorCode.EXPECTED_TYPE_NAME))
            current = separator.token.next_cursor
    if first.token.kind is not AssemblyTokenKind.IDENTIFIER:
        return _WidthResult(0, first.token.next_cursor, first.token, _error_for_token(first.token, AssemblyParserErrorCode.EXPECTED_TYPE_NAME))
    return _WidthResult(1, first.token.next_cursor, first.token)


def _parse_register_group(
    text: BoundedText,
    cursor: TextCursor,
    *,
    allow_empty: bool,
) -> _WidthResult:
    first = _next_token(text, cursor)
    if first.error is not None:
        return _WidthResult(0, cursor, _dummy_token(cursor), first.error)
    assert first.token is not None
    if first.token.kind is AssemblyTokenKind.LEFT_BRACKET:
        current = first.token.next_cursor
        separator = _next_token(text, current)
        if separator.error is not None:
            return _WidthResult(0, current, first.token, separator.error)
        assert separator.token is not None
        if separator.token.kind is AssemblyTokenKind.RIGHT_BRACKET:
            if allow_empty:
                return _WidthResult(0, separator.token.next_cursor, separator.token)
            return _WidthResult(0, separator.token.next_cursor, separator.token, _error_for_token(separator.token, AssemblyParserErrorCode.EXPECTED_REGISTER_GROUP))
        width = 0
        last = first.token
        current = first.token.next_cursor
        while True:
            item = _expect(text, current, AssemblyTokenKind.REGISTER_NAME)
            if item.error is not None:
                return _WidthResult(0, current, last, item.error)
            width += 1
            last = item.token
            separator = _next_token(text, item.token.next_cursor)
            if separator.error is not None:
                return _WidthResult(0, item.token.next_cursor, last, separator.error)
            assert separator.token is not None
            if separator.token.kind is AssemblyTokenKind.RIGHT_BRACKET:
                return _WidthResult(width, separator.token.next_cursor, separator.token)
            if separator.token.kind is not AssemblyTokenKind.COMMA:
                return _WidthResult(0, separator.token.next_cursor, separator.token, _error_for_token(separator.token, AssemblyParserErrorCode.EXPECTED_REGISTER_GROUP))
            current = separator.token.next_cursor
    if first.token.kind is not AssemblyTokenKind.REGISTER_NAME:
        return _WidthResult(0, first.token.next_cursor, first.token, _error_for_token(first.token, AssemblyParserErrorCode.EXPECTED_REGISTER_GROUP))
    return _WidthResult(1, first.token.next_cursor, first.token)


def _count_trailing_operands(text: BoundedText, cursor: TextCursor) -> _WidthResult:
    current = cursor
    width = 0
    last = _dummy_token(cursor)
    while True:
        peek = _next_token(text, current)
        if peek.error is not None:
            return _WidthResult(width, current, last, peek.error)
        assert peek.token is not None
        if peek.token.kind in (AssemblyTokenKind.NEWLINE, AssemblyTokenKind.COMMENT):
            return _WidthResult(width, current, last)
        if peek.token.kind is AssemblyTokenKind.COMMA:
            item = _next_token(text, peek.token.next_cursor)
            if item.error is not None:
                return _WidthResult(width, peek.token.next_cursor, peek.token, item.error)
            assert item.token is not None
            if item.token.kind not in (AssemblyTokenKind.REGISTER_NAME, AssemblyTokenKind.INTEGER, AssemblyTokenKind.IDENTIFIER, AssemblyTokenKind.VALUE_NAME):
                return _WidthResult(width, item.token.next_cursor, item.token, _error_for_token(item.token, AssemblyParserErrorCode.UNSUPPORTED_SYNTAX))
            width += 1
            last = item.token
            current = item.token.next_cursor
            continue
        return _WidthResult(width, peek.token.next_cursor, peek.token, _error_for_token(peek.token, AssemblyParserErrorCode.UNSUPPORTED_SYNTAX))


def _expect(text: BoundedText, cursor: TextCursor, kind: AssemblyTokenKind) -> _TokenResult:
    result = _next_token(text, cursor)
    if result.error is not None:
        return result
    assert result.token is not None
    if result.token.kind is not kind:
        return _TokenResult(error=_error_for_token(result.token, AssemblyParserErrorCode.UNSUPPORTED_SYNTAX))
    return result


def _expect_directive(text: BoundedText, cursor: TextCursor, directive_id: int) -> _TokenResult:
    result = _expect(text, cursor, AssemblyTokenKind.DIRECTIVE)
    if result.error is not None:
        return result
    assert result.token is not None
    if result.token.scalar_value != directive_id:
        return _TokenResult(error=_error_for_token(result.token, AssemblyParserErrorCode.UNSUPPORTED_SYNTAX))
    return result


def _next_token(text: BoundedText, cursor: TextCursor) -> _TokenResult:
    result = next_assembly_token(text, cursor)
    if result.variant == "error":
        assert result.error is not None
        return _TokenResult(error=AssemblyParserError(AssemblyParserErrorCode.TOKEN_ERROR, result.error.span, result.error.detail, result.error))
    if result.variant == "end":
        end_cursor = result.cursor or cursor
        return _TokenResult(error=AssemblyParserError(AssemblyParserErrorCode.UNSUPPORTED_SYNTAX, SourceSpan(end_cursor.position, end_cursor.position)))
    assert result.token is not None
    if result.token.kind is AssemblyTokenKind.COMMENT:
        return _next_token(text, result.token.next_cursor)
    return _TokenResult(token=result.token)


def _skip_trivia(text: BoundedText, cursor: TextCursor) -> TextCursor:
    current = cursor
    while True:
        result = next_assembly_token(text, current)
        if result.variant == "token" and result.token is not None and result.token.kind in (AssemblyTokenKind.NEWLINE, AssemblyTokenKind.COMMENT):
            current = result.token.next_cursor
            continue
        return current


def _line_end(text: BoundedText, cursor: TextCursor) -> TextCursor | None:
    result = next_assembly_token(text, cursor)
    if result.variant == "end":
        return result.cursor
    if result.variant != "token" or result.token is None:
        return None
    if result.token.kind is AssemblyTokenKind.COMMENT:
        return _line_end(text, result.token.next_cursor)
    if result.token.kind is AssemblyTokenKind.NEWLINE:
        return result.token.next_cursor
    return None


def _failure(
    state: AssemblyParserState,
    error: AssemblyParserError,
    code: AssemblyParserErrorCode,
) -> AssemblyParserResult:
    return AssemblyParserResult(
        "error",
        state,
        error=AssemblyParserError(code, error.span, error.detail, error.token_error),
    )


def _failure_token(
    state: AssemblyParserState,
    token: AssemblyToken,
    code: AssemblyParserErrorCode,
) -> AssemblyParserResult:
    return AssemblyParserResult("error", state, error=_error_for_token(token, code))


def _error_for_token(token: AssemblyToken, code: AssemblyParserErrorCode) -> AssemblyParserError:
    return AssemblyParserError(code, token.span, token.scalar_value)


def _with_cursor(state: AssemblyParserState, cursor: TextCursor) -> AssemblyParserState:
    return AssemblyParserState(
        state.phase,
        cursor,
        state.version,
        state.function_count,
        state.declaration_count,
        state.block_count,
        state.call_count,
        state.return_count,
        state.current_result_width,
        state.max_result_width,
    )


def _dummy_token(cursor: TextCursor) -> AssemblyToken:
    return AssemblyToken(AssemblyTokenKind.NEWLINE, SourceSpan(cursor.position, cursor.position), cursor)


def _slice_ascii(text: BoundedText, start: int, end: int) -> str:
    return "".join(chr(text.units[index]) for index in range(start, end))


def _version_value(version: str) -> int:
    major, minor, patch = (int(part) for part in version.split("."))
    return major * 100 + minor * 10 + patch
