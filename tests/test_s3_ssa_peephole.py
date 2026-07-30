from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_peephole_add_zero() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 42\n"
        "    mut b: tryte = a + 0\n"
        "    return b\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 42


def test_peephole_minimum_maximum_self() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 13\n"
        "    mut min_val: tryte = a & a\n"
        "    mut max_val: tryte = a | a\n"
        "    return min_val + max_val\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 26


def test_peephole_compare_self() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 77\n"
        "    mut cmp: trit = a <=> a\n"
        "    mut res: tryte = 0\n"
        "    match cmp:\n"
        "        0:\n"
        "            res = 100\n"
        "        else:\n"
        "            res = 0\n"
        "    return res\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 100


def test_peephole_double_invert() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 5\n"
        "    mut inv1: tryte = ~a\n"
        "    mut inv2: tryte = ~inv1\n"
        "    return inv2\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 5
