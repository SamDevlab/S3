from __future__ import annotations

import hashlib

import pytest

from bootstrap.s3.static_text import (
    StaticTextDecodeError,
    StaticTextBuilder,
    StaticTextDocument,
    StaticTextLineEmitter,
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


def test_static_text_document_normalizes_and_exposes_metadata() -> None:
    document = StaticTextDocument("alpha\r\nbeta\r")

    assert document.text == "alpha\nbeta\n"
    assert document.utf8_bytes == b"alpha\nbeta\n"
    assert document.byte_count == 11
    assert document.line_count == 2
    assert (
        document.sha256
        == "e49c81e2d2f84e259d40e2fb8192f3bcd198b355184845d76d8f58807d0d78ee"
    )


def test_static_text_builder_composes_deterministic_document() -> None:
    first = (
        StaticTextBuilder()
        .append_text("hello")
        .append_text("\r\n")
        .append_literal(r"quote: \"")
        .append_line()
        .append_line("done")
        .build()
    )
    second = (
        StaticTextBuilder()
        .append_text("hello\n")
        .append_literal(r"quote: \"")
        .append_line()
        .append_line("done")
        .build()
    )

    assert first == second
    assert first.text == 'hello\nquote: "\ndone\n'
    assert first.utf8_bytes == b'hello\nquote: "\ndone\n'
    assert first.byte_count == 20
    assert first.line_count == 3


def test_static_text_builder_empty_document_is_deterministic() -> None:
    document = StaticTextBuilder().build()

    assert document.text == ""
    assert document.utf8_bytes == b""
    assert document.byte_count == 0
    assert document.line_count == 0
    assert (
        document.sha256
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_static_text_builder_reports_literal_decode_errors() -> None:
    builder = StaticTextBuilder()

    with pytest.raises(StaticTextDecodeError):
        builder.append_literal(r"bad\t")


def test_static_text_line_emitter_builds_lf_terminated_lines() -> None:
    document = (
        StaticTextLineEmitter()
        .emit_line("header")
        .emit_blank_line()
        .emit_line("body")
        .build()
    )

    assert document.text == "header\n\nbody\n"
    assert document.utf8_bytes == b"header\n\nbody\n"
    assert document.byte_count == 13
    assert document.line_count == 3
    assert document.sha256 == hashlib.sha256(document.utf8_bytes).hexdigest()


def test_static_text_line_emitter_supports_literal_lines_and_indentation() -> None:
    document = (
        StaticTextLineEmitter(indent_text="  ")
        .emit_line(".function main")
        .emit_literal_line(r"TRET r0 ; \"done\"", indent=1)
        .build()
    )

    assert document.text == '.function main\n  TRET r0 ; "done"\n'
    assert document.utf8_bytes == b'.function main\n  TRET r0 ; "done"\n'
    assert document.line_count == 2


def test_static_text_line_emitter_normalizes_line_newlines() -> None:
    document = StaticTextLineEmitter().emit_line("a\r\nb\rc").build()

    assert document.text == "a\nb\nc\n"
    assert document.line_count == 3


def test_static_text_line_emitter_rejects_invalid_indentation() -> None:
    with pytest.raises(ValueError):
        StaticTextLineEmitter(indent_text="\t\n")

    emitter = StaticTextLineEmitter()
    with pytest.raises(ValueError):
        emitter.emit_line("bad", indent=-1)
    with pytest.raises(TypeError):
        emitter.emit_line("bad", indent=True)


def test_static_text_line_emitter_reports_literal_decode_errors() -> None:
    emitter = StaticTextLineEmitter()

    with pytest.raises(StaticTextDecodeError):
        emitter.emit_literal_line(r"bad\t")
