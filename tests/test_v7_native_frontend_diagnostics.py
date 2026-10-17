from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from bootstrap.s3 import compiler_provider
from bootstrap.s3.diagnostics import (
    DiagnosticCode,
    LexError,
    ParseError,
    diagnostic_from_exception,
)
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.native_compiler import (
    NativeDiagnosticCode,
    NativeS3CExecutable,
    NativeSourceSetResult,
    decode_output_envelope_v2,
)
from bootstrap.s3.pipeline import compile_source, compile_sources
from tools.native_s3c_ng import compiler_source_set


_ROOT = Path(__file__).resolve().parents[1]
_CASES = (
    (
        "invalid_character",
        "module app\nfn main() -> i64:\n    return \x00\n",
        NativeDiagnosticCode.LEX_INVALID_CHARACTER,
        "LEX_INVALID_CHARACTER",
        2,
    ),
    (
        "unsupported_punctuation",
        "module app\nfn main() -> i64:\n    return @\n",
        NativeDiagnosticCode.LEX_INVALID_CHARACTER,
        "LEX_INVALID_CHARACTER",
        2,
    ),
    (
        "non_ascii_unsupported_symbol",
        "module app\nfn main() -> i64:\n    return π\n",
        NativeDiagnosticCode.LEX_INVALID_CHARACTER,
        "LEX_INVALID_CHARACTER",
        2,
    ),
    (
        "non_ascii_3byte_symbol",
        "module app\nfn main() -> i64:\n    return 中\n",
        NativeDiagnosticCode.LEX_INVALID_CHARACTER,
        "LEX_INVALID_CHARACTER",
        2,
    ),
    (
        "non_ascii_4byte_symbol",
        "module app\nfn main() -> i64:\n    return 💩\n",
        NativeDiagnosticCode.LEX_INVALID_CHARACTER,
        "LEX_INVALID_CHARACTER",
        2,
    ),
    (
        "unterminated_string",
        'module app\nfn main() -> i64:\n    return "oops\n',
        NativeDiagnosticCode.LEX_UNTERMINATED_STRING_LITERAL,
        "LEX_UNTERMINATED_STRING_LITERAL",
        2,
    ),
    (
        "unexpected_token",
        "module app\nfn main() -> i64:\n    return )\n",
        NativeDiagnosticCode.PARSE_SYNTAX,
        "PARSE_SYNTAX",
        3,
    ),
)


def _probe_app_source() -> str:
    declarations = [
        "module app",
        "from selfhost.compiler_ng.modules import NgSourceUnit, ng_emit_source_set_v2",
        "",
        "record ProbeOutput:",
        "    status: i64",
        "    diagnostics: vector<i64>",
        "",
        "fn main() -> i64:",
        "    return 0",
        "",
        "fn run_probe_bytes(contents: bytes) -> ProbeOutput:",
        "    mut path: text = text_from_static(\"fixture.s3\")",
        "    mut units: vector<NgSourceUnit> = vector_new<NgSourceUnit>(2)",
        "    discard vector_push<NgSourceUnit>(&mut units, NgSourceUnit(path=path, contents=contents))",
        "    mut source: bytes = bytes_new(4096)",
        "    mut events: vector<i64> = vector_new<i64>(128)",
        "    mut diagnostics: vector<i64> = vector_new<i64>(7)",
        "    mut status: i64 = ng_emit_source_set_v2(&units, text_from_static(\"app\"), &mut source, &mut events, &mut diagnostics)",
        "    return ProbeOutput(status=status, diagnostics=diagnostics)",
        "",
        "fn run_probe(source_text: text) -> ProbeOutput:",
        "    mut contents: bytes = bytes_from_text(&source_text)",
        "    return run_probe_bytes(contents)",
    ]
    for case_name, source_text, _, _, _ in _CASES:
        if case_name == "invalid_character":
            declarations.extend(
                (
                    "",
                    f"fn probe_{case_name}() -> ProbeOutput:",
                    "    mut prefix: text = text_from_static(\"module app\\nfn main() -> i64:\\n    return \" )",
                    "    mut prefix_bytes: bytes = bytes_from_text(&prefix)",
                    "    mut contents: bytes = bytes_new(128)",
                    "    mut index: i64 = 0",
                    "    while index < bytes_len(&prefix_bytes):",
                    "        discard bytes_push(&mut contents, bytes_get(&prefix_bytes, index))",
                    "        index = index + 1",
                    "    discard bytes_push(&mut contents, 0)",
                    "    discard bytes_push(&mut contents, 10)",
                    "    return run_probe_bytes(contents)",
                )
            )
        else:
            declarations.extend(
                (
                    "",
                    f"fn probe_{case_name}() -> ProbeOutput:",
                    f"    return run_probe(text_from_static({json.dumps(source_text, ensure_ascii=False)}))",
                )
            )
    return "\n".join(declarations) + "\n"


