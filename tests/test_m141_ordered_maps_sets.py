from __future__ import annotations

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.dynamic import (
    BufferBoundsError,
    BufferFullError,
    DynamicMap,
    DynamicSet,
)


def test_map_replaces_without_reordering_and_removes_by_compaction() -> None:
    value = DynamicMap(3)
    value.put(10, 1)
    value.put(20, 2)
    value.put(10, 9)
    assert value.key_at(0) == 10
    assert value.value_at(0) == 9
    value.remove(10)
    assert value.key_at(0) == 20
    assert value.length == 1


def test_set_is_ordered_and_deduplicates() -> None:
    value = DynamicSet(2)
    value.add(4)
    value.add(4)
    value.add(5)
    assert value.length == 2
    assert value.at(0) == 4
    assert value.at(1) == 5
    assert value.contains(4) == -1
    value.remove(4)
    assert value.at(0) == 5


def test_map_and_set_capacity_and_bounds_are_deterministic() -> None:
    value = DynamicMap(1)
    value.put(1, 2)
    with pytest.raises(BufferFullError):
        value.put(3, 4)
    with pytest.raises(BufferBoundsError):
        value.key_at(1)
    collection = DynamicSet(0)
    with pytest.raises(BufferFullError):
        collection.add(1)


def test_map_source_pipeline_preserves_insertion_order() -> None:
    source = """\
fn main() -> i64:
    mut values: i64_map = i64_map_new(3)
    discard i64_map_put(&mut values, 7, 70)
    discard i64_map_put(&mut values, 8, 80)
    discard i64_map_put(&mut values, 7, 77)
    return i64_map_value_at(&values, 0)
"""
    assert run_source(source) == 77


def test_set_source_pipeline_compacts_after_remove() -> None:
    source = """\
fn main() -> i64:
    mut values: i64_set = i64_set_new(3)
    discard i64_set_add(&mut values, 7)
    discard i64_set_add(&mut values, 8)
    discard i64_set_remove(&mut values, 7)
    return i64_set_at(&values, 0)
"""
    assert run_source(source) == 8


def test_map_move_and_borrow_rules_reuse_m139_ownership_contract() -> None:
    moved = """\
fn main() -> i64:
    first: i64_map = i64_map_new(1)
    second: i64_map = first
    return i64_map_len(&first)
"""
    with pytest.raises(SemanticError) as error:
        compile_source(moved)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_USE_AFTER_MOVE

    borrowed = """\
fn main() -> i64:
    mut values: i64_set = i64_set_new(1)
    view: &i64_set = &values
    discard i64_set_reserve(&mut values, 2)
    return i64_set_len(view)
"""
    with pytest.raises(SemanticError) as error:
        compile_source(borrowed)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_BORROW_CONFLICT


def test_map_and_set_native_calls_lower_to_collection_runtime() -> None:
    source = """\
fn main() -> i64:
    mut values: i64_map = i64_map_new(1)
    discard i64_map_put(&mut values, 7, 42)
    return i64_map_get(&values, 7)
"""
    native = X8664Backend().generate(compile_source(source).assembly)
    assert "__s3_builtin_i64_map_new" in native
    assert "__s3_builtin_i64_map_put" in native
    assert "__s3_builtin_i64_map_get" in native
