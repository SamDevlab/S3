from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_execution_constant_if_true() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut res: tryte = 0\n"
        "    match -1:\n"
        "        -1:\n"
        "            res = 42\n"
        "        else:\n"
        "            res = 99\n"
        "    return res\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 42


def test_execution_constant_if_false() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut res: tryte = 0\n"
        "    match 0:\n"
        "        -1:\n"
        "            res = 42\n"
        "        else:\n"
        "            res = 99\n"
        "    return res\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 99
