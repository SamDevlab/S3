from __future__ import annotations

import platform
from pathlib import Path

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.generic_syntax import IntegerPayload, NodeKind
from bootstrap.s3.frontend_token_arena import TokenArena
from bootstrap.s3.lexer import SyntaxMode, TokenKind
from bootstrap.s3.source_frontend import parse_source_to_syntax_independent


_ORDINARY_SOURCES = {
    0: "fn main\nreturn 0\n",
    1: "fn main()\nreturn 0\n",
    2: "fn entry()\nreturn 42\n",
    3: "fn worker()\nreturn 7\n",
}
_KIND_CODES = {
    TokenKind.FN: 2,
    TokenKind.IDENTIFIER: 1,
    TokenKind.RETURN: 3,
    TokenKind.INTEGER: 5,
    TokenKind.NEWLINE: 6,
    TokenKind.EOF: 0,
    TokenKind.LEFT_PAREN: 7,
    TokenKind.RIGHT_PAREN: 8,
}
_PARSER_SOURCES = {
    0: "fn entry() -> i64:\n    return 42\n",
    1: "fn worker() -> i64:\n    return 7\n",
}


def _candidate_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_lexer_native_case({case_id})\n"
    )


def _candidate_parser_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_native_parser_case({case_id})\n"
    )


def _independent_digest(source: str) -> int:
    arena = TokenArena.from_source_independent(
        source,
        mode=SyntaxMode.V0_6,
    )
    digest = 0
    for token_id in range(len(arena)):
        record = arena.token(token_id)
        digest += token_id * 3
        digest += _KIND_CODES[record.kind] * 5
        digest += record.span.start * 7
        digest += record.span.end * 11
    return digest


def _independent_parser_digest(source: str) -> int:
    parsed = parse_source_to_syntax_independent(source)
    arena = parsed.syntax_arena
    function = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.FUNCTION
    )
    return_node = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.RETURN
    )
    integer = next(
        node
        for _, node in arena.nodes.items()
        if node.kind is NodeKind.INTEGER_LITERAL
    )
    integer_payload = arena.payload(integer)
    assert isinstance(integer_payload, IntegerPayload)
    tokens = TokenArena.from_source_independent(source, mode=SyntaxMode.V0_6)
    name_token = next(
        token
        for _, token in tokens.tokens.items()
        if token.kind is TokenKind.IDENTIFIER and token.text != "i64"
    )
    name_digest = 0
    for unit in source[name_token.span.start:name_token.span.end].encode("utf-8"):
        name_digest = name_digest * 31 + unit
    native_token_count = len(tokens) - sum(
        token.kind in {TokenKind.INDENT, TokenKind.DEDENT}
        for _, token in tokens.tokens.items()
    ) + 1
    digest = name_digest * 11
    digest += name_token.span.start * 13
    digest += name_token.span.end * 17
    digest += return_node.span.start * 19
    digest += integer.span.start * 23
    digest += integer.span.end * 29
    digest += integer_payload.value * 31
    digest += native_token_count * 37
    assert function.span.start == 0
    return digest


@pytest.mark.parametrize(
    "case_id,expected_digest",
    ((0, 1509), (1, 2101), (2, 2285), (3, 2375)),
)
def test_ordinary_s3_lexer_slice_matches_independent_generic_frontend(
    case_id: int,
    expected_digest: int,
) -> None:
    expected = _independent_digest(_ORDINARY_SOURCES[case_id])
    assert expected == expected_digest
    assert run_source(_candidate_source(case_id)) == expected


@pytest.mark.s3_native
def test_ordinary_s3_lexer_slice_qualifies_on_linux_x86_64(
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("ordinary S3 lexer qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    for case_id, expected_digest in (
        (0, 1509),
        (1, 2101),
        (2, 2285),
        (3, 2375),
    ):
        compilation = compile_source(_candidate_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-lexer-slice-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == f"program returned: {expected_digest}\n"
        assert completed.stderr == ""


@pytest.mark.parametrize(
    "case_id,expected_digest",
    ((0, 1063349395), (1, 38641705493)),
)
def test_native_parser_minimal_function_matches_independent_syntax_oracle(
    case_id: int,
    expected_digest: int,
) -> None:
    expected = _independent_parser_digest(_PARSER_SOURCES[case_id])
    assert expected == expected_digest
    assert run_source(_candidate_parser_source(case_id)) == expected


@pytest.mark.parametrize("case_id", (2, 3))
def test_native_parser_minimal_function_rejects_malformed_input(case_id: int) -> None:
    assert run_source(_candidate_parser_source(case_id)) == -1


def test_native_parser_slice_has_no_reference_frontend_fallback() -> None:
    source = _candidate_parser_source(0)
    for forbidden in (
        "GenericLexer(",
        "GenericParser(",
        "tokenize(",
        "parse_tokens(",
        "bootstrap.s3.ast",
    ):
        assert forbidden not in source


@pytest.mark.s3_native
def test_native_parser_minimal_function_qualifies_on_linux_x86_64(
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("ordinary S3 parser qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    for case_id, expected_digest in ((0, 1063349395), (1, 38641705493)):
        compilation = compile_source(_candidate_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-parser-slice-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == f"program returned: {expected_digest}\n"
        assert completed.stderr == ""

    for case_id in (2, 3):
        compilation = compile_source(_candidate_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-parser-slice-negative-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: -1\n"
        assert completed.stderr == ""
