from __future__ import annotations

import pytest

from bootstrap.s3.lsp import LanguageServer, LspError


SOURCE = (
    "fn add(value: i64) -> i64:\n"
    "    return value\n"
    "fn main() -> i64:\n"
    "    return add(3)\n"
)


def test_initialize_and_document_symbols_are_deterministic() -> None:
    server = LanguageServer()
    assert server.initialize()["capabilities"]["hoverProvider"] is True
    server.did_open("file:///main.s3", SOURCE)
    symbols = server.document_symbols("file:///main.s3")
    assert [item["name"] for item in symbols] == ["add", "main"]
    assert symbols[0]["detail"] == "fn add(value: i64) -> i64"


def test_diagnostics_and_full_document_change() -> None:
    server = LanguageServer()
    opened = server.did_open(
        "file:///main.s3",
        "fn main() -> i64:\n    return missing(3)\n",
    )
    assert len(opened["diagnostics"]) == 1
    changed = server.did_change("file:///main.s3", SOURCE, 2)
    assert changed["diagnostics"] == []


def test_hover_definition_and_completion_use_known_symbols() -> None:
    server = LanguageServer()
    server.did_open("file:///main.s3", SOURCE)
    hover = server.hover("file:///main.s3", {"line": 3, "character": 12})
    assert hover is not None
    assert "fn add(value: i64) -> i64" in hover["contents"]["value"]
    definition = server.definition("file:///main.s3", {"line": 3, "character": 12})
    assert definition[0]["range"]["start"] == {"line": 0, "character": 3}
    assert [item["label"] for item in server.completion("file:///main.s3", {"line": 3, "character": 12})] == ["add"]


def test_incremental_range_changes_and_unknown_documents_are_rejected() -> None:
    server = LanguageServer()
    with pytest.raises(LspError):
        server.did_change("file:///main.s3", [{"range": {}, "text": SOURCE}], 2)
    with pytest.raises(LspError):
        server.hover("file:///missing.s3", {"line": 0, "character": 0})
