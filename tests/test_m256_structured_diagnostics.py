"""M2.56 bounded structured diagnostic construction contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticMessageBuilder,
    DiagnosticMessageLimitError,
    DiagnosticPhase,
    DiagnosticSeverity,
    DiagnosticSource,
)


def test_message_builder_produces_deterministic_structured_diagnostics() -> None:
    builder = DiagnosticMessageBuilder(max_message_bytes=64, max_notes=2)
    builder.append("nome ").append("não encontrado")
    builder.add_note("verifique o escopo")
    diagnostic = builder.build(
        severity=DiagnosticSeverity.ERROR,
        category=DiagnosticCategory.SEMANTIC,
        phase=DiagnosticPhase.SEMANTIC,
        code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        file="main.s3",
        source=DiagnosticSource(offset=4, line=1, column=5),
    )
    assert isinstance(diagnostic, Diagnostic)
    assert diagnostic.to_json() == diagnostic.to_json()
    assert diagnostic.message == "nome não encontrado"
    assert diagnostic.notes == ("verifique o escopo",)


def test_message_builder_enforces_utf8_bytes_without_partial_mutation() -> None:
    builder = DiagnosticMessageBuilder(max_message_bytes=5)
    builder.append("ab")
    with pytest.raises(DiagnosticMessageLimitError):
        builder.append("éé")
    assert builder.render() == "ab"
    assert builder.message_bytes == 2


def test_message_builder_bounds_note_count_and_note_bytes() -> None:
    builder = DiagnosticMessageBuilder(max_notes=1, max_note_bytes=3)
    builder.add_note("ok")
    with pytest.raises(DiagnosticMessageLimitError):
        builder.add_note("x")
    with pytest.raises(DiagnosticMessageLimitError):
        DiagnosticMessageBuilder(max_note_bytes=2).add_note("éé")


def test_message_builder_rejects_untyped_or_empty_text() -> None:
    builder = DiagnosticMessageBuilder()
    with pytest.raises(TypeError):
        builder.append(1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        builder.add_note("")
    with pytest.raises(ValueError):
        DiagnosticMessageBuilder(max_message_bytes=0)
