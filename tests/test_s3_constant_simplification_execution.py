from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_execution_constant_simplification_addition() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 42\n"
        "    a: tryte = x + 0\n"
        "    b: tryte = 0 + a\n"
        "    return b\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 42


def test_execution_constant_simplification_subtraction() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 100\n"
        "    a: tryte = x - 0\n"
        "    return a\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 100


def test_execution_constant_simplification_double_negate() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 25\n"
        "    a: tryte = -(-x)\n"
        "    return a\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 25
