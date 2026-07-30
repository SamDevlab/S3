from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_execution_constant_logical_and() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    t1: tryte = -1 & -1\n"
        "    t2: tryte = -1 & 0\n"
        "    t3: tryte = 0 & 0\n"
        "    return t1 + t2 + t3\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == -2


def test_execution_constant_logical_or() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    t1: tryte = -1 | 0\n"
        "    t2: tryte = 0 | 0\n"
        "    return t1 + t2\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 0


def test_execution_constant_logical_not() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    t1: tryte = ~(-1)\n"
        "    t2: tryte = ~0\n"
        "    return t1 + t2\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 1


def test_execution_constant_logical_compound() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    c1: trit = (10 == 10) & (5 < 10)\n"
        "    c2: trit = ~(10 == 10)\n"
        "    c3: tryte = (-1 & 0) | (~(-1))\n"
        "    return c3\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == 1


def test_execution_partially_constant_logical() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 1\n"
        "    r1: tryte = x & -1\n"
        "    r2: tryte = ~x\n"
        "    return r1 + r2\n"
    )
    assert run_source(source, mode=SyntaxMode.V0_6) == -2
