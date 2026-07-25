from __future__ import annotations

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def test_semantic_discard_statement() -> None:
    source = (
        "fn helper(x: tryte) -> tryte:\n"
        "    return x + 1\n"
        "fn main() -> tryte:\n"
        "    discard helper(10)\n"
        "    return 0\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    assert model is not None
