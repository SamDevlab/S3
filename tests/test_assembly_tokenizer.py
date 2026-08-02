from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bootstrap.s3.assembly_tokenizer import (
    AssemblyTokenErrorCode,
    AssemblyTokenKind,
    next_assembly_token,
)
from bootstrap.s3.bounded_text import (
    BOUNDED_TEXT_CAPACITY,
    BoundedText,
    TextCursor,
    encode_ascii,
)
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_sources


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


@dataclass(frozen=True, slots=True)
class ExpectedToken:
    text: str
    cursor: int
    kind: AssemblyTokenKind
    start: int
    end: int
    next_cursor: int
    scalar_value: int = 0


@dataclass(frozen=True, slots=True)
class ExpectedError:
    text: str
    cursor: int
    code: AssemblyTokenErrorCode
    start: int
    end: int
    detail: int = 0


TOKEN_CASES = (
    ExpectedToken(".s3asm", 0, AssemblyTokenKind.VERSION_DIRECTIVE, 0, 6, 6),
    ExpectedToken("  .s3asm 0.6.0", 0, AssemblyTokenKind.VERSION_DIRECTIVE, 2, 8, 8),
    ExpectedToken("0.6.0", 0, AssemblyTokenKind.VERSION_NUMBER, 0, 5, 5, 60),
    ExpectedToken("0.5.0", 0, AssemblyTokenKind.VERSION_NUMBER, 0, 5, 5, 50),
    ExpectedToken(".function main", 0, AssemblyTokenKind.DIRECTIVE, 0, 9, 9, 1),
    ExpectedToken("main", 0, AssemblyTokenKind.IDENTIFIER, 0, 4, 4),
    ExpectedToken("tryte", 0, AssemblyTokenKind.IDENTIFIER, 0, 5, 5),
    ExpectedToken("r12", 0, AssemblyTokenKind.REGISTER_NAME, 0, 3, 3, 12),
    ExpectedToken("m3", 0, AssemblyTokenKind.VALUE_NAME, 0, 2, 2, 3),
    ExpectedToken("entry:", 0, AssemblyTokenKind.IDENTIFIER, 0, 5, 5),
    ExpectedToken("TCALL", 0, AssemblyTokenKind.IDENTIFIER, 0, 5, 5),
    ExpectedToken("TRET", 0, AssemblyTokenKind.IDENTIFIER, 0, 4, 4),
    ExpectedToken("TCONST", 0, AssemblyTokenKind.IDENTIFIER, 0, 6, 6),
    ExpectedToken("0", 0, AssemblyTokenKind.INTEGER, 0, 1, 1, 0),
    ExpectedToken("364", 0, AssemblyTokenKind.INTEGER, 0, 3, 3, 364),
    ExpectedToken("-364", 0, AssemblyTokenKind.INTEGER, 0, 4, 4, -364),
    ExpectedToken(":", 0, AssemblyTokenKind.COLON, 0, 1, 1),
    ExpectedToken(",", 0, AssemblyTokenKind.COMMA, 0, 1, 1),
    ExpectedToken("=", 0, AssemblyTokenKind.EQUALS, 0, 1, 1),
    ExpectedToken("[", 0, AssemblyTokenKind.LEFT_BRACKET, 0, 1, 1),
    ExpectedToken("]", 0, AssemblyTokenKind.RIGHT_BRACKET, 0, 1, 1),
    ExpectedToken("(", 0, AssemblyTokenKind.LEFT_PARENTHESIS, 0, 1, 1),
    ExpectedToken(")", 0, AssemblyTokenKind.RIGHT_PARENTHESIS, 0, 1, 1),
    ExpectedToken("\n", 0, AssemblyTokenKind.NEWLINE, 0, 1, 1),
    ExpectedToken("\r\n", 0, AssemblyTokenKind.NEWLINE, 0, 2, 2),
    ExpectedToken("; source=1:2:3\n", 0, AssemblyTokenKind.COMMENT, 0, 14, 14),
    ExpectedToken("TRET r0", 5, AssemblyTokenKind.REGISTER_NAME, 5, 7, 7, 0),
)

