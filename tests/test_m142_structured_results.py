from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.ir_serialization import serialize_ir
from bootstrap.s3.pipeline import compile_source, run_source


STRUCTURED_RESULT_SOURCE = """\
record ErrorContext:
    code: tryte
    detail: tryte
enum ParseResult:
    Ok(value: tryte)
    Err(error: ErrorContext)
fn parse(flag: trit) -> ParseResult:
    match flag:
        -1:
            return ParseResult.Err(error=ErrorContext(code=7, detail=11))
        0:
            return ParseResult.Ok(value=42)
        1:
            return ParseResult.Ok(value=43)
fn forward(flag: trit) -> ParseResult:
    result: ParseResult = parse(flag)
    match result:
        ParseResult.Ok(value):
            return ParseResult.Ok(value=value)
        ParseResult.Err(error):
            return ParseResult.Err(error=error)
fn inspect(result: ParseResult) -> tryte:
    match result:
        ParseResult.Ok(value):
            return value
        ParseResult.Err(error):
            return 0 - error.code - error.detail
fn main() -> tryte:
    return inspect(forward(0)) + inspect(forward(-1))
"""


def test_explicit_error_result_propagation_is_o0_o1_equivalent() -> None:
    assert run_source(STRUCTURED_RESULT_SOURCE, optimization="O0") == 24
    assert run_source(STRUCTURED_RESULT_SOURCE, optimization="O1") == 24


def test_nested_error_context_serialization_is_deterministic() -> None:
    first = compile_source(STRUCTURED_RESULT_SOURCE, optimization="O0")
    second = compile_source(STRUCTURED_RESULT_SOURCE, optimization="O0")

    assert serialize_ir(first.ir) == serialize_ir(second.ir)
    assert first.assembly_text == second.assembly_text
    assert [type_name.value for type_name in first.ir.functions[0].result_types] == [
        "tryte",
        "tryte",
        "tryte",
    ]


def test_result_must_be_matched_before_scalar_return() -> None:
    source = """\
enum Result:
    Ok(value: tryte)
    Err(code: tryte)
fn produce() -> Result:
    return Result.Ok(value=1)
fn main() -> tryte:
    return produce()
"""

    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH


def test_result_matching_is_exhaustive() -> None:
    source = """\
enum Result:
    Ok(value: tryte)
    Err(code: tryte)
fn inspect(result: Result) -> tryte:
    match result:
        Result.Ok(value):
            return value
fn main() -> tryte:
    return 0
"""

    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.MATCH_NON_EXHAUSTIVE
