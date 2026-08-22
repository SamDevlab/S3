from __future__ import annotations

import io
import json

import pytest

from bootstrap.s3.lsp import LspError
from bootstrap.s3.lsp_transport import JsonRpcTransport, LspTransportError


SOURCE = "fn main() -> i64:\n    return 1\n"


def _message(payload: dict[str, object]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


def test_json_rpc_lifecycle_and_diagnostics_use_bounded_framing() -> None:
    transport = JsonRpcTransport(max_message_bytes=4096)
    initialize = transport.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert initialize is not None
    assert initialize.payload["result"]["serverInfo"]["name"] == "s3-language-server"  # type: ignore[index]
    opened = transport.dispatch({
        "jsonrpc": "2.0", "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///main.s3", "text": SOURCE, "version": 1}},
    })
    assert opened is None
    assert transport.dispatch({"jsonrpc": "2.0", "id": 2, "method": "textDocument/documentSymbol", "params": {"textDocument": {"uri": "file:///main.s3"}}}).payload["result"]  # type: ignore[union-attr]


def test_unknown_method_and_malformed_or_oversized_messages_fail_closed() -> None:
    transport = JsonRpcTransport(max_message_bytes=32)
    unknown = transport.dispatch({"jsonrpc": "2.0", "id": 4, "method": "textDocument/implementation"})
    assert unknown is not None
    assert unknown.error is not None and unknown.error["code"] == -32601
    with pytest.raises(LspTransportError, match="exceeds bound"):
        transport.read_message(io.BytesIO(b"Content-Length: 33\r\n\r\n" + b"x" * 33))


def test_document_versions_are_monotonic_and_exit_stops_transport() -> None:
    transport = JsonRpcTransport()
    assert transport.dispatch({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": "file:///main.s3", "text": SOURCE, "version": 3}}}) is None
    with pytest.raises(LspError, match="increase"):
        transport.server.did_change("file:///main.s3", SOURCE, 3)
    assert transport.dispatch({"jsonrpc": "2.0", "id": 5, "method": "exit"}) is not None
    assert transport.stopped
    assert transport.dispatch({"jsonrpc": "2.0", "id": 6, "method": "initialize"}) is None


def test_reference_and_rename_requests_use_lexed_semantic_symbols() -> None:
    transport = JsonRpcTransport()
    source = (
        "fn add(value: i64) -> i64:\n"
        "    return value\n"
        "fn main() -> i64:\n"
        "    return add(3)\n"
    )
    opened = transport.dispatch({
        "jsonrpc": "2.0", "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///main.s3", "text": source, "version": 1}},
    })
    assert opened is None
    params = {"textDocument": {"uri": "file:///main.s3"}, "position": {"line": 3, "character": 12}}
    references = transport.dispatch({"jsonrpc": "2.0", "id": 7, "method": "textDocument/references", "params": params})
    assert references is not None and len(references.payload["result"]) == 2  # type: ignore[arg-type]
    renamed = transport.dispatch({
        "jsonrpc": "2.0", "id": 8, "method": "textDocument/rename",
        "params": {**params, "newName": "sum"},
    })
    assert renamed is not None
    assert len(renamed.payload["result"]["changes"]["file:///main.s3"]) == 2  # type: ignore[index]
    invalid = transport.dispatch({
        "jsonrpc": "2.0", "id": 9, "method": "textDocument/rename",
        "params": {**params, "newName": "not-valid!"},
    })
    assert invalid is not None and invalid.error is not None and invalid.error["code"] == -32602


def test_serve_writes_json_rpc_response() -> None:
    incoming = io.BytesIO(_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
    outgoing = io.BytesIO()
    JsonRpcTransport().serve(incoming, outgoing)
    assert b"Content-Length:" in outgoing.getvalue()
