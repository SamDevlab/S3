from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_compound_assignment_scalar() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    x += 5\n"
        "    x += 15\n"
        "    return x\n"
    )
    assert _execute(source) == 30


def test_execution_compound_assignment_indexed() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut arr: tryte[3] = [10, 20, 30]\n"
        "    arr[1] += 5\n"
        "    return arr[1]\n"
    )
    assert _execute(source) == 25


def test_execution_compound_assignment_in_for_loop() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(0, 5):\n"
        "        total += i\n"
        "    return total\n"
    )
    assert _execute(source) == 10