ERROR_CASES = (
    ExpectedError(".", 0, AssemblyTokenErrorCode.TRUNCATED_TOKEN, 0, 1, 46),
    ExpectedError(".s3", 0, AssemblyTokenErrorCode.TRUNCATED_TOKEN, 0, 3, 46),
    ExpectedError(".unknown", 0, AssemblyTokenErrorCode.INVALID_DIRECTIVE, 0, 8, 46),
    ExpectedError("365", 0, AssemblyTokenErrorCode.INTEGER_OVERFLOW, 0, 3, 364),
    ExpectedError("-365", 0, AssemblyTokenErrorCode.INTEGER_OVERFLOW, 0, 4, 364),
    ExpectedError("-", 0, AssemblyTokenErrorCode.MALFORMED_INTEGER, 0, 1, 45),
    ExpectedError("12abc", 0, AssemblyTokenErrorCode.MALFORMED_INTEGER, 0, 5, 97),
    ExpectedError("@", 0, AssemblyTokenErrorCode.UNEXPECTED_CODE_UNIT, 0, 1, 64),
    ExpectedError('"literal"', 0, AssemblyTokenErrorCode.UNSUPPORTED_TOKEN, 0, 1, 34),
    ExpectedError("\r", 0, AssemblyTokenErrorCode.TRUNCATED_TOKEN, 0, 1, 13),
    ExpectedError("x", 2, AssemblyTokenErrorCode.CURSOR_OUT_OF_BOUNDS, 1, 1, 2),
)


def _encoded(value: str) -> BoundedText:
    result = encode_ascii(value)
    assert result.error is None
    assert result.text is not None
    return result.text


def _units_literal(value: str) -> str:
    units = [*(ord(character) for character in value)]
    units.extend(0 for _ in range(BOUNDED_TEXT_CAPACITY - len(units)))
    return "[" + ", ".join(str(unit) for unit in units) + "]"


def _s3_sources(main_source: str) -> dict[str, str]:
    return {
        "bounded_text_types.s3": BOUNDED_TYPES_SOURCE,
        "selfhost/assembly/tokenizer_types.s3": TOKENIZER_TYPES_SOURCE,
        "selfhost/assembly/assembly_tokenizer.s3": TOKENIZER_SOURCE,
        "main.s3": main_source,
    }


def _program_for_token_case(case: ExpectedToken) -> str:
    return (
        "module main\n"
        "from bounded_text_types import BoundedText\n"
        "from bounded_text_types import TextCursor\n"
        "from selfhost.assembly.tokenizer_types import AssemblyTokenResult\n"
        "from selfhost.assembly.assembly_tokenizer import next_assembly_token\n"
        "fn diff(actual: tryte, expected: tryte, code: tryte) -> tryte:\n"
        "    match actual <=> expected:\n"
        "        0:\n"
        "            return 0\n"
        "        -1:\n"
        "            return code\n"
        "        1:\n"
        "            return code\n"
        "fn main() -> tryte:\n"
        f"    units: tryte[364] = {_units_literal(case.text)}\n"
        f"    text: BoundedText = BoundedText(length={len(case.text)}, units=units)\n"
        f"    result: AssemblyTokenResult = next_assembly_token(text, TextCursor(position={case.cursor}))\n"
        "    match result:\n"
        "        AssemblyTokenResult.Token(resultToken):\n"
        "            mut status: tryte = 0\n"
        f"            status = status + diff(resultToken.kind, {int(case.kind)}, -1)\n"
        f"            status = status + diff(resultToken.span.start, {case.start}, -2)\n"
        f"            status = status + diff(resultToken.span.end, {case.end}, -3)\n"
        f"            status = status + diff(resultToken.next_cursor.position, {case.next_cursor}, -4)\n"
        f"            status = status + diff(resultToken.scalar_value, {case.scalar_value}, -5)\n"
        "            match status <=> 0:\n"
        "                0:\n"
        "                    return 1\n"
        "                -1:\n"
        "                    return status\n"
        "                1:\n"
        "                    return status\n"
        "        AssemblyTokenResult.End(cursor):\n"
        "            return -6\n"
        "        AssemblyTokenResult.Error(resultError):\n"
        "            return 0 - resultError.code\n"
    )


