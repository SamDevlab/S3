from __future__ import annotations

from pathlib import Path

from bootstrap.s3.assembly_frontend_candidate import analyze_bounded_assembly
from bootstrap.s3.assembly_parser_kernel import AssemblyParserErrorCode
from bootstrap.s3.bounded_text import BoundedText, encode_ascii


COVERAGE_STATUS = "CREATED — NOT EXECUTED UNTIL MILESTONE 1.16 IMPLEMENTATION COMPLETION"

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_TYPES_SOURCE = (
    ROOT / "selfhost/assembly/frontend_types.s3"
).read_text(encoding="utf-8")
FRONTEND_SOURCE = (
    ROOT / "selfhost/assembly/assembly_frontend.s3"
).read_text(encoding="utf-8")


VALID_FRONTEND_ASSEMBLY = """.s3asm 0.6.0

.function main -> [tryte, trit]
    .register r0, tryte
    .register r1, trit
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


def test_tests_are_created_but_not_part_of_final_campaign_validation() -> None:
    assert COVERAGE_STATUS == (
        "CREATED — NOT EXECUTED UNTIL MILESTONE 1.16 IMPLEMENTATION COMPLETION"
    )


def test_python_frontend_candidate_summarizes_bounded_assembly() -> None:
    result = analyze_bounded_assembly(_encoded(VALID_FRONTEND_ASSEMBLY))

    assert result.variant == "summary"
    assert result.summary is not None
    assert result.summary.version == 60
    assert result.summary.function_count == 1
    assert result.summary.declaration_count == 2
    assert result.summary.block_count == 1
    assert result.summary.call_count == 1
    assert result.summary.return_count == 1
    assert result.summary.max_result_width == 2
    assert result.summary.ended is True


def test_python_frontend_candidate_returns_structured_parser_error() -> None:
    result = analyze_bounded_assembly(_encoded(".s3asm 0.8.0\n"))

    assert result.variant == "error"
    assert result.error is not None
    assert result.error.code is AssemblyParserErrorCode.UNSUPPORTED_VERSION
    assert result.parser_result is not None
    assert result.parser_result.variant == "error"


def test_s3_frontend_sources_are_available_for_deferred_differential_coverage() -> None:
    assert "export fn analyze_bounded_assembly" in FRONTEND_SOURCE
    assert "export enum AssemblyFrontendResult" in FRONTEND_TYPES_SOURCE
    assert "AssemblyFrontendSummary" in FRONTEND_TYPES_SOURCE
    assert "next_assembly_parser_event" in FRONTEND_SOURCE
