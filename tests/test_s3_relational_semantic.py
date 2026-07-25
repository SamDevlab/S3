from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def _analyze(source: str):
    return analyze(parse(source, mode=SyntaxMode.V0_6))


def test_relational_operand_types_matched() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    mut b: tryte = 20\n"
        "    mut c: trit = a < b\n"
        "    mut d: trit = a == b\n"
        "    mut e: trit = a != b\n"
        "    mut f: trit = a <= b\n"
        "    mut g: trit = a > b\n"
        "    mut h: trit = a >= b\n"
        "    return 0\n"
    )
    assert model is not None


def test_relational_mismatched_types_rejected() -> None:
    with pytest.raises(SemanticError, match="has type trit; expected tryte"):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut a: tryte = 10\n"
            "    mut b: trit = 1\n"
            "    mut c: trit = a < b\n"
            "    return 0\n"
        )


def test_relational_result_must_be_trit() -> None:
    with pytest.raises(SemanticError, match="comparison result has type trit; expected tryte"):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut a: tryte = 10\n"
            "    mut b: tryte = 20\n"
            "    mut c: tryte = a == b\n"
            "    return 0\n"
        )


def test_relational_condition_in_while() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    while i != 5:\n"
        "        i = i + 1\n"
        "    return i\n"
    )
    assert model is not None
