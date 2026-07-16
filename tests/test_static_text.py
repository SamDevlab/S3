from __future__ import annotations

import hashlib

import pytest

from bootstrap.s3.static_text import (
    StaticTextDecodeError,
    decode_static_text,
    encode_static_text,
    normalize_static_text_newlines,
    static_text_metadata,
)


def test_static_text_ascii_encodes_to_deterministic_utf8_bytes() -> None:
    assert encode_static_text("TRET r0") == b"TRET r0"


def test_static_text_normalizes_newlines_to_lf() -> None:
    assert normalize_static_text_newlines("a\r\nb\rc") == "a\nb\nc"
    assert encode_static_text("a\\nb") == b"a\nb"


def test_static_text_metadata_is_deterministic() -> None:
    metadata = static_text_metadata("alpha\\nbeta")
    data = b"alpha\nbeta"

    assert metadata.byte_count == len(data)
    assert metadata.line_count == 2
    assert metadata.sha256 == hashlib.sha256(data).hexdigest()


def test_static_text_supported_escapes_decode_explicitly() -> None:
    assert decode_static_text(r"quote: \" slash: \\ newline:\n.") == (
        'quote: " slash: \\ newline:\n.'
    )


def test_static_text_unsupported_escape_fails_deterministically() -> None:
    with pytest.raises(StaticTextDecodeError) as captured:
        decode_static_text(r"bad\t")

    assert "unsupported static text escape '\\t' at offset 3" == str(
        captured.value
    )
