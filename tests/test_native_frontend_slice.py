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


_ORDINARY_SOURCE = "fn main\nreturn 0\n"
_KIND_CODES = {
    TokenKind.FN: 2,
    TokenKind.IDENTIFIER: 1,
    TokenKind.RETURN: 3,
    TokenKind.INTEGER: 5,
    TokenKind.NEWLINE: 6,
    TokenKind.EOF: 0,
}


def _candidate_source() -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return substrate + "\nfn main() -> i64:\n    return generic_lexer_native_case(0)\n"


def _independent_digest() -> int:
    arena = TokenArena.from_source_independent(
        _ORDINARY_SOURCE,
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


def test_ordinary_s3_lexer_slice_matches_independent_generic_frontend() -> None:
    expected = _independent_digest()
    assert expected == 1509
    assert run_source(_candidate_source()) == expected


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

    compilation = compile_source(_candidate_source())
    executable = toolchain.build(
        generate_native_assembly(compilation.assembly),
        tmp_path / "ordinary-s3-lexer-slice",
    )
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stdout == "program returned: 1509\n"
    assert completed.stderr == ""
