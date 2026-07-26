from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_single_bound_range() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(5):\n"
        "        total += i\n"
        "    return total\n"
    )
    assert _execute(source) == 10


def test_execution_single_bound_range_with_len() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[4] = [10, 20, 30, 40]\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(len(values)):\n"
        "        total += values[i]\n"
        "    return total\n"
    )
    assert _execute(source) == 100