def _program_for_error_case(case: ExpectedError) -> str:
    return (
        "module main\n"
        "from bounded_text_types import BoundedText\n"
        "from bounded_text_types import TextCursor\n"
        "from selfhost.assembly.tokenizer_types import AssemblyTokenResult\n"
        "from selfhost.assembly.assembly_tokenizer import next_assembly_token\n"
        "fn diff(actual: tryte, expected: tryte, code: tryte) -> tryte:\n"
        "    match actual <=> expected:\n"
        "        0:\n"
        "            return 0\n"
        "        -1:\n"
        "            return code\n"
        "        1:\n"
        "            return code\n"
        "fn main() -> tryte:\n"
        f"    units: tryte[364] = {_units_literal(case.text)}\n"
        f"    text: BoundedText = BoundedText(length={len(case.text)}, units=units)\n"
        f"    result: AssemblyTokenResult = next_assembly_token(text, TextCursor(position={case.cursor}))\n"
        "    match result:\n"
        "        AssemblyTokenResult.Token(resultToken):\n"
        "            return -1\n"
        "        AssemblyTokenResult.End(cursor):\n"
        "            return -2\n"
        "        AssemblyTokenResult.Error(resultError):\n"
        "            mut status: tryte = 0\n"
        f"            status = status + diff(resultError.code, {int(case.code)}, -3)\n"
        f"            status = status + diff(resultError.span.start, {case.start}, -4)\n"
        f"            status = status + diff(resultError.span.end, {case.end}, -5)\n"
        f"            status = status + diff(resultError.detail, {case.detail}, -6)\n"
        "            match status <=> 0:\n"
        "                0:\n"
        "                    return 1\n"
        "                -1:\n"
        "                    return status\n"
        "                1:\n"
        "                    return status\n"
    )


def _execute(source: str, optimization: str) -> int:
    compilation = compile_sources(_s3_sources(source), optimization)
    return Emulator(max_memory_trits=32_768).execute(compilation.assembly)


def test_python_reference_manual_token_corpus() -> None:
    for case in TOKEN_CASES:
        result = next_assembly_token(_encoded(case.text), TextCursor(case.cursor))
        assert result.variant == "token", case
        assert result.token is not None
        assert result.token.kind is case.kind
        assert result.token.span.start == case.start
        assert result.token.span.end == case.end
        assert result.token.next_cursor.position == case.next_cursor
        assert result.token.scalar_value == case.scalar_value


def test_python_reference_manual_error_corpus() -> None:
    for case in ERROR_CASES:
        result = next_assembly_token(_encoded(case.text), TextCursor(case.cursor))
        assert result.variant == "error", case
        assert result.error is not None
        assert result.error.code is case.code
        assert result.error.span.start == case.start
        assert result.error.span.end == case.end
        assert result.error.detail == case.detail


def test_python_reference_end_of_input_and_repeated_calls() -> None:
    text = _encoded(" \t")
    cursor = TextCursor(0)
    first = next_assembly_token(text, cursor)
    second = next_assembly_token(text, cursor)

    assert first == second
    assert first.variant == "end"
    assert first.cursor == TextCursor(2)


def test_s3_tokenizer_matches_manual_token_corpus_o0_o1() -> None:
    for case in TOKEN_CASES:
        source = _program_for_token_case(case)
        assert _execute(source, "O0") == 1, case
        assert _execute(source, "O1") == 1, case


def test_s3_tokenizer_matches_manual_error_corpus_o0_o1() -> None:
    for case in ERROR_CASES:
        source = _program_for_error_case(case)
        assert _execute(source, "O0") == 1, case
        assert _execute(source, "O1") == 1, case


def test_s3_tokenizer_source_unit_permutations_are_deterministic() -> None:
    source = _program_for_token_case(
        ExpectedToken("TCALL [r1, r2]", 0, AssemblyTokenKind.IDENTIFIER, 0, 5, 5)
    )
    forward = tuple(_s3_sources(source).items())
    backward = tuple(reversed(forward))

    assert compile_sources(forward, "O0").ir.to_dict() == compile_sources(
        backward,
        "O0",
    ).ir.to_dict()
