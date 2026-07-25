from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_len_tryte_array() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[7] = [10, 20, 30, 40, 50, 60, 70]\n"
        "    return len(values)\n"
    )
    assert _execute(source) == 7


def test_execution_len_trit_array() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    flags: trit[4] = [-1, 0, 1, -1]\n"
        "    return len(flags)\n"
    )
    assert _execute(source) == 4


def test_execution_len_for_loop_range_summation() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[5] = [2, 4, 6, 8, 10]\n"
        "    mut sum: tryte = 0\n"
        "    for i: tryte in range(0, len(values)):\n"
        "        sum = sum + values[i]\n"
        "    return sum\n"
    )
    # 2 + 4 + 6 + 8 + 10 = 30
    assert _execute(source) == 30


def test_execution_len_arithmetic() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[3] = [1, 2, 3]\n"
        "    return len(values) + 10\n"
    )
    assert _execute(source) == 13


def test_execution_len_in_match() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
        "    match len(values) <=> 5:\n"
        "        -1:\n"
        "            return -1\n"
        "        0:\n"
        "            return 42\n"
        "        1:\n"
        "            return 1\n"
    )
    assert _execute(source) == 42
