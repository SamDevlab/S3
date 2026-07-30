from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_execution_constant_propagation_chain() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    a: tryte = 5\n"
        "    b: tryte = a\n"
        "    c: tryte = b + 3\n"
        "    return c\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 8


def test_execution_constant_propagation_mutable() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 5\n"
        "    a = 10\n"
        "    b: tryte = a + 3\n"
        "    return b\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 13
