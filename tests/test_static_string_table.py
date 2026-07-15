from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.static_strings import (
    StaticStringTable,
    collect_static_string_literals,
)


def _table(source: str) -> StaticStringTable:
    return collect_static_string_literals(parse(source, mode=SyntaxMode.V0_6))


def test_single_static_string_literal_gets_s0() -> None:
    table = _table('fn main() -> tryte:\n    return "hello"\n')

    assert [(entry.id, entry.value, entry.index) for entry in table.entries] == [
        ("s0", "hello", 0),
    ]


def test_static_string_literal_table_preserves_first_occurrence_order() -> None:
    table = _table(
        'fn main() -> tryte:\n'
        '    first: tryte = "hello"\n'
        '    second: tryte = "world"\n'
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in table.entries] == [
        ("s0", "hello"),
        ("s1", "world"),
    ]


def test_static_string_literal_table_deduplicates_by_value() -> None:
    table = _table(
        'fn main() -> tryte:\n'
        '    first: tryte = "hello"\n'
        '    second: tryte = "world"\n'
        '    third: tryte = "hello"\n'
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in table.entries] == [
        ("s0", "hello"),
        ("s1", "world"),
    ]
    assert table.entry_for_value("hello") is table.entries[0]
    assert table.entry_for_value("missing") is None


def test_static_string_literal_table_walks_nested_expressions() -> None:
    table = _table('fn main() -> tryte:\n    return "left" + ("right" + "left")\n')

    assert [(entry.id, entry.value) for entry in table.entries] == [
        ("s0", "left"),
        ("s1", "right"),
    ]


def test_static_string_literals_still_fail_before_lowering() -> None:
    with pytest.raises(SemanticError) as captured:
        compile_source('fn main() -> tryte:\n    return "hello"\n')

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED
    )
