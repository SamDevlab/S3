from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.optimizer import OptimizationLevel, optimize_ir
from bootstrap.s3.pipeline import compile_source, run_source


def test_multi_field_record_return_feeds_direct_field_access_o0_o1() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "fn make() -> Pair:\n"
        "    return Pair(left=4, right=6)\n"
        "fn main() -> tryte:\n"
        "    return make().left + make().right\n"
    )

    assert run_source(source, optimization="O0") == 10
    assert run_source(source, optimization="O1") == 10
    compilation = compile_source(source, optimization="O0")
    make = compilation.ir.functions[0]
    call = compilation.ir.functions[1].blocks[0].instructions[0]

    assert [type_name.value for type_name in make.result_types] == [
        "tryte",
        "tryte",
    ]
    assert len(call.results) == 2


def test_nested_record_return_preserves_depth_first_cell_order() -> None:
    source = (
        "record Inner:\n"
        "    x: tryte\n"
        "    y: trit\n"
        "record Outer:\n"
        "    prefix: tryte\n"
        "    inner: Inner\n"
        "fn make() -> Outer:\n"
        "    return Outer(prefix=3, inner=Inner(x=5, y=-1))\n"
        "fn main() -> tryte:\n"
        "    item: Outer = make()\n"
        "    mut total: tryte = item.prefix + item.inner.x\n"
        "    match item.inner.y <=> 0:\n"
        "        -1:\n"
        "            return total - 1\n"
        "        0:\n"
        "            return total\n"
        "        1:\n"
        "            return total + 1\n"
    )

    assert run_source(source, optimization="O0") == 7
    assert run_source(source, optimization="O1") == 7
    compilation = compile_source(source, optimization="O0")
    make = compilation.ir.functions[0]

    assert [type_name.value for type_name in make.result_types] == [
        "tryte",
        "tryte",
        "trit",
    ]


def test_structured_result_enum_return_can_be_matched_by_caller() -> None:
    source = (
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(code: tryte)\n"
        "fn parse(flag: trit) -> Result:\n"
        "    match flag:\n"
        "        -1:\n"
        "            return Result.Err(code=7)\n"
        "        0:\n"
        "            return Result.Ok(value=11)\n"
        "        1:\n"
        "            return Result.Ok(value=13)\n"
        "fn unwrap(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "        Result.Err(code):\n"
        "            return 0 - code\n"
        "fn main() -> tryte:\n"
        "    return unwrap(parse(0)) + unwrap(parse(-1))\n"
    )

    assert run_source(source, optimization="O0") == 4
    assert run_source(source, optimization="O1") == 4
    compilation = compile_source(source, optimization="O0")
    parse = compilation.ir.functions[0]

    assert [type_name.value for type_name in parse.result_types] == [
        "tryte",
        "tryte",
    ]


def test_optimizer_preserves_multi_cell_call_result_groups() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "fn make() -> Pair:\n"
        "    return Pair(left=2, right=3)\n"
        "fn main() -> tryte:\n"
        "    pair: Pair = make()\n"
        "    return pair.left\n"
    )
    module = compile_source(source, optimization="O0").ir

    optimized = optimize_ir(module, OptimizationLevel.O1)
    call = next(
        instruction
        for instruction in optimized.functions[1].instructions
        if instruction.callee == "make"
    )

    assert len(call.results) == 2


def test_entry_main_rejects_aggregate_result() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "fn main() -> Pair:\n"
        "    return Pair(left=1, right=2)\n"
    )

    with pytest.raises(SemanticError) as error:
        compile_source(source)

    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE
    assert "main" in str(error.value)
