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
    wrapper = f"""
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>(32)
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
{expected_vectors[0]}
{expected_vectors[1]}
{expected_vectors[2]}
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
                        return index + 1
                    0:
                        index = index
                    1:
                        return index + 1
                match token.start <=> vector_get<i64>(&expected_starts, index):
                    -1:
                        return index + 1
                    0:
                        index = index
                    1:
                        return index + 1
                match token.end <=> vector_get<i64>(&expected_ends, index):
                    -1:
                        return index + 1
                    0:
                        index = index + 1
                    1:
                        return index + 1
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
    mut source_text: text = text_from_static({json.dumps(source)})
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


def test_nextgen_runtime_lexer_fails_closed_on_unterminated_string() -> None:
    source = "fn broken() -> i64: return \"unterminated"
    assert _nextgen_rejects(source)
