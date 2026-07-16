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


def _read_lf_normalized_golden_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").encode("utf-8")


def test_first_fixture_output_probe_matches_inspect_golden() -> None:
    document = build_first_fixture_assembly_text()
    expected = _read_lf_normalized_golden_bytes(FIRST_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.text
    assert document.utf8_bytes == expected
    assert document.byte_count == len(expected)
    assert document.line_count == 18
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert document.sha256 == "46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67"
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_first_fixture_output_probe_does_not_create_actual_output_root() -> None:
    build_first_fixture_assembly_text()

    assert not ACTUAL_OUTPUT_ROOT.exists()
