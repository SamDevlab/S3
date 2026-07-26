from __future__ import annotations

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def test_semantic_single_bound_range() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[3] = [1, 2, 3]\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(len(values)):\n"
        "        total += values[i]\n"
        "    return total\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    assert model is not None
