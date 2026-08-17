from __future__ import annotations

import ctypes
import platform

import pytest

from bootstrap.s3.dynamic import (
    AllocationError,
    Allocator,
    DynamicBytes,
    DynamicError,
    DynamicKind,
    DynamicText,
    DynamicValue,
    OwnedBuffer,
)
from bootstrap.s3.ffi import build_shared_library


def test_dynamic_value_preserves_scalar_tag_and_value() -> None:
    value = DynamicValue.f64(0.25)
    assert value.kind is DynamicKind.F64
    assert value.require(DynamicKind.F64) == 0.25


def test_dynamic_value_rejects_implicit_numeric_conversion() -> None:
    value = DynamicValue.i64(4)
    with pytest.raises(DynamicError, match="expected f64"):
        value.require(DynamicKind.F64)


def test_dynamic_value_validates_closed_scalar_domains() -> None:
    with pytest.raises(DynamicError, match="trit"):
        DynamicValue.trit(2)
    with pytest.raises(DynamicError, match="must be an integer"):
        DynamicValue.tryte(1.0)  # type: ignore[arg-type]


def test_owned_buffer_grows_and_preserves_values() -> None:
    buffer = OwnedBuffer(int, capacity=1)
    buffer.push(4)
    old_capacity = buffer.capacity
    buffer.push(9)
    assert buffer.length == 2
    assert buffer.capacity > old_capacity
    assert [buffer[0], buffer[1]] == [4, 9]


def test_owned_buffer_borrow_is_bounded_and_mutable_without_copy() -> None:
    buffer = OwnedBuffer(int, capacity=2)
    buffer.push(4)
    buffer.push(9)
    view = buffer.borrow(mutable=True)
    assert view.address == buffer.address
    view[1] = 12
    assert buffer[1] == 12
    with pytest.raises(DynamicError, match="immutable"):
        buffer.borrow()[0] = 99


def test_owned_buffer_allocation_failure_is_deterministic() -> None:
    allocator = Allocator(max_elements=2)
    buffer = OwnedBuffer(int, allocator=allocator, capacity=1)
    buffer.push(1)
    buffer.push(2)
    with pytest.raises(AllocationError, match="exceeds limit"):
        buffer.push(3)


def test_owned_buffer_supports_all_closed_numeric_kinds() -> None:
    trits = OwnedBuffer(DynamicKind.TRIT, capacity=1)
    trits.push(-1)
    trytes = OwnedBuffer(DynamicKind.TRYTE, capacity=1)
    trytes.push(364)
    integers = OwnedBuffer(DynamicKind.I64, capacity=1)
    integers.push(2**62)
    floats = OwnedBuffer(DynamicKind.F64, capacity=1)
    floats.push(0.5)
    assert [trits[0], trytes[0], integers[0], floats[0]] == [-1, 364, 2**62, 0.5]


def test_dynamic_bytes_and_text_are_runtime_owned() -> None:
    data = DynamicBytes(capacity=1)
    data.push(65)
    data.reserve(2)
    data.push(66)
    assert data.length == 2
    text = DynamicText("S3")
    text.reserve(len("S3 runtime".encode("utf-8")))
    text.append_static(" runtime")
    assert text.to_string() == "S3 runtime"
    assert text.length == len("S3 runtime".encode("utf-8"))


@pytest.mark.skipif(platform.system() != "Linux", reason="requires Linux native FFI")
def test_owned_buffer_borrows_directly_into_s3_slice(tmp_path) -> None:
    source = """\
export fn sum(xs: &[i64]) -> i64:
    return xs[0] + xs[1]
export fn bump(xs: &mut [i64]) -> i64:
    xs[0] = xs[0] + 1
    return xs[0]
fn main() -> i64:
    return 0
"""
    library = build_shared_library(source, tmp_path / "libowned.so")
    lib = ctypes.CDLL(str(library))
    buffer = OwnedBuffer(int, capacity=2)
    buffer.push(7)
    buffer.push(8)
    pointer = ctypes.cast(buffer.address, ctypes.POINTER(ctypes.c_int64))
    lib.sum.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_int64]
    lib.sum.restype = ctypes.c_int64
    assert lib.sum(pointer, buffer.length) == 15
    lib.bump.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_int64]
    lib.bump.restype = ctypes.c_int64
    assert lib.bump(pointer, buffer.length) == 8
    assert buffer[0] == 8