@pytest.fixture(scope="module")
def hosted_frontend_ir():
    sources = compiler_source_set(_ROOT)
    sources["app.s3"] = _probe_app_source()
    compilation = compile_sources(sources, entry_module="app")
    assert compilation.ir is not None
    return compilation.ir


def _probe_record(hosted_frontend_ir, case_name: str) -> tuple[int, tuple[int, ...]]:
    suffix = f"probe_{case_name}"
    entries = [function.name for function in hosted_frontend_ir.functions if function.name.endswith(suffix)]
    assert len(entries) == 1
    output = execute_ir(hosted_frontend_ir, entry=entries[0])
    assert isinstance(output, tuple) and len(output) == 2
    status, diagnostic_cells = output
    return int(status), tuple(int(value) for value in diagnostic_cells)


def _decode_record(status: int, cells: tuple[int, ...]):
    assert len(cells) == 7
    encoded = (
        b"S3NGOUT2"
        + struct.pack("<qQQQ", status, 0, 0, 1)
        + struct.pack("<7q", *cells)
    )
    return decode_output_envelope_v2(encoded)


@pytest.mark.parametrize(
    ("case_name", "source_text", "native_code", "python_code_name", "phase_id"),
    _CASES,
)
def test_native_frontend_diagnostic_matches_python_reference(
    case_name: str,
    source_text: str,
    native_code: NativeDiagnosticCode,
    python_code_name: str,
    phase_id: int,
    hosted_frontend_ir,
    monkeypatch,
) -> None:
    status, cells = _probe_record(hosted_frontend_ir, case_name)
    assert status != 0
    native_status, _, _, records = _decode_record(status, cells)
    assert native_status == status
    assert len(records) == 1
    record = records[0]
    assert (record.category_id, record.phase_id, record.code_id, record.message_id) == (
        2,
        phase_id,
        native_code,
        native_code,
    )
    assert record.source_unit_index == 0

    encoded_source = source_text.encode("utf-8")
    if case_name == "invalid_character":
        expected_start = encoded_source.index(b"\x00")
        expected_end = expected_start + 1
    elif case_name == "unsupported_punctuation":
        expected_start = encoded_source.index(b"@")
        expected_end = expected_start + 1
    elif case_name == "non_ascii_unsupported_symbol":
        expected_start = encoded_source.index("π".encode("utf-8"))
        expected_end = expected_start + len("π".encode("utf-8"))
    elif case_name == "non_ascii_3byte_symbol":
        expected_start = encoded_source.index("中".encode("utf-8"))
        expected_end = expected_start + len("中".encode("utf-8"))
    elif case_name == "non_ascii_4byte_symbol":
        expected_start = encoded_source.index("💩".encode("utf-8"))
        expected_end = expected_start + len("💩".encode("utf-8"))
    elif case_name == "unterminated_string":
        expected_start = encoded_source.index(b'"')
        expected_end = encoded_source.index(b"\n", expected_start)
    else:
        expected_start = encoded_source.rindex(b")")
        expected_end = expected_start + 1
    assert (record.start_byte, record.end_byte) == (expected_start, expected_end)

    with pytest.raises((LexError, ParseError)) as reference_error:
        compile_source(source_text)
    expected = diagnostic_from_exception(reference_error.value, file="fixture.s3")
    assert expected.code is getattr(DiagnosticCode, python_code_name)

    native_result = NativeSourceSetResult(
        status=native_status,
        source=b"",
        events=(),
        returncode=0,
        stdout=b"",
        stderr=b"",
        output_envelope_sha256=hashlib.sha256(b"").hexdigest(),
        output_envelope_bytes=0,
        elapsed_seconds=0.0,
        diagnostics=records,
    )
    monkeypatch.setattr(
        compiler_provider,
        "require_s3c_ng_executable",
        lambda _path: NativeS3CExecutable(Path("unused-s3c-ng"), "ng_emit_source_set_v2"),
    )
    monkeypatch.setattr(
        compiler_provider,
        "run_native_source_set",
        lambda *_args, **_kwargs: native_result,
    )
    with pytest.raises((LexError, ParseError)) as native_error:
        compiler_provider.compile_source_set_with_provider(
            {"fixture.s3": source_text}, compiler="s3c-ng"
        )
    actual = diagnostic_from_exception(native_error.value)

    assert actual.category is expected.category
    assert actual.phase is expected.phase
    assert actual.code is expected.code
    assert actual.file == expected.file
    assert actual.source == expected.source
    assert native_error.value.location == reference_error.value.location
