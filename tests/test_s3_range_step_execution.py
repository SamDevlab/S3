from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_stepped_range_positive() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(0, 10, 2):\n"
        "        total += i\n"
        "    return total\n"
    )
    # i = 0, 2, 4, 6, 8 -> sum = 20
    assert _execute(source) == 20


def test_execution_stepped_range_negative() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(5, -1, -1):\n"
        "        total += i\n"
        "    return total\n"
    )
    # i = 5, 4, 3, 2, 1, 0 -> sum = 15
    assert _execute(source) == 15
