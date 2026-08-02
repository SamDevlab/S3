from __future__ import annotations

from pathlib import Path


ADR_PATH = Path("docs/decisions/ADR-0021-enum-payload-layout-gate.md")


def test_adr_0021_accepts_fixed_tagged_multi_cell_layout() -> None:
    text = ADR_PATH.read_text(encoding="utf-8")

    assert "Status: Accepted" in text
    assert "tag, payload_cell_0" in text
    assert "the tag is always cell 0" in text
    assert "inactive payload slots are deterministically initialized" in text
    assert "IR JSON remains `0.5.0`" in text
    assert "S3 Assembly remains `0.5.0`" in text
    assert "ABI remains unchanged" in text
    assert "multi-cell enum returns" in text
