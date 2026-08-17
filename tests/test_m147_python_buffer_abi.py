from __future__ import annotations

from array import array

import pytest

from bootstrap.s3.dynamic import BorrowConflictError, DynamicBytes, DynamicText
from bootstrap.s3.ffi import FFISignature, FFIType
from bootstrap.s3.python_buffer_abi import (
    ABIStatus,
    BufferDescriptor,
    BufferReadOnlyError,
    BufferReleasedError,
    BufferViewError,
    adapt_python_buffer,
    borrow_s3_bytes,
    call_with_python_buffer,
    call_with_s3_bytes,
    copy_to_s3_bytes,
    copy_to_s3_text,
    render_abi_manifest,
    render_c_header,
)


def test_descriptor_is_canonical_little_endian_twelve_bytes() -> None:
    descriptor = BufferDescriptor(0, 3, 8)
    assert descriptor.to_bytes() == bytes.fromhex("000000000300000008000000")
    assert BufferDescriptor.from_bytes(descriptor.to_bytes()) == descriptor
    with pytest.raises(ValueError, match="exactly 12"):
        BufferDescriptor.from_bytes(b"short")


def test_python_read_only_and_writable_views_are_explicit() -> None:
    with adapt_python_buffer(b"abc") as readonly:
        assert readonly.to_bytes() == b"abc"
        assert readonly.writable is False
        with pytest.raises(BufferReadOnlyError):
            readonly[0] = 65
    data = bytearray(b"abc")
    with adapt_python_buffer(data, writable=True) as writable:
        writable[1] = 90
    assert data == bytearray(b"aZc")


def test_python_buffer_profile_rejects_non_byte_and_noncontiguous_views() -> None:
    with pytest.raises(BufferViewError, match="one-dimensional"):
        adapt_python_buffer(array("I", [1]))
    data = bytearray(b"abcd")
    with pytest.raises(BufferViewError, match="one-dimensional"):
        adapt_python_buffer(memoryview(data)[::2])
    with pytest.raises(BufferViewError, match="one-dimensional"):
        adapt_python_buffer(memoryview(data)[::-1])


def test_release_is_idempotent_and_use_after_release_is_rejected() -> None:
    view = adapt_python_buffer(b"abc")
    view.close()
    view.close()
    assert view.closed is True
    with pytest.raises(BufferReleasedError):
        view.to_bytes()


def test_s3_borrow_blocks_reallocation_and_releases_before_retry() -> None:
    value = DynamicBytes(3, _data=b"ab")
    view = borrow_s3_bytes(value)
    assert view.descriptor.capacity == 3
    with pytest.raises(BorrowConflictError):
        value.reserve(4)
    view.close()
    value.reserve(4)
    assert value.capacity == 4


def test_s3_writable_borrow_and_text_view_preserve_owned_storage() -> None:
    value = DynamicBytes(3, _data=b"abc")
    with borrow_s3_bytes(value, writable=True) as view:
        view[0] = 90
    assert value.to_bytes() == b"Zbc"
    text = DynamicText.from_static("Aé")
    with borrow_s3_bytes(value) as _:
        pass
    from bootstrap.s3.python_buffer_abi import borrow_s3_text

    with borrow_s3_text(text) as view:
        assert view.to_bytes() == "Aé".encode("utf-8")


def test_copy_is_the_explicit_retention_operation() -> None:
    data = bytearray(b"abc")
    retained = copy_to_s3_bytes(data)
    data[0] = 90
    assert retained.to_bytes() == b"abc"
    retained_text = copy_to_s3_text("é".encode("utf-8"))
    assert retained_text.to_string() == "é"


def test_call_boundary_returns_closed_status_instead_of_exception() -> None:
    readonly = call_with_python_buffer(b"abc", lambda view: view[0] + 1, writable=True)
    assert readonly.status is ABIStatus.READ_ONLY
    assert readonly.ok is False
    assert readonly.error is not None
    assert readonly.error.code == "BufferReadOnlyError"
    conflict_owner = DynamicBytes(1)
    active = borrow_s3_bytes(conflict_owner)
    try:
        conflict = call_with_s3_bytes(conflict_owner, lambda _view: None, writable=True)
    finally:
        active.close()
    assert conflict.status is ABIStatus.BORROW_CONFLICT


def test_manifest_and_header_are_deterministic_for_mixed_scalar_buffer_abi() -> None:
    signatures = (
        FFISignature("zeta", (FFIType.BYTES_VIEW, FFIType.I64), FFIType.F64),
        FFISignature("alpha", (FFIType.TEXT_VIEW,), FFIType.I64),
    )
    manifest = render_abi_manifest(signatures)
    assert manifest == render_abi_manifest(tuple(reversed(signatures)))
    assert '"schema_version": "s3.python-buffer-abi.v1"' in manifest
    header = render_c_header(signatures)
    assert header == render_c_header(tuple(reversed(signatures)))
    assert "typedef struct" in header
    assert "s3_bytes_view_v1 arg0" in header
    assert "S3_API double zeta" in header
