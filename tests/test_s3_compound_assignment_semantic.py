from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _analyze(source: str) -> SemanticModel:
    return analyze(parse(source, mode=SyntaxMode.V0_6))


def test_compound_assignment_semantic_valid_scalar() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    x += 5\n"
        "    return x\n"
    )
    assert model is not None


def test_compound_assignment_semantic_valid_indexed() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    mut arr: tryte[3] = [1, 2, 3]\n"
        "    arr[0] += 10\n"
        "    return arr[0]\n"
    )
    assert model is not None


def test_compound_assignment_semantic_rejects_immutable() -> None:
    with pytest.raises(SemanticError, match="cannot assign to immutable variable"):
        _analyze(
            "fn main() -> tryte:\n"
            "    x: tryte = 10\n"
            "    x += 5\n"
            "    return x\n"
        )
