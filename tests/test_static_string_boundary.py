from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import (
    DiagnosticCode,
    DiagnosticPhase,
    SemanticError,
)
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_source


SOURCE = 'fn main() -> tryte:\n    return "hello"\n'


def test_static_string_literal_as_tryte_stops_at_semantic_boundary() -> None:
    program = parse(SOURCE, mode=SyntaxMode.V0_6)
    statement = program.functions[0].body.statements[0]
    assert isinstance(statement, ast.ReturnStatement)
    assert isinstance(statement.expression, ast.StringLiteral)

    with pytest.raises(SemanticError) as captured:
        compile_source(SOURCE, mode=SyntaxMode.V0_6)

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_TYPE_MISMATCH
    )
    assert captured.value.diagnostic_phase is DiagnosticPhase.SEMANTIC
    assert captured.value.message == "string literal has type string; expected tryte"
