from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_execution_while_false() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 100\n"
        "    while 0:\n"
        "        a = a + 50\n"
        "    return a\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 100


def test_execution_match_statement_constant_selector() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut res: tryte = 0\n"
        "    match 1:\n"
        "        -1:\n"
        "            res = 10\n"
        "        0:\n"
        "            res = 20\n"
        "        1:\n"
        "            res = 30\n"
        "    return res\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 30


def test_execution_match_expression_constant_selector() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    val: tryte = match -1:\n"
        "        -1: 100\n"
        "        0: 200\n"
        "        1: 300\n"
        "    return val\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 100
