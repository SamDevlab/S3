from __future__ import annotations

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


@pytest.mark.parametrize(
    ("op", "a", "b", "expected"),
    [
        ("==", 10, 10, -1),
        ("==", 10, 20, 0),
        ("!=", 10, 20, -1),
        ("!=", 10, 10, 0),
        ("<", 10, 20, -1),
        ("<", 20, 10, 0),
        ("<=", 10, 10, -1),
        ("<=", 10, 20, -1),
        ("<=", 20, 10, 0),
        (">", 20, 10, -1),
        (">", 10, 20, 0),
        (">=", 20, 20, -1),
        (">=", 20, 10, -1),
        (">=", 10, 20, 0),
    ],
)
def test_relational_operations_execution(op: str, a: int, b: int, expected: int) -> None:
    source = (
        f"fn main() -> tryte:\n"
        f"    mut res: trit = {a} {op} {b}\n"
        f"    match res:\n"
        f"        -1:\n"
        f"            return -1\n"
        f"        0:\n"
        f"            return 0\n"
        f"        1:\n"
        f"            return 1\n"
    )
    assert _execute(source) == expected


def test_relational_while_loop_execution() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    while i != 5:\n"
        "        i = i + 1\n"
        "    return i\n"
    )
    assert _execute(source) == 5
