from __future__ import annotations

from bootstrap.s3.backends._hosted_execution import _execute_hosted_assembly
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources, run_source


def _run_o0_o1(source: str) -> tuple[int, int]:
    return (
        run_source(source, optimization="O0"),
        run_source(source, optimization="O1"),
    )


def test_enum_payload_scalar_local_parameter_call_and_match_execute() -> None:
    source = (
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Empty\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "        Result.Empty:\n"
        "            return 0\n"
        "fn main() -> tryte:\n"
        "    result: Result = Result.Ok(value=7)\n"
        "    return inspect(result)\n"
    )

    assert _run_o0_o1(source) == (7, 7)


def test_enum_payload_record_binding_executes() -> None:
    source = (
        "record Detail:\n"
        "    code: tryte\n"
        "enum Result:\n"
        "    Ok(detail: Detail)\n"
        "    Empty\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(detail):\n"
        "            return detail.code\n"
        "        Result.Empty:\n"
        "            return 0\n"
        "fn main() -> tryte:\n"
        "    result: Result = Result.Ok(detail=Detail(code=5))\n"
        "    return inspect(result)\n"
    )

    assert _run_o0_o1(source) == (5, 5)


def test_enum_payload_inactive_string_slot_is_initialized() -> None:
    source = (
        "enum Result:\n"
        "    Empty\n"
        "    Text(value: string)\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Empty:\n"
        "            return 3\n"
        "        Result.Text(value):\n"
        "            return 9\n"
        "fn main() -> tryte:\n"
        "    result: Result = Result.Empty\n"
        "    return inspect(result)\n"
    )

    assert _run_o0_o1(source) == (3, 3)


def test_enum_payload_constructor_argument_and_copy_execute() -> None:
    source = (
        "enum Result:\n"
        "    Empty\n"
        "    Ok(value: tryte)\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Empty:\n"
        "            return 0\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "fn main() -> tryte:\n"
        "    first: Result = Result.Ok(value=4)\n"
        "    second: Result = first\n"
        "    return inspect(second) + inspect(Result.Ok(value=2))\n"
    )

    assert _run_o0_o1(source) == (6, 6)


def test_nested_enum_payload_execute() -> None:
    source = (
        "enum Inner:\n"
        "    Empty\n"
        "    Code(value: tryte)\n"
        "enum Outer:\n"
        "    Wrap(inner: Inner)\n"
        "    Other(value: tryte)\n"
        "fn inspect(inner: Inner) -> tryte:\n"
        "    match inner:\n"
        "        Inner.Empty:\n"
        "            return 0\n"
        "        Inner.Code(value):\n"
        "            return value\n"
        "fn unwrap(outer: Outer) -> tryte:\n"
        "    match outer:\n"
        "        Outer.Wrap(inner):\n"
        "            return inspect(inner)\n"
        "        Outer.Other(value):\n"
        "            return value\n"
        "fn main() -> tryte:\n"
        "    outer: Outer = Outer.Wrap(inner=Inner.Code(value=8))\n"
        "    return unwrap(outer)\n"
    )

    assert _run_o0_o1(source) == (8, 8)


def test_imported_qualified_enum_payload_construction_executes() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from api import Result\n"
            "from api import inspect\n"
            "fn main() -> tryte:\n"
            "    result: Result = api.Result.Ok(value=6)\n"
            "    return inspect(result)\n"
        ),
        "api.s3": (
            "module api\n"
            "export enum Result:\n"
            "    Empty\n"
            "    Ok(value: tryte)\n"
            "export fn inspect(result: Result) -> tryte:\n"
            "    match result:\n"
            "        Result.Empty:\n"
            "            return 0\n"
            "        Result.Ok(value):\n"
            "            return value\n"
        ),
    }

    for optimization in (OptimizationLevel.O0, OptimizationLevel.O1):
        compilation = compile_sources(sources, optimization=optimization)
        assert _execute_hosted_assembly(compilation.assembly, "main") == 6


def test_enum_payload_match_expression_binding_executes() -> None:
    source = (
        "enum Result:\n"
        "    Empty\n"
        "    Ok(value: tryte)\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    return match result:\n"
        "        Result.Empty: 0\n"
        "        Result.Ok(value): value\n"
        "fn main() -> tryte:\n"
        "    return inspect(Result.Ok(value=9))\n"
    )

    assert _run_o0_o1(source) == (9, 9)


def test_enum_payload_nested_record_binding_executes() -> None:
    source = (
        "record Inner:\n"
        "    code: tryte\n"
        "record Detail:\n"
        "    inner: Inner\n"
        "enum Result:\n"
        "    Empty\n"
        "    Err(detail: Detail)\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Empty:\n"
        "            return 0\n"
        "        Result.Err(detail):\n"
        "            return detail.inner.code\n"
        "fn main() -> tryte:\n"
        "    result: Result = Result.Err(detail=Detail(inner=Inner(code=7)))\n"
        "    return inspect(result)\n"
    )

    assert _run_o0_o1(source) == (7, 7)
