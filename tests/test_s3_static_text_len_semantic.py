from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze
from bootstrap.s3.ternary import TRYTE_MAX


def _analyze(source: str) -> SemanticModel:
    return analyze(parse(source, mode=SyntaxMode.V0_6))


def test_len_semantic_accepts_static_text_literal() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        '    size: tryte = len("abc")\n'
        "    return size\n"
    )
    assert model is not None


def test_len_semantic_accepts_constant_static_text_concatenation() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        '    size: tryte = len(("a" + "b") + "c")\n'
        "    return size\n"
    )
    assert model is not None


def test_len_semantic_accepts_static_text_in_return() -> None:
    model = _analyze(
        "fn size() -> tryte:\n"
        '    return len("hello" + " world")\n'
        "fn main() -> tryte:\n"
        "    return size()\n"
    )
    assert model is not None


def test_len_semantic_rejects_static_text_binding_operand() -> None:
    with pytest.raises(
        SemanticError,
        match="len\\(\\) argument must be a static array or a compile-time static text expression",
    ):
        _analyze(
            "fn main() -> tryte:\n"
            '    value: string = "abc"\n'
            "    return len(value)\n"
        )


def test_len_semantic_rejects_runtime_static_text_concatenation() -> None:
    with pytest.raises(
        SemanticError,
        match="len\\(\\) argument must be a static array or a compile-time static text expression",
    ):
        _analyze(
            "fn size(name: string) -> tryte:\n"
            '    return len("hello" + name)\n'
            "fn main() -> tryte:\n"
            '    return size("world")\n'
        )


def test_len_semantic_rejects_unsupported_operand() -> None:
    with pytest.raises(
        SemanticError,
        match="len\\(\\) argument must be a static array or a compile-time static text expression",
    ):
        _analyze(
            "fn main() -> tryte:\n"
            "    return len(10)\n"
        )


def test_len_semantic_rejects_array_element() -> None:
    with pytest.raises(
        SemanticError,
        match="not an array element",
    ):
        _analyze(
            "fn main() -> tryte:\n"
            "    values: tryte[2] = [1, 2]\n"
            "    return len(values[0])\n"
        )


def test_len_semantic_rejects_static_text_length_outside_tryte_range() -> None:
    literal = "a" * (TRYTE_MAX + 1)
    with pytest.raises(
        SemanticError,
        match=f"static text length {TRYTE_MAX + 1} exceeds tryte maximum {TRYTE_MAX}",
    ):
        _analyze(
            "fn main() -> tryte:\n"
            f'    return len("{literal}")\n'
        )
