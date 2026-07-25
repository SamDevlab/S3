from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_discard_with_side_effect() -> None:
    source = (
        "fn bump(val: tryte) -> tryte:\n"
        "    return val + 1\n"
        "fn main() -> tryte:\n"
        "    mut state: tryte = 0\n"
        "    discard bump(state)\n"
        "    state += 2\n"
        "    discard bump(state)\n"
        "    return state\n"
    )
    assert _execute(source) == 2
