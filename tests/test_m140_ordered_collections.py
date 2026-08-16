from __future__ import annotations

import random

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.dynamic import (
    BufferBoundsError,
    BufferFullError,
    DynamicVector,
)


def test_vector_capacity_growth_pop_and_stable_iteration() -> None:
    value = DynamicVector("i64", 2)
    value.push(10)
    value.push(20)
    with pytest.raises(BufferFullError):
        value.push(30)
    value.reserve(4)
    value.push(30)
    assert value.length == 3
    assert value.capacity == 4
    assert tuple(value) == (10, 20, 30)
    assert value.pop() == 30
    assert tuple(value) == (10, 20)


def test_vector_indexing_and_slice_are_checked() -> None:
    value = DynamicVector("tryte", 3, _data=(1, 2, 3))
    assert value.get(1) == 2
    value.set(1, 9)
    assert value.slice(1, 3).get(0) == 9
    with pytest.raises(BufferBoundsError):
        value.get(3)
    empty = DynamicVector("tryte", 0)
    with pytest.raises(BufferBoundsError):
        empty.pop()


def test_vector_source_pipeline_is_type_specific_and_deterministic() -> None:
    source = """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(2)
    discard i64_vector_push(&mut values, 41)
    discard i64_vector_push(&mut values, 42)
    discard i64_vector_set(&mut values, 0, 7)
    return i64_vector_get(&values, 1)
"""
    compilation = compile_source(source)
    assert compilation.semantic_model.contains_dynamic
    assert run_source(source) == 42


def test_vector_clone_and_slice_preserve_order() -> None:
    source = """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(3)
    discard i64_vector_push(&mut values, 4)
    discard i64_vector_push(&mut values, 5)
    copy: i64_vector = i64_vector_clone(&values)
    part: i64_vector = i64_vector_slice(&copy, 1, 2)
    return i64_vector_get(&part, 0)
"""
    assert run_source(source) == 5


def test_f64_vector_uses_closed_element_signature() -> None:
    source = """\
fn main() -> i64:
    mut values: f64_vector = f64_vector_new(1)
    discard f64_vector_push(&mut values, 1.5)
    return f64_vector_len(&values)
"""
    assert run_source(source) == 1


def test_vector_move_is_linear() -> None:
    source = """\
fn main() -> i64:
    first: i64_vector = i64_vector_new(1)
    second: i64_vector = first
    return i64_vector_len(&first)
"""
    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_USE_AFTER_MOVE


def test_vector_borrow_blocks_reserve() -> None:
    source = """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(1)
    view: &i64_vector = &values
    discard i64_vector_reserve(&mut values, 2)
    return i64_vector_len(view)
"""
    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_BORROW_CONFLICT


def test_vector_native_calls_lower_to_private_descriptor_runtime() -> None:
    source = """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(1)
    discard i64_vector_push(&mut values, 42)
    return i64_vector_get(&values, 0)
"""
    compilation = compile_source(source)
    native = X8664Backend().generate(compilation.assembly)
    assert "__s3_builtin_i64_vector_new" in native
    assert "__s3_builtin_i64_vector_push" in native
    assert "__s3_builtin_i64_vector_get" in native


def test_fixed_seed_vector_trace_matches_reference_model() -> None:
    rng = random.Random(140)
    actual = DynamicVector("i64", 8)
    expected: list[int] = []
    for _ in range(64):
        operation = rng.randrange(3)
        if operation == 0 and len(expected) < actual.capacity:
            value = rng.randrange(-1000, 1001)
            actual.push(value)
            expected.append(value)
        elif operation == 1 and expected:
            index = rng.randrange(len(expected))
            value = rng.randrange(-1000, 1001)
            actual.set(index, value)
            expected[index] = value
        elif expected:
            assert actual.pop() == expected.pop()
        assert tuple(actual) == tuple(expected)


def test_dynamic_vector_o0_and_o1_are_equivalent() -> None:
    source = """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(2)
    discard i64_vector_push(&mut values, 11)
    discard i64_vector_push(&mut values, 22)
    return i64_vector_get(&values, 1)
"""
    assert run_source(source, optimization="O0") == run_source(source, optimization="O1") == 22
