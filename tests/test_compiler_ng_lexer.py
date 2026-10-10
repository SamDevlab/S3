from __future__ import annotations

import json
from pathlib import Path

import pytest

from bootstrap.s3 import compile_source
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.lexer import Lexer, SyntaxMode


_ROOT = Path(__file__).parents[1]


def _module_body(relative_path: str) -> str:
    return "\n".join(
        line
        for line in (_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
        if not line.startswith("module ") and not line.startswith("from ")
    )


_LEXER_SOURCE = "\n".join(
    (
        _module_body("selfhost/compiler_ng/character_classes.s3"),
        _module_body("selfhost/compiler_ng/lexer.s3"),
    )
)

_PAIR_KINDS = {
    "->": 201,
    "<=>": 202,
    "==": 203,
    "!=": 204,
    "<=": 205,
    ">=": 206,
    "+=": 207,
    "*=": 208,
}


def _python_tokens(source: str) -> tuple[tuple[int, int, int], ...]:
    tokens: list[tuple[int, int, int]] = []
    for token in Lexer(source, mode=SyntaxMode.V0_5).tokenize():
        if token.kind.name == "EOF":
            kind = 0
        elif token.text.isidentifier():
            kind = 1
        elif token.kind.name == "INTEGER":
            kind = 2
        elif token.kind.name == "STRING_LITERAL":
            kind = 3
        elif token.text in _PAIR_KINDS:
            kind = _PAIR_KINDS[token.text]
        else:
            kind = 300 + ord(token.text)
        end = token.position + len(token.text)
        if token.kind.name == "EOF":
            end = len(source)
        tokens.append((kind, token.position, end))
    return tuple(tokens)


def _nextgen_conformance_result(source: str, expected: tuple[tuple[int, int, int], ...]) -> int:
    expected_vectors = []
    for label, column in (
        ("expected_kinds", 0),
        ("expected_starts", 1),
        ("expected_ends", 2),
    ):
        values = [entry[column] for entry in expected]
        pushes = "\n".join(
            f"    discard vector_push<i64>(&mut {label}, {value})"
            for value in values
        )
        expected_vectors.append(
            f"    mut {label}: vector<i64> = vector_new<i64>({len(values)})\n{pushes}"
        )
    indents = []
    for _, start, _ in expected:
        line_start = source.rfind("\n", 0, start) + 1
        line_end = source.find("\n", line_start)
        if line_end < 0:
            line_end = len(source)
        indent = 0
        for character in source[line_start:line_end]:
            if character == " ":
                indent += 1
            elif character == "\t":
                indent = -1
                break
            else:
                break
        indents.append(indent)
    indent_pushes = "\n".join(
        f"    discard vector_push<i64>(&mut expected_indents, {value})" for value in indents
    )
    expected_vectors.append(
        f"    mut expected_indents: vector<i64> = vector_new<i64>({len(indents)})\n{indent_pushes}"
    )
    wrapper = f"""
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>(32)
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
{expected_vectors[0]}
{expected_vectors[1]}
{expected_vectors[2]}
{expected_vectors[3]}
    match status <=> 0:
        -1:
            return -1000
        0:
            mut index: i64 = 0
            match vector_len<NgToken>(&tokens) <=> vector_len<i64>(&expected_kinds):
                -1:
                    return -1001
                0:
                    index = 0
                1:
                    return -1001
            while index < vector_len<i64>(&expected_kinds):
                mut token: NgToken = vector_get<NgToken>(&tokens, index)
                match token.kind <=> vector_get<i64>(&expected_kinds, index):
                    -1:
                        return 1000 + index
                    0:
                        index = index
                    1:
                        return 1000 + index
                match token.start <=> vector_get<i64>(&expected_starts, index):
                    -1:
                        return 2000 + index
                    0:
                        index = index
                    1:
                        return 2000 + index
                match token.end <=> vector_get<i64>(&expected_ends, index):
                    -1:
                        return 3000 + index
                    0:
                        status = status
                    1:
                        return 3000 + index
                match token.indent <=> vector_get<i64>(&expected_indents, index):
                    -1:
                        return 4000 + index
                    0:
                        index = index + 1
                    1:
                        return 4000 + index
            return 0
        1:
            return -1000
"""
    compilation = compile_source(_LEXER_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    return int(execute_ir(compilation.ir))


def _nextgen_rejects(source: str) -> bool:
    wrapper = f"""
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(source, ensure_ascii=False)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>(32)
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
    match status <=> 0:
        -1:
            return 1
        0:
            return 0
        1:
            return 1
"""
    compilation = compile_source(_LEXER_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    return int(execute_ir(compilation.ir)) == 1


@pytest.mark.parametrize(
    "source",
    [
        "fn add(left: i64, right: i64) -> i64:\n    return left + right\n",
        "fn count() -> i64:\n    return 12 // ignored words 99\n",
        "fn compare(value: i64) -> trit: return value <=> 0",
    ],
)
def test_nextgen_runtime_lexer_matches_reference_subset(source: str) -> None:
    assert _nextgen_conformance_result(source, _python_tokens(source)) == 0


def test_nextgen_runtime_lexer_matches_all_multi_byte_symbols() -> None:
    source = "-> <=> == != <= >= += *= ( ) [ ] { } , : ; + - * / < = >"

    assert _nextgen_conformance_result(source, _python_tokens(source)) == 0


def test_nextgen_runtime_lexer_records_line_indentation_once() -> None:
    source = "alpha\n    beta + gamma\n    // comment\n  omega"

    assert _nextgen_conformance_result(source, _python_tokens(source)) == 0


def test_nextgen_runtime_lexer_preserves_indentation_after_multiline_string() -> None:
    source = 'alpha\n    "first line\n  second line"\n  omega'
    string_start = source.index('"')
    string_end = source.index('"', string_start + 1) + 1
    omega_start = source.index("omega")
    expected = (
        (1, 0, 5),
        (3, string_start, string_end),
        (1, omega_start, omega_start + 5),
        (0, len(source), len(source)),
    )

    assert _nextgen_conformance_result(source, expected) == 0


def test_nextgen_ascii_classifiers_match_reference_ranges() -> None:
    wrapper = """
fn main() -> vector<i64>:
    mut result: vector<i64> = vector_new<i64>(512)
    mut unit: i64 = 0
    while unit < 128:
        discard vector_push<i64>(&mut result, to_i64(ng_is_alpha(unit)))
        discard vector_push<i64>(&mut result, to_i64(ng_is_space(unit)))
        discard vector_push<i64>(&mut result, to_i64(ng_is_identifier_start(unit)))
        discard vector_push<i64>(&mut result, to_i64(ng_is_identifier_continue(unit)))
        unit = unit + 1
    return result
"""
    compilation = compile_source(_LEXER_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    actual = [int(value) for value in execute_ir(compilation.ir)]
    expected = []
    for unit in range(128):
        is_alpha = 65 <= unit <= 90 or 97 <= unit <= 122
        expected.extend(
            (
                -1 if is_alpha else 0,
                -1 if unit in {9, 10, 13, 32} else 0,
                -1 if is_alpha or unit == 95 else 0,
                -1 if is_alpha or unit == 95 or 48 <= unit <= 57 else 0,
            )
        )
    assert actual == expected


def test_nextgen_character_class_table_matches_all_byte_values() -> None:
    wrapper = """
fn main() -> vector<i64>:
    mut classes: vector<i64> = vector_new<i64>(256)
    mut result: vector<i64> = vector_new<i64>(256)
    mut unit: i64 = 0
    discard ng_build_character_class_table(&mut classes)
    while unit < 256:
        discard vector_push<i64>(&mut result, vector_get<i64>(&classes, unit))
        unit = unit + 1
    return result
"""
    compilation = compile_source(_LEXER_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    actual = [int(value) for value in execute_ir(compilation.ir)]
    expected = []
    for unit in range(256):
        is_digit = 48 <= unit <= 57
        is_alpha = 65 <= unit <= 90 or 97 <= unit <= 122
        if is_digit:
            expected.append(1)
        elif is_alpha:
            expected.append(2)
        elif unit == 95:
            expected.append(3)
        elif unit in {9, 10, 13, 32}:
            expected.append(4)
        elif unit == 35:
            expected.append(5)
        elif unit == 47:
            expected.append(6)
        elif unit == 34:
            expected.append(7)
        elif unit in {33, 42, 43, 45, 60, 61, 62}:
            expected.append(8)
        elif unit < 128:
            expected.append(9)
        else:
            expected.append(10)
    assert actual == expected


def test_nextgen_span_fingerprint_distinguishes_interior_bytes() -> None:
    wrapper = """
fn main() -> vector<i64>:
    mut source_text: text = text_from_static("parser pester pasper paszxr")
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut result: vector<i64> = vector_new<i64>(4)
    discard vector_push<i64>(&mut result, ng_span_fingerprint(&source_bytes, 0, 6))
    discard vector_push<i64>(&mut result, ng_span_fingerprint(&source_bytes, 7, 13))
    discard vector_push<i64>(&mut result, ng_span_fingerprint(&source_bytes, 14, 20))
    discard vector_push<i64>(&mut result, ng_span_fingerprint(&source_bytes, 21, 27))
    return result
"""
    compilation = compile_source(_LEXER_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    first, second, different_interior, different_penultimate = map(
        int, execute_ir(compilation.ir)
    )

    assert first != second
    assert first != different_interior
    assert first != different_penultimate


def test_nextgen_short_span_fingerprint_covers_every_byte() -> None:
    wrapper = """
fn main() -> vector<i64>:
    mut source_text: text = text_from_static("abcdef abXdef")
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut result: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut result, ng_span_fingerprint(&source_bytes, 0, 6))
    discard vector_push<i64>(&mut result, ng_span_fingerprint(&source_bytes, 7, 13))
    return result
"""
    compilation = compile_source(_LEXER_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    first, changed_at_unsampled_index = map(int, execute_ir(compilation.ir))

    assert first != changed_at_unsampled_index


def test_nextgen_runtime_lexer_fails_closed_on_unterminated_string() -> None:
    source = "fn broken() -> i64: return \"unterminated"
    assert _nextgen_rejects(source)


def test_nextgen_runtime_lexer_fails_closed_on_non_ascii_symbol() -> None:
    assert _nextgen_rejects("fn main() -> i64: return §")
