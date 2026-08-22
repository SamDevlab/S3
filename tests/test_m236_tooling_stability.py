from __future__ import annotations

import io

import pytest

from bootstrap.s3.lsp import LanguageServer
from bootstrap.s3.lsp_transport import JsonRpcTransport, LspTransportError


pytestmark = pytest.mark.s3_fast


def test_lsp_indexes_open_documents_and_resolves_unique_project_symbols() -> None:
    server = LanguageServer()
    server.did_open(
        "file:///lib.s3",
        "fn add(value: i64) -> i64:\n    return value\n",
        1,
    )
    server.did_open(
        "file:///main.s3",
        "fn main() -> i64:\n    return add(3)\n",
        1,
    )

    symbols = server.workspace_symbols("AD")
    assert [(item["name"], item["uri"]) for item in symbols] == [("add", "file:///lib.s3")]
    definition = server.definition("file:///main.s3", {"line": 1, "character": 12})
    assert definition[0]["uri"] == "file:///lib.s3"
    references = server.references("file:///main.s3", {"line": 1, "character": 12})
    assert [item["uri"] for item in references] == ["file:///lib.s3", "file:///main.s3"]
    changes = server.rename("file:///main.s3", {"line": 1, "character": 12}, "sum")["changes"]
    assert sorted(changes) == ["file:///lib.s3", "file:///main.s3"]


def test_lsp_duplicate_project_symbols_remain_document_local() -> None:
    server = LanguageServer()
    source = "fn same() -> i64:\n    return 1\n"
    server.did_open("file:///a.s3", source, 1)
    server.did_open("file:///b.s3", source, 1)
    definition = server.definition("file:///a.s3", {"line": 0, "character": 4})
    assert definition[0]["uri"] == "file:///a.s3"
    changes = server.rename("file:///a.s3", {"line": 0, "character": 4}, "left")["changes"]
    assert sorted(changes) == ["file:///a.s3"]


def test_json_rpc_accepts_cancellation_notifications_and_rejects_duplicate_headers() -> None:
    transport = JsonRpcTransport()
    assert transport.dispatch(
        {
            "jsonrpc": "2.0",
            "method": "$/cancelRequest",
            "params": {"id": 7},
        }
    ) is None
    with pytest.raises(LspTransportError, match="duplicate"):
        transport.read_message(
            io.BytesIO(
                b"Content-Length: 2\r\ncontent-length: 2\r\n\r\n{}"
            )
        )
