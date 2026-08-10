from __future__ import annotations

from bootstrap.s3.assembly import AssemblyType
from bootstrap.s3.codegen import TYPE_MAP
from bootstrap.s3.ir import IRType


def test_numeric_types_are_publicly_named_in_ir_and_assembly() -> None:
    assert IRType.I64.value == "i64"
    assert IRType.F64.value == "f64"
    assert AssemblyType.I64.value == "i64"
    assert AssemblyType.F64.value == "f64"
    assert TYPE_MAP[IRType.I64] is AssemblyType.I64
    assert TYPE_MAP[IRType.F64] is AssemblyType.F64
