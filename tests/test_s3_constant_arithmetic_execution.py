from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_execution_constant_arithmetic_simple() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    a: tryte = 10 + 5\n"
        "    b: tryte = 10 - 5\n"
        "    return a + b\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 20


def test_execution_constant_arithmetic_compound() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    a: tryte = (20 - 5) + (10 - 15)\n"
        "    return a\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 10


def test_execution_constant_arithmetic_mixed() -> None:
    source = (
        "fn main() -> trit:\n"
        "    a: trit = (10 == 10) + (10 == 5)\n"
        "    return a\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == -1


def test_execution_partially_constant_arithmetic() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    a: tryte = x + 5\n"
        "    return a\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 15
