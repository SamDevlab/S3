from __future__ import annotations

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_for_execution_basic_summation() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 0\n"
        "    for i: tryte in range(0, 5):\n"
        "        sum = sum + i\n"
        "    return sum\n"
    )
    assert _execute(source) == 10


def test_for_execution_offset_range() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 0\n"
        "    for i: tryte in range(5, 8):\n"
        "        sum = sum + i\n"
        "    return sum\n"
    )
    assert _execute(source) == 18


def test_for_execution_empty_range() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 42\n"
        "    for i: tryte in range(5, 5):\n"
        "        sum = 0\n"
        "    return sum\n"
    )
    assert _execute(source) == 42


def test_for_execution_start_greater_than_end() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 42\n"
        "    for i: tryte in range(10, 5):\n"
        "        sum = 0\n"
        "    return sum\n"
    )
    assert _execute(source) == 42


def test_for_execution_break() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 0\n"
        "    for i: tryte in range(0, 10):\n"
        "        match i == 3:\n"
        "            -1:\n"
        "                break\n"
        "            0:\n"
        "                sum = sum\n"
        "            1:\n"
        "                sum = sum\n"
        "        sum = sum + i\n"
        "    return sum\n"
    )
    # 0 + 1 + 2 = 3
    assert _execute(source) == 3


def test_for_execution_continue() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 0\n"
        "    for i: tryte in range(0, 5):\n"
        "        match i == 2:\n"
        "            -1:\n"
        "                continue\n"
        "            0:\n"
        "                sum = sum\n"
        "            1:\n"
        "                sum = sum\n"
        "        sum = sum + i\n"
        "    return sum\n"
    )
    # 0 + 1 + (skip 2) + 3 + 4 = 8
    assert _execute(source) == 8


def test_for_execution_nested() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut count: tryte = 0\n"
        "    for i: tryte in range(0, 3):\n"
        "        for j: tryte in range(0, 4):\n"
        "            count = count + 1\n"
        "    return count\n"
    )
    assert _execute(source) == 12
