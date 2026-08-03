"""Experimental bounded Assembly frontend candidate.

This module composes the 1.14 tokenizer and 1.15 parser kernel into a small
summary-producing frontend. It is not the default Assembly parser.
"""

from __future__ import annotations

from dataclasses import dataclass

from .assembly_parser_kernel import (
    AssemblyParserError,
    AssemblyParserEventKind,
    AssemblyParserResult,
    initial_parser_state,
    next_assembly_event,
)
from .bounded_text import BoundedText


@dataclass(frozen=True, slots=True)
class AssemblyFrontendSummary:
    version: int
    function_count: int
    declaration_count: int
    block_count: int
    call_count: int
    return_count: int
    max_result_width: int
    ended: bool


@dataclass(frozen=True, slots=True)
class AssemblyFrontendResult:
    variant: str
    summary: AssemblyFrontendSummary | None = None
    error: AssemblyParserError | None = None
    parser_result: AssemblyParserResult | None = None


def analyze_bounded_assembly(text: BoundedText) -> AssemblyFrontendResult:
    state = initial_parser_state()
    ended = False
    while True:
        result = next_assembly_event(text, state)
        if result.variant == "error":
            return AssemblyFrontendResult(
                "error",
                error=result.error,
                parser_result=result,
            )
        if result.variant == "end":
            summary = AssemblyFrontendSummary(
                state.version,
                state.function_count,
                state.declaration_count,
                state.block_count,
                state.call_count,
                state.return_count,
                state.max_result_width,
                ended,
            )
            return AssemblyFrontendResult("summary", summary=summary, parser_result=result)
        assert result.event is not None
        state = result.state
        if result.event.kind is AssemblyParserEventKind.END_FUNCTION:
            ended = True
