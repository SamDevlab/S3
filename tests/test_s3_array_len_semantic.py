from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _analyze(source: str) -> SemanticModel:
    return analyze(parse(source, mode=SyntaxMode.V0_6))


def test_len_semantic_tryte_array() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
        "    size: tryte = len(values)\n"
        "    return size\n"
    )
    assert model is not None


def test_len_semantic_trit_array() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    flags: trit[3] = [-1, 0, 1]\n"
        "    size: tryte = len(flags)\n"
        "    return size\n"
    )
    assert model is not None


def test_len_semantic_rejects_scalar_variable() -> None:
    with pytest.raises(SemanticError, match="len\\(\\) argument must be a static array"):
        _analyze(
            "fn main() -> tryte:\n"
            "    x: tryte = 5\n"
            "    return len(x)\n"
        )


def test_len_semantic_rejects_index_expression() -> None:
    with pytest.raises(SemanticError, match="len\\(\\) argument must be a static array, not an array element"):
        _analyze(
            "fn main() -> tryte:\n"
            "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
            "    return len(values[0])\n"
        )


def test_len_semantic_rejects_integer_literal() -> None:
    with pytest.raises(SemanticError, match="len\\(\\) argument must be a static array"):
        _analyze(
            "fn main() -> tryte:\n"
            "    return len(10)\n"
        )


def test_len_semantic_rejects_undeclared_variable() -> None:
    with pytest.raises(SemanticError, match="undeclared variable 'unknown'"):
        _analyze(
            "fn main() -> tryte:\n"
            "    return len(unknown)\n"
        )
