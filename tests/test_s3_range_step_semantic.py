from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def test_semantic_stepped_range_valid() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut total: tryte = 0\n"
        "    for i: tryte in range(0, 10, 2):\n"
        "        total += i\n"
        "    return total\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    assert model is not None


def test_semantic_stepped_range_rejects_zero_step() -> None:
    with pytest.raises(SemanticError, match="range step cannot be zero"):
        source = (
            "fn main() -> tryte:\n"
            "    mut total: tryte = 0\n"
            "    for i: tryte in range(0, 10, 0):\n"
            "        total += i\n"
            "    return total\n"
        )
        analyze(parse(source, mode=SyntaxMode.V0_6))
