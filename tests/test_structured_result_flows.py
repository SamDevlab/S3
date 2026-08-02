from __future__ import annotations

import pytest

from bootstrap.s3.backends._hosted_execution import _execute_hosted_assembly
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources, run_source


def _run_o0_o1(source: str) -> tuple[int, int]:
    return (
        run_source(source, optimization="O0"),
        run_source(source, optimization="O1"),
    )


def test_structured_result_success_and_error_locals_execute() -> None:
    source = (
        "record Error:\n"
        "    code: tryte\n"
        "enum ParseResult:\n"
        "    Ok(value: tryte)\n"
        "    Err(error: Error)\n"
        "fn handle(result: ParseResult) -> tryte:\n"
        "    match result:\n"
        "        ParseResult.Ok(value):\n"
        "            return value\n"
        "        ParseResult.Err(error):\n"
        "            return error.code\n"
        "fn main() -> tryte:\n"
        "    success: ParseResult = ParseResult.Ok(value=8)\n"
        "    failure: ParseResult = ParseResult.Err(error=Error(code=-2))\n"
        "    return handle(success) + handle(failure)\n"
    )

    assert _run_o0_o1(source) == (6, 6)


def test_structured_result_nested_error_record_executes() -> None:
    source = (
        "record Diagnostic:\n"
        "    code: tryte\n"
        "record Error:\n"
        "    diagnostic: Diagnostic\n"
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(error: Error)\n"
        "fn handle(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "        Result.Err(error):\n"
        "            return error.diagnostic.code\n"
        "fn main() -> tryte:\n"
        "    result: Result = Result.Err(error=Error(diagnostic=Diagnostic(code=5)))\n"
        "    return handle(result)\n"
    )

    assert _run_o0_o1(source) == (5, 5)


def test_imported_structured_result_type_executes() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from resultlib import Result\n"
            "from resultlib import Error\n"
            "from resultlib import handle\n"
            "fn main() -> tryte:\n"
            "    result: Result = resultlib.Result.Err(error=resultlib.Error(code=4))\n"
            "    return handle(result)\n"
        ),
        "resultlib.s3": (
            "module resultlib\n"
            "export record Error:\n"
            "    code: tryte\n"
            "export enum Result:\n"
            "    Ok(value: tryte)\n"
            "    Err(error: Error)\n"
            "export fn handle(result: Result) -> tryte:\n"
            "    match result:\n"
            "        Result.Ok(value):\n"
            "            return value\n"
            "        Result.Err(error):\n"
            "            return error.code\n"
        ),
    }

    for optimization in (OptimizationLevel.O0, OptimizationLevel.O1):
        compilation = compile_sources(sources, optimization=optimization)
        assert _execute_hosted_assembly(compilation.assembly, "main") == 4


def test_structured_result_return_remains_rejected_semantically() -> None:
    source = (
        "record Error:\n"
        "    code: tryte\n"
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(error: Error)\n"
        "fn make() -> Result:\n"
        "    return Result.Ok(value=1)\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    with pytest.raises(SemanticError) as error:
        run_source(source)
    assert "multi-cell enum returns require a future aggregate ABI" in str(error.value)
