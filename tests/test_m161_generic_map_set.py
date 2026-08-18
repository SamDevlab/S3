from __future__ import annotations

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.backends.x86_64.backend import X8664Backend


def test_generic_map_i64_i64_uses_ordered_map_runtime() -> None:
    source = """\
fn main() -> i64:
    mut values: map<i64, i64> = map_new<i64, i64>(3)
    discard map_put<i64, i64>(&mut values, 7, 70)
    discard map_put<i64, i64>(&mut values, 8, 80)
    discard map_put<i64, i64>(&mut values, 7, 77)
    return map_value_at<i64, i64>(&values, 0)
"""
    compilation = compile_source(source)
    assert run_source(source, optimization="O0") == 77
    assert run_source(source, optimization="O1") == 77
    native = X8664Backend().generate(compilation.assembly)
    assert "__s3_builtin_i64_map_new" in native
    assert "__s3_builtin_i64_map_put" in native


def test_generic_set_i64_preserves_duplicate_and_order_contract() -> None:
    source = """\
fn main() -> i64:
    mut values: set<i64> = set_new<i64>(3)
    discard set_add<i64>(&mut values, 7)
    discard set_add<i64>(&mut values, 8)
    discard set_add<i64>(&mut values, 7)
    discard set_remove<i64>(&mut values, 7)
    return set_at<i64>(&values, 0)
"""
    assert run_source(source, optimization="O0") == 8
    assert run_source(source, optimization="O1") == 8


def test_generic_map_and_set_reject_unimplemented_type_domains() -> None:
    invalid_map = """\
fn main() -> i64:
    mut values: map<tryte, i64> = map_new<tryte, i64>(1)
    return map_len<tryte, i64>(&values)
"""
    with pytest.raises(SemanticError) as map_error:
        compile_source(invalid_map)
    assert map_error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE

    invalid_set = """\
fn main() -> i64:
    mut values: set<tryte> = set_new<tryte>(1)
    return set_len<tryte>(&values)
"""
    with pytest.raises(SemanticError) as set_error:
        compile_source(invalid_set)
    assert set_error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE
