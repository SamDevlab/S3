from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticCollection,
    DiagnosticPhase,
    DiagnosticSeverity,
    DiagnosticSource,
)


def _diagnostic(file: str, line: int, code: DiagnosticCode, message: str) -> Diagnostic:
    return Diagnostic(
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.SEMANTIC,
        DiagnosticPhase.SEMANTIC,
        code,
        message,
        file=file,
        source=DiagnosticSource(line=line, column=2),
    )


def test_diagnostic_collection_orders_by_source_and_code() -> None:
    later = _diagnostic("b.s3", 4, DiagnosticCode.SEMANTIC_TYPE_MISMATCH, "later")
    earlier = _diagnostic("a.s3", 2, DiagnosticCode.SEMANTIC_INVALID_PROGRAM, "earlier")
    collection = DiagnosticCollection.from_iterable([later, earlier])
    assert collection.diagnostics == (earlier, later)
    assert '"schema":"s3-diagnostic-list"' in collection.to_json()
    assert collection.to_text().splitlines()[0] == "a.s3:2:2: S3E_SEMANTIC_INVALID_PROGRAM: earlier"


def test_diagnostic_collection_rejects_unbounded_or_untyped_input() -> None:
    with pytest.raises(TypeError):
        DiagnosticCollection.from_iterable("not diagnostics")
    diagnostic = _diagnostic("a.s3", 1, DiagnosticCode.PARSE_SYNTAX, "bad")
    with pytest.raises(ValueError, match="positive integer"):
        DiagnosticCollection((diagnostic,), max_items=0)
    with pytest.raises(ValueError, match="canonical order"):
        DiagnosticCollection((
            _diagnostic("b.s3", 1, DiagnosticCode.PARSE_SYNTAX, "b"),
            _diagnostic("a.s3", 1, DiagnosticCode.PARSE_SYNTAX, "a"),
        ))
