from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def _analyze(source: str):
    return analyze(parse(source, mode=SyntaxMode.V0_6))


def test_for_semantic_valid() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 0\n"
        "    for i: tryte in range(0, 10):\n"
        "        sum = sum + i\n"
        "    return sum\n"
    )
    assert model is not None


def test_for_semantic_start_bound_must_be_tryte() -> None:
    with pytest.raises(SemanticError, match="has type trit; expected tryte"):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut t: trit = 0\n"
            "    for i: tryte in range(t, 10):\n"
            "        return 0\n"
            "    return 0\n"
        )


def test_for_semantic_end_bound_must_be_tryte() -> None:
    with pytest.raises(SemanticError, match="has type trit; expected tryte"):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut t: trit = 0\n"
            "    for i: tryte in range(0, t):\n"
            "        return 0\n"
            "    return 0\n"
        )


def test_for_semantic_loop_variable_immutable() -> None:
    with pytest.raises(SemanticError, match="cannot assign to immutable variable"):
        _analyze(
            "fn main() -> tryte:\n"
            "    for i: tryte in range(0, 10):\n"
            "        i = 5\n"
            "    return 0\n"
        )


def test_for_semantic_loop_variable_scoped_to_body() -> None:
    with pytest.raises(SemanticError, match="undeclared variable 'i'"):
        _analyze(
            "fn main() -> tryte:\n"
            "    for i: tryte in range(0, 10):\n"
            "        mut x: tryte = i\n"
            "    return i\n"
        )
