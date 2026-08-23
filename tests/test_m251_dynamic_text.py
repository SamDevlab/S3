"""M2.51 owned and bounded dynamic text contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.dynamic import (
    BufferFullError,
    DynamicError,
    DynamicText,
    MovedValueError,
    TextEncodingError,
)


def test_dynamic_text_move_transfers_owned_storage() -> None:
    original = DynamicText.from_static("S3")
    moved = original.move()
    assert moved.to_string() == "S3"
    with pytest.raises(MovedValueError):
        original.to_string()


def test_dynamic_text_append_is_bounded_and_failure_is_atomic() -> None:
    text = DynamicText.new(4)
    text.append_static("ab")
    with pytest.raises(BufferFullError):
        text.append_static("cde")
    assert text.to_string() == "ab"
    assert text.length == 2


def test_dynamic_text_rejects_invalid_unicode_deterministically() -> None:
    with pytest.raises(TextEncodingError, match="invalid Unicode"):
        DynamicText("\ud800")
    text = DynamicText.new(2)
    with pytest.raises(TextEncodingError, match="invalid Unicode"):
        text.append_static("\ud800")
    assert text.length == 0


def test_dynamic_text_operations_reject_wrong_value_families() -> None:
    text = DynamicText.from_static("S3")
    with pytest.raises(DynamicError, match="append requires"):
        text.append(1)  # type: ignore[arg-type]
    with pytest.raises(DynamicError, match="find requires"):
        text.find("S3")  # type: ignore[arg-type]

