from __future__ import annotations

import hashlib
from pathlib import Path

from bootstrap.s3.assembly_text_probe import build_first_fixture_assembly_text
from bootstrap.s3.static_text import StaticTextDocument


REPO_ROOT = Path(__file__).resolve().parents[1]
FIRST_ASSEMBLY_GOLDEN = REPO_ROOT / "tests" / "golden" / "inspect" / "first.assembly.txt"
ACTUAL_OUTPUT_ROOT = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_actual"
)
FIRST_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "first.assembly.txt"
SIMPLE_CALL_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "simple_call.assembly.txt"
SIGN_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "sign.assembly.txt"


def _read_lf_normalized_golden_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").encode("utf-8")


def test_first_fixture_output_probe_matches_inspect_golden() -> None:
    document = build_first_fixture_assembly_text()
    expected = _read_lf_normalized_golden_bytes(FIRST_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.text
    assert document.utf8_bytes == expected
    assert document.byte_count == len(expected)
    assert document.line_count == 16
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert document.sha256 == "31a70bf2e3b61ba920b0ca680702d287f7db9a4caa6ed2241cbfdba998a69316"
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_first_fixture_actual_output_matches_probe_and_golden() -> None:
    document = build_first_fixture_assembly_text()
    expected = _read_lf_normalized_golden_bytes(FIRST_ASSEMBLY_GOLDEN)
    actual = FIRST_ACTUAL_OUTPUT.read_text(encoding="utf-8").encode("utf-8")

    assert FIRST_ACTUAL_OUTPUT.is_file()
    assert actual == document.utf8_bytes
    assert actual == expected
    assert len(actual) == 377
    assert len(actual.decode("utf-8").splitlines()) == 16
    assert (
        hashlib.sha256(actual).hexdigest()
        == "31a70bf2e3b61ba920b0ca680702d287f7db9a4caa6ed2241cbfdba998a69316"
    )
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")


def test_first_fixture_expected_and_actual_are_byte_for_byte_equal() -> None:
    expected = _read_lf_normalized_golden_bytes(FIRST_ASSEMBLY_GOLDEN)
    actual = FIRST_ACTUAL_OUTPUT.read_text(encoding="utf-8").encode("utf-8")

    assert actual == expected


def test_first_simple_call_and_sign_actual_outputs_exist() -> None:
    assert FIRST_ACTUAL_OUTPUT.is_file()
    assert SIMPLE_CALL_ACTUAL_OUTPUT.is_file()
    assert SIGN_ACTUAL_OUTPUT.is_file()
