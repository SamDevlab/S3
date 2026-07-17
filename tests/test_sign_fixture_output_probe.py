from __future__ import annotations

import hashlib
from pathlib import Path

from bootstrap.s3.assembly_text_probe import build_sign_fixture_assembly_text
from bootstrap.s3.static_text import StaticTextDocument


REPO_ROOT = Path(__file__).resolve().parents[1]
SIGN_ASSEMBLY_GOLDEN = REPO_ROOT / "tests" / "golden" / "inspect" / "sign.assembly.txt"
ACTUAL_OUTPUT_ROOT = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_actual"
)
FIRST_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "first.assembly.txt"
SIMPLE_CALL_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "simple_call.assembly.txt"
SIGN_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "sign.assembly.txt"


def _read_lf_normalized_golden_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def test_sign_fixture_output_probe_matches_lf_normalized_inspect_golden() -> None:
    document = build_sign_fixture_assembly_text()
    expected = _read_lf_normalized_golden_bytes(SIGN_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.text
    assert document.utf8_bytes == expected
    assert document.byte_count == len(expected)
    assert document.byte_count == 946
    assert document.line_count == expected.count(b"\n")
    assert document.line_count == 36
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert (
        document.sha256
        == "c077d2c49639b1a033505ec8c1ba1c60c78242e6e09c43f60a8aa5ed8b49e2d9"
    )
    assert document.text.endswith("\n")
    assert document.utf8_bytes.endswith(b"\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_sign_fixture_probe_does_not_create_actual_output() -> None:
    document = build_sign_fixture_assembly_text()

    assert document.utf8_bytes
    assert FIRST_ACTUAL_OUTPUT.is_file()
    assert SIMPLE_CALL_ACTUAL_OUTPUT.is_file()
    assert not SIGN_ACTUAL_OUTPUT.exists()
