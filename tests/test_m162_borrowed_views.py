from __future__ import annotations

import pytest

from bootstrap.s3.dynamic import (
    BorrowConflictError,
    BufferBoundsError,
    DynamicBytes,
    DynamicText,
    DynamicVector,
    TextBoundaryError,
)
from bootstrap.s3.pipeline import run_source


def test_static_array_slice_abi_remains_zero_copy_and_lexical() -> None:
    source = """\
fn sum(values: &[i64]) -> i64:
    return values[0] + values[1]
fn main() -> i64:
    values: i64[2] = [7, 8]
    return sum(&values)
"""
    assert run_source(source, optimization="O0") == 15
    assert run_source(source, optimization="O1") == 15


def test_vector_view_is_borrowed_in_place_and_blocks_owner_mutation() -> None:
    values = DynamicVector("i64", 4, _data=(10, 20, 30))
    view = values.borrow_range(1, 3)
    assert view.length == 2
    assert [view[0], view[1]] == [20, 30]
    with pytest.raises(BorrowConflictError):
        values.set(1, 99)
    view.close()
    values.set(1, 99)
    assert values[1] == 99


def test_mutable_byte_view_updates_owner_and_bounds_are_relative() -> None:
    data = DynamicBytes(4, _data=b"abcd")
    view = data.borrow_range(1, 3, mutable=True)
    view[0] = ord("X")
    assert data.to_bytes() == b"aXcd"
    with pytest.raises(BufferBoundsError):
        _ = view[2]
    view.close()


def test_text_view_requires_utf8_boundaries_and_is_read_only() -> None:
    text = DynamicText("aéz")
    view = text.borrow_range(1, 3)
    assert view.length == 2
    assert bytes(view[index] for index in range(view.length)) == "é".encode("utf-8")
    with pytest.raises(BorrowConflictError):
        text.borrow_range(1, 3, mutable=True)
    view.close()
    with pytest.raises(TextBoundaryError):
        text.borrow_range(2, 3)
