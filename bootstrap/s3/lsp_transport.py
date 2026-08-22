"""Bounded JSON-RPC stdio transport for the S3 language-server foundation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import BinaryIO, Mapping

from .lsp import LanguageServer, LspError


class LspTransportError(ValueError):
    """Raised for bounded framing or JSON-RPC protocol errors."""


@dataclass(frozen=True, slots=True)
class JsonRpcResponse:
    identifier: object
    result: object | None = None
    error: dict[str, object] | None = None

    @property
    def payload(self) -> dict[str, object]:
        result: dict[str, object] = {"jsonrpc": "2.0", "id": self.identifier}
        if self.error is not None:
            result["error"] = self.error
        else:
            result["result"] = self.result
        return result


class JsonRpcTransport:
    """One-message parser and dispatcher with fixed protocol bounds."""

    def __init__(self, *, max_header_bytes: int = 16_384, max_message_bytes: int = 1_048_576) -> None:
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (max_header_bytes, max_message_bytes)):
            raise ValueError("JSON-RPC bounds must be positive integers")
        self.max_header_bytes = max_header_bytes
        self.max_message_bytes = max_message_bytes
        self.server = LanguageServer()
        self.stopped = False

    def read_message(self, stream: BinaryIO) -> dict[str, object] | None:
        header = bytearray()
        while b"\r\n\r\n" not in header:
            chunk = stream.read(1)
            if not chunk:
                if header:
                    raise LspTransportError("truncated headers")
                return None
            header.extend(chunk)
            if len(header) > self.max_header_bytes:
                raise LspTransportError("JSON-RPC headers exceed bound")
        marker = b"\r\n\r\n"
        raw_header, _ = bytes(header).split(marker, 1)
        fields: dict[str, str] = {}
        for line in raw_header.split(b"\r\n"):
            if b":" not in line:
                raise LspTransportError("malformed JSON-RPC header")
            key, value = line.split(b":", 1)
            normalized_key = key.decode("ascii").strip().lower()
            if normalized_key in fields:
                raise LspTransportError("duplicate JSON-RPC header")
            fields[normalized_key] = value.decode("ascii").strip()
        try:
            length = int(fields["content-length"])
        except (KeyError, ValueError) as error:
            raise LspTransportError("Content-Length header is required") from error
        if length < 0 or length > self.max_message_bytes:
            raise LspTransportError("JSON-RPC message exceeds bound")
        body = stream.read(length)
        if len(body) != length:
            raise LspTransportError("truncated JSON-RPC message")
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise LspTransportError("invalid JSON-RPC message") from error
        if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
            raise LspTransportError("JSON-RPC message must be an object with jsonrpc 2.0")
        return value

    def dispatch(self, request: Mapping[str, object]) -> JsonRpcResponse | None:
        if self.stopped:
            return None
        method = request.get("method")
        identifier = request.get("id")
        params = request.get("params", {})
        if not isinstance(method, str) or not method:
            return JsonRpcResponse(identifier, error={"code": -32600, "message": "invalid request"})
        try:
            result = self._dispatch_method(method, params)
        except (LspError, LspTransportError, KeyError, TypeError, ValueError) as error:
            code = -32601 if str(error).startswith("method not found:") else -32602
            return JsonRpcResponse(identifier, error={"code": code, "message": str(error)})
        if "id" not in request:
            return None
        return JsonRpcResponse(identifier, result=result)

    def write_response(self, stream: BinaryIO, response: JsonRpcResponse) -> None:
        body = json.dumps(response.payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(body) > self.max_message_bytes:
            raise LspTransportError("JSON-RPC response exceeds bound")
        stream.write(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
        stream.flush()

    def serve(self, incoming: BinaryIO, outgoing: BinaryIO) -> None:
        while not self.stopped:
            request = self.read_message(incoming)
            if request is None:
                return
            response = self.dispatch(request)
            if response is not None:
                self.write_response(outgoing, response)

    def _dispatch_method(self, method: str, params: object) -> object:
        if not isinstance(params, Mapping):
            raise LspTransportError("JSON-RPC params must be an object")
        if method == "initialize":
            return self.server.initialize()
        if method == "initialized":
            return None
        if method == "$/cancelRequest":
            request_id = params.get("id")
            if isinstance(request_id, bool) or not isinstance(request_id, (int, str)):
                raise LspTransportError("cancelRequest id must be an integer or string")
            return None
        if method == "shutdown":
            return None
        if method == "exit":
            self.stopped = True
            return None
        if method == "textDocument/didOpen":
            document = _document(params)
            return self.server.did_open(document[0], document[1], document[2])
        if method == "textDocument/didChange":
            document = params.get("textDocument")
            changes = params.get("contentChanges")
            if not isinstance(document, Mapping) or not isinstance(changes, list):
                raise LspTransportError("didChange requires textDocument and contentChanges")
            return self.server.did_change(document.get("uri"), changes, document.get("version"))
        if method == "textDocument/didClose":
            uri = params.get("textDocument", {}).get("uri") if isinstance(params.get("textDocument"), Mapping) else None
            self.server.did_close(uri)
            return None
        if method == "textDocument/documentSymbol":
            return self.server.document_symbols(_uri(params))
        if method == "textDocument/hover":
            return self.server.hover(_uri(params), _position(params))
        if method == "textDocument/definition":
            return self.server.definition(_uri(params), _position(params))
        if method == "textDocument/references":
            return self.server.references(_uri(params), _position(params))
        if method == "textDocument/rename":
            new_name = params.get("newName")
            if not isinstance(new_name, str):
                raise LspTransportError("rename requires newName")
            return self.server.rename(_uri(params), _position(params), new_name)
        if method == "workspace/symbol":
            query = params.get("query", "")
            if not isinstance(query, str):
                raise LspTransportError("workspace/symbol query must be a string")
            return self.server.workspace_symbols(query)
        raise LspTransportError(f"method not found: {method}")


def _document(params: Mapping[str, object]) -> tuple[str, str, int]:
    document = params.get("textDocument")
    if not isinstance(document, Mapping):
        raise LspTransportError("textDocument is required")
    uri, text, version = document.get("uri"), document.get("text"), document.get("version", 1)
    if not isinstance(uri, str) or not isinstance(text, str) or isinstance(version, bool) or not isinstance(version, int):
        raise LspTransportError("document uri, text and version are invalid")
    return uri, text, version


def _uri(params: Mapping[str, object]) -> str:
    document = params.get("textDocument")
    if not isinstance(document, Mapping) or not isinstance(document.get("uri"), str):
        raise LspTransportError("textDocument uri is required")
    return document["uri"]


def _position(params: Mapping[str, object]) -> Mapping[str, int]:
    position = params.get("position")
    if not isinstance(position, Mapping):
        raise LspTransportError("position is required")
    return position  # type: ignore[return-value]
