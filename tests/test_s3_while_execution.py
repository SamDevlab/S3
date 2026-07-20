from __future__ import annotations

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_zero_iterations() -> None:
    result = run_source(
        "fn main() -> tryte:\n    mut x: tryte = 42\n    while 0:\n        x = 0\n    return x\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 42


def test_one_iteration() -> None:
    result = run_source(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 1:\n        x = x + 1\n    return x\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 1


def test_five_iterations() -> None:
    result = run_source(
        "fn main() -> tryte:\n    mut i: tryte = 0\n    while i <=> 5:\n        i = i + 1\n    return i\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 5


def test_accumulator() -> None:
    result = run_source(
        "fn main() -> tryte:\n    mut acc: tryte = 0\n    mut i: tryte = 0\n    while i <=> 10:\n        acc = acc + i\n        i = i + 1\n    return acc\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 45


def test_variable_updated_after_loop() -> None:
    result = run_source(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 3:\n        x = x + 1\n    x = 100\n    return x\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 100


def test_array_filled_in_same_frame() -> None:
    result = run_source(
        "fn main() -> tryte:\n"
        "    mut buf: tryte[4] = [0, 0, 0, 0]\n"
        "    mut i: tryte = 0\n"
        "    while i <=> 4:\n"
        "        buf[i] = i + 10\n"
        "        i = i + 1\n"
        "    return buf[0] + buf[1] + buf[2] + buf[3]\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 46


def test_array_read_after_loop() -> None:
    result = run_source(
        "fn main() -> tryte:\n"
        "    mut buf: tryte[3] = [0, 0, 0]\n"
        "    mut i: tryte = 0\n"
        "    while i <=> 3:\n"
        "        buf[i] = i\n"
        "        i = i + 1\n"
        "    return buf[0] + buf[2]\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 2


def test_match_inside_while() -> None:
    result = run_source(
        "fn main() -> tryte:\n"
        "    mut x: trit = -1\n"
        "    while x <=> 0:\n"
        "        match x:\n"
        "            -1:\n"
        "                x = 0\n"
        "            0:\n"
        "                x = 1\n"
        "            1:\n"
        "                x = 1\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 0


def test_nested_while() -> None:
    result = run_source(
        "fn main() -> tryte:\n"
        "    mut acc: tryte = 0\n"
        "    mut i: tryte = 0\n"
        "    while i <=> 3:\n"
        "        mut j: tryte = 0\n"
        "        while j <=> 2:\n"
        "            acc = acc + 1\n"
        "            j = j + 1\n"
        "        i = i + 1\n"
        "    return acc\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 6


def test_negative_enters_body() -> None:
    result = run_source(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 0\n"
        "    mut cond: trit = -1\n"
        "    while cond <=> 0:\n"
        "        x = 42\n"
        "        cond = 0\n"
        "    return x\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 42


def test_zero_exits_immediately() -> None:
    result = run_source(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 0\n"
        "    mut cond: trit = 0\n"
        "    while cond <=> 0:\n"
        "        x = 42\n"
        "        cond = 0\n"
        "    return x\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 0


def test_positive_exits_immediately() -> None:
    result = run_source(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 0\n"
        "    mut cond: trit = 1\n"
        "    while cond <=> 0:\n"
        "        x = 42\n"
        "        cond = 0\n"
        "    return x\n",
        mode=SyntaxMode.V0_6,
    )
    assert result == 0


def test_determinism() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut acc: tryte = 0\n"
        "    mut i: tryte = 0\n"
        "    while i <=> 5:\n"
        "        acc = acc + i\n"
        "        i = i + 1\n"
        "    return acc\n"
    )
    results = [run_source(source, mode=SyntaxMode.V0_6) for _ in range(5)]
    assert all(r == results[0] for r in results)
