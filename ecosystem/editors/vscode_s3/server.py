"""stdio launcher adding the LSP diagnostics notification to S3's bounded transport."""

from __future__ import annotations

import json
import sys
from typing import BinaryIO, Mapping

from bootstrap.s3.formatter import format_source
from bootstrap.s3.lsp_transport import JsonRpcResponse, JsonRpcTransport, LspTransportError


def _write_notification(stream: BinaryIO, method: str, params: Mapping[str, object]) -> None:
    body = json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    stream.write(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
    stream.flush()


def serve(incoming: BinaryIO, outgoing: BinaryIO, errors: BinaryIO) -> None:
    transport = JsonRpcTransport()
    document_text: dict[str, str] = {}
    while not transport.stopped:
        request = transport.read_message(incoming)
        if request is None:
            return
        method = request.get("method")
        params = request.get("params", {})
        if isinstance(method, str) and method in {"textDocument/didOpen", "textDocument/didChange"} and "id" not in request:
            try:
                if not isinstance(params, Mapping):
                    raise LspTransportError("JSON-RPC params must be an object")
                document = params.get("textDocument")
                if not isinstance(document, Mapping) or not isinstance(document.get("uri"), str):
                    raise LspTransportError("document notification requires a URI")
                if method == "textDocument/didOpen":
                    text = document.get("text")
                else:
                    changes = params.get("contentChanges")
                    text = changes[0].get("text") if isinstance(changes, list) and len(changes) == 1 and isinstance(changes[0], Mapping) else None
                if not isinstance(text, str):
                    raise LspTransportError("document notification requires full source text")
                document_text[document["uri"]] = text
                report = transport._dispatch_method(str(method), params)
                if not isinstance(report, Mapping):
                    raise LspTransportError("document validation returned no diagnostics")
                _write_notification(outgoing, "textDocument/publishDiagnostics", report)
            except (LspTransportError, TypeError, ValueError, KeyError) as error:
                errors.write(f"s3 LSP notification rejected: {error}\n".encode("utf-8", errors="replace"))
                errors.flush()
            continue
        if method == "textDocument/didClose" and "id" not in request:
            try:
                if not isinstance(params, Mapping):
                    raise LspTransportError("JSON-RPC params must be an object")
                document = params.get("textDocument")
                if not isinstance(document, Mapping) or not isinstance(document.get("uri"), str):
                    raise LspTransportError("didClose requires a document URI")
                transport._dispatch_method(str(method), params)
                document_text.pop(document["uri"], None)
                _write_notification(
                    outgoing,
                    "textDocument/publishDiagnostics",
                    {"uri": document["uri"], "diagnostics": []},
                )
            except (LspTransportError, TypeError, ValueError, KeyError) as error:
                errors.write(f"s3 LSP close rejected: {error}\n".encode("utf-8", errors="replace"))
                errors.flush()
            continue
        if method == "textDocument/formatting" and "id" in request:
            try:
                if not isinstance(params, Mapping):
                    raise LspTransportError("formatting params must be an object")
                document = params.get("textDocument")
                if not isinstance(document, Mapping) or not isinstance(document.get("uri"), str):
                    raise LspTransportError("formatting requires a document URI")
                uri = document["uri"]
                if uri not in document_text:
                    raise LspTransportError(f"document is not open: {uri}")
                source = document_text[uri]
                formatted = format_source(source)
                if formatted == source:
                    edits: list[dict[str, object]] = []
                else:
                    lines = source.split("\n")
                    edits = [{
                        "range": {
                            "start": {"line": 0, "character": 0},
                            "end": {"line": len(lines) - 1, "character": len(lines[-1])},
                        },
                        "newText": formatted,
                    }]
                response = JsonRpcResponse(request.get("id"), result=edits)
            except (LspTransportError, TypeError, ValueError, KeyError) as error:
                response = JsonRpcResponse(
                    request.get("id"),
                    error={"code": -32602, "message": str(error)},
                )
            transport.write_response(outgoing, response)
            continue
        response = transport.dispatch(request)
        if response is not None:
            if method == "initialize" and response.error is None and isinstance(response.result, dict):
                capabilities = response.result.get("capabilities")
                if isinstance(capabilities, dict):
                    capabilities["documentFormattingProvider"] = True
            transport.write_response(outgoing, response)


def main() -> int:
    try:
        serve(sys.stdin.buffer, sys.stdout.buffer, sys.stderr.buffer)
    except (LspTransportError, OSError) as error:
        sys.stderr.write(f"s3 LSP transport stopped: {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
