from __future__ import annotations

import hashlib
from pathlib import Path

from bootstrap.s3.assembly_text_probe import build_simple_call_fixture_assembly_text
from bootstrap.s3.static_text import StaticTextDocument


REPO_ROOT = Path(__file__).resolve().parents[1]
SIMPLE_CALL_ASSEMBLY_GOLDEN = (
    REPO_ROOT / "tests" / "golden" / "inspect" / "simple_call.assembly.txt"
)
ACTUAL_OUTPUT_ROOT = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_actual"
)
SIMPLE_CALL_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "simple_call.assembly.txt"
SIGN_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "sign.assembly.txt"


def _read_lf_normalized_golden_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").encode("utf-8")


def test_simple_call_fixture_output_probe_matches_inspect_golden() -> None:
    document = build_simple_call_fixture_assembly_text()
    expected = _read_lf_normalized_golden_bytes(SIMPLE_CALL_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.text
    assert document.utf8_bytes == expected
    assert document.byte_count == len(expected)
    assert document.byte_count == 448
    assert document.line_count == len(
        expected.decode("utf-8").splitlines()
    )
    assert document.line_count == 21
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert (
        document.sha256
        == "a5cd6a06c66b44f328ce3d0c1368b4acf35a980f5d2040b051f903126f02552b"
    )
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_simple_call_actual_output_matches_probe_bytes() -> None:
    document = build_simple_call_fixture_assembly_text()
    actual = SIMPLE_CALL_ACTUAL_OUTPUT.read_bytes()

    assert SIMPLE_CALL_ACTUAL_OUTPUT.exists()
    assert actual == document.utf8_bytes
    assert actual == _read_lf_normalized_golden_bytes(SIMPLE_CALL_ASSEMBLY_GOLDEN)
    assert document.byte_count == 448
    assert document.line_count == 21
    assert (
        document.sha256
        == "a5cd6a06c66b44f328ce3d0c1368b4acf35a980f5d2040b051f903126f02552b"
    )
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")
    assert SIGN_ACTUAL_OUTPUT.is_file()
