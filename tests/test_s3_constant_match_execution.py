from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_execution_constant_match_statement_fallback() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut res: tryte = 0\n"
        "    match 1:\n"
        "        -1:\n"
        "            res = 10\n"
        "        0:\n"
        "            res = 20\n"
        "        else:\n"
        "            res = 99\n"
        "    return res\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 99


def test_execution_constant_match_expression() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    res: tryte = match 0:\n"
        "        -1: 10\n"
        "        0: 20\n"
        "        1: 30\n"
        "    return res\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 20
