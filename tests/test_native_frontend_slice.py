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
from bootstrap.s3.frontend_token_arena import TokenArena
from bootstrap.s3.lexer import SyntaxMode, TokenKind


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


def _candidate_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_lexer_native_case({case_id})\n"
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
