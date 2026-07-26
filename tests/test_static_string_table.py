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
from bootstrap.s3.static_text import StaticTextDecodeError


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


def test_static_string_literal_entry_exposes_deterministic_text_metadata() -> None:
    table = _table(
        'fn main() -> tryte:\n'
        r'    first: tryte = "line\nnext"'
        "\n"
        r'    second: tryte = "quote: \" slash: \\"'
        "\n"
        "    return 0\n"
    )

    first = table.entries[0]
    assert first.id == "s0"
    assert first.value == "line\nnext"
    assert first.text == "line\nnext"
    assert first.utf8_bytes == b"line\nnext"
    assert first.byte_count == 9
    assert first.line_count == 2
    assert (
        first.sha256
        == "dc20ec73d7c6c71c3936bd3ff9734b011870b68ef6ca70ac638189d251526eb9"
    )

    second = table.entries[1]
    assert second.text == 'quote: " slash: \\'


def test_static_string_literal_table_keeps_stable_ids_with_escaped_literals() -> None:
    table = _table(
        'fn main() -> tryte:\n'
        r'    first: tryte = "same\ntext"'
        "\n"
        r'    second: tryte = "other"'
        "\n"
        r'    third: tryte = "same\ntext"'
        "\n"
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in table.entries] == [
        ("s0", "same\ntext"),
        ("s1", "other"),
    ]


def test_static_string_literal_table_reports_unsupported_escape_when_collected() -> None:
    with pytest.raises(StaticTextDecodeError):
        _table('fn main() -> tryte:\n' r'    return "bad\t"' "\n")


def test_static_string_literal_table_walks_nested_expressions() -> None:
    table = _table('fn main() -> tryte:\n    return "left" + ("right" + "left")\n')

    assert [(entry.id, entry.value) for entry in table.entries] == [
        ("s0", "leftrightleft"),
    ]


def test_static_string_literal_table_deduplicates_folded_concat_with_literal() -> None:
    table = _table(
        "fn main() -> tryte:\n"
        '    first: string = "a" + "b"\n'
        '    second: string = "ab"\n'
        "    return 0\n"
    )

    assert [(entry.id, entry.value) for entry in table.entries] == [
        ("s0", "ab"),
    ]


def test_static_string_literal_used_as_tryte_fails_semantic_type_check() -> None:
    with pytest.raises(SemanticError) as captured:
        compile_source('fn main() -> tryte:\n    return "hello"\n')

    assert captured.value.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH
