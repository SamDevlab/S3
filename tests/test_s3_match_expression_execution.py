from __future__ import annotations

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


@pytest.mark.parametrize(
    ("sel", "expected"),
    [
        (-1, 100),
        (0, 200),
        (1, 300),
    ],
)
def test_match_expression_execution_all_branches(sel: int, expected: int) -> None:
    source = (
        f"fn main() -> tryte:\n"
        f"    mut s: trit = {sel}\n"
        f"    return match s:\n"
        f"        -1: 100\n"
        f"        0: 200\n"
        f"        1: 300\n"
    )
    assert _execute(source) == expected


def test_match_expression_execution_trit_result() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut s: trit = 1\n"
        "    mut res: trit = match s:\n"
        "        -1: 1\n"
        "        0: 0\n"
        "        1: -1\n"
        "    match res:\n"
        "        -1:\n"
        "            return -1\n"
        "        0:\n"
        "            return 0\n"
        "        1:\n"
        "            return 1\n"
    )
    assert _execute(source) == -1


def test_match_expression_nested_execution() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: trit = 0\n"
        "    mut b: trit = -1\n"
        "    return match a:\n"
        "        -1: 10\n"
        "        0: match b:\n"
        "            -1: 20\n"
        "            0: 30\n"
        "            1: 40\n"
        "        1: 50\n"
    )
    assert _execute(source) == 20


def test_match_expression_lazy_evaluation_unselected_arms_not_executed() -> None:
    source = (
        "fn inf(n: tryte) -> tryte:\n"
        "    return inf(n + 1)\n"
        "\n"
        "fn main() -> tryte:\n"
        "    mut sel: trit = -1\n"
        "    val: tryte = match sel:\n"
        "        -1: 42\n"
        "        0: inf(0)\n"
        "        1: inf(0)\n"
        "    return val\n"
    )
    assert _execute(source) == 42
