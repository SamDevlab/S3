from __future__ import annotations

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.dynamic import (
    Allocator,
    BorrowConflictError,
    BufferBoundsError,
    BufferFullError,
    DynamicBytes,
    DynamicText,
    TextBoundaryError,
    TextEncodingError,
    bytes_from_text,
    text_from_bytes,
)


def test_bytes_use_exact_capacity_and_explicit_reserve() -> None:
    value = DynamicBytes(2)
    value.push(65)
    value.push(66)
    assert value.to_bytes() == b"AB"
    with pytest.raises(BufferFullError):
        value.push(67)
    value.reserve(4)
    value.push(67)
    assert value.capacity == 4
    assert value.to_bytes() == b"ABC"


def test_bytes_copy_slice_concat_and_checked_access() -> None:
    left = DynamicBytes(3)
    for item in (1, 2, 3):
        left.push(item)
    right = left.clone()
    right.set(1, 9)
    assert left.to_bytes() == bytes((1, 2, 3))
    assert right.to_bytes() == bytes((1, 9, 3))
    assert left.slice(1, 3).to_bytes() == bytes((2, 3))
    assert left.concat(right).to_bytes() == bytes((1, 2, 3, 1, 9, 3))
    with pytest.raises(BufferBoundsError):
        left.get(3)


def test_borrow_conflicts_block_owner_invalidation() -> None:
    value = DynamicBytes(2)
    value.push(7)
    shared = value.borrow()
    with pytest.raises(BorrowConflictError):
        value.reserve(4)
    with pytest.raises(BorrowConflictError):
        value.borrow(mutable=True)
    shared.close()
    value.reserve(4)
    assert value.capacity == 4


def test_text_is_utf8_and_uses_byte_lengths() -> None:
    value = DynamicText.from_static("Aé")
    assert value.length == 3
    assert value.capacity == 3
    with pytest.raises(TextBoundaryError):
        value.slice(1, 2)
    assert value.slice(1, 3).to_string() == "é"
    raw = DynamicBytes(2)
    raw.push(0xC3)
    raw.push(0xA9)
    assert text_from_bytes(raw).to_string() == "é"
    invalid = DynamicBytes(1)
    invalid.push(0xFF)
    with pytest.raises(TextEncodingError):
        text_from_bytes(invalid)


def test_allocator_limit_is_checked_before_allocation() -> None:
    allocator = Allocator(max_bytes=3)
    DynamicBytes(3, allocator=allocator)
    with pytest.raises(Exception, match="active limit"):
        DynamicBytes(4, allocator=allocator)


def test_dynamic_buffers_lower_and_execute_through_ir_emulator() -> None:
    source = """\
fn main() -> tryte:
    mut data: bytes = bytes_new(2)
    discard bytes_push(&mut data, 65)
    discard bytes_push(&mut data, 66)
    return bytes_get(&data, 1)
"""
    compilation = compile_source(source)
    assert compilation.semantic_model.contains_dynamic
    assert any(
        instruction.callee == "bytes_push"
        for instruction in compilation.ir.functions[0].instructions
    )
    assert run_source(source) == 66


def test_dynamic_text_round_trip_through_source_pipeline() -> None:
    source = """\
fn main() -> i64:
    mut value: text = text_from_static("S3")
    discard text_reserve(&mut value, 10)
    discard text_append_static(&mut value, " runtime")
    return text_len(&value)
"""
    assert run_source(source) == len("S3 runtime".encode("utf-8"))


def test_dynamic_move_is_linear_in_semantic_analysis() -> None:
    source = """\
fn main() -> bytes:
    first: bytes = bytes_new(1)
    second: bytes = first
    return first
"""
    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_USE_AFTER_MOVE


def test_dynamic_borrow_conflict_is_rejected_lexically() -> None:
    source = """\
fn main() -> i64:
    mut value: bytes = bytes_new(1)
    borrow: &bytes = &value
    discard bytes_reserve(&mut value, 2)
    return bytes_len(borrow)
"""
    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_BORROW_CONFLICT
