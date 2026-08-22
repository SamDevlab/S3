"""Bounded deterministic in-process Language Server Protocol surface for M1.58."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from . import ast
from .diagnostics import S3Error, SourceLocation, diagnostic_from_exception
from .parser import parse
from .pipeline import compile_source


class LspError(ValueError):
    """Raised for unsupported or malformed M1.58 protocol operations."""


@dataclass(frozen=True, slots=True)
class _Symbol:
    name: str
    kind: int
    location: SourceLocation
    detail: str


@dataclass(slots=True)
class _Document:
    uri: str
    text: str
    version: int
    symbols: tuple[_Symbol, ...] = ()


_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")


def _type_text(type_name: ast.DeclaredType) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.TypeParameterType):
        return type_name.name
    if isinstance(type_name, ast.NominalType):
        suffix = ""
        if type_name.type_arguments:
            suffix = "<" + ", ".join(_type_text(item) for item in type_name.type_arguments) + ">"
        return type_name.name + suffix
    if isinstance(type_name, ast.ArrayType):
        return f"{_type_text(type_name.element_type)}[{type_name.length}]"
    if isinstance(type_name, ast.ReferenceType):
        return "&" + ("mut " if type_name.mutable else "") + _type_text(type_name.target)
    if isinstance(type_name, ast.SliceType):
        return "&" + ("mut " if type_name.mutable else "") + f"[{type_name.element_type.value}]"
    return "<unknown>"


def _position(location: SourceLocation, *, length: int = 1) -> dict[str, int]:
    return {"line": location.line - 1, "character": location.column - 1 + length}


def _range(location: SourceLocation, *, length: int = 1) -> dict[str, object]:
    return {
        "start": {"line": location.line - 1, "character": location.column - 1},
        "end": _position(location, length=length),
    }


def _location_from_position(text: str, position: Mapping[str, int]) -> int:
    line = position.get("line")
    character = position.get("character")
    if isinstance(line, bool) or not isinstance(line, int) or line < 0:
        raise LspError("position.line must be a non-negative integer")
    if isinstance(character, bool) or not isinstance(character, int) or character < 0:
        raise LspError("position.character must be a non-negative integer")
    lines = text.splitlines(keepends=True)
    if line >= len(lines):
        return len(text)
    return min(sum(len(item) for item in lines[:line]) + character, len(text))


def _word_at(text: str, position: Mapping[str, int]) -> str | None:
    offset = _location_from_position(text, position)
    for match in _WORD.finditer(text):
        if match.start() <= offset <= match.end():
            return match.group(0)
    return None


def _symbols(program: ast.Program) -> tuple[_Symbol, ...]:
    result: list[_Symbol] = []
    for function in program.functions:
        parameters = ", ".join(
            f"{item.name}: {_type_text(item.type_name)}" for item in function.parameters
        )
        type_parameters = ""
        if function.signature.type_parameters:
            type_parameters = "<" + ", ".join(
                item.name for item in function.signature.type_parameters
            ) + ">"
        result.append(
            _Symbol(
                function.name,
                12,
                function.signature.location,
                f"fn {function.name}{type_parameters}({parameters}) -> {_type_text(function.return_type)}",
            )
        )
    result.extend(
        _Symbol(
            record.name,
            23,
            record.location,
            f"record {record.name}",
        )
        for record in program.records
    )
    result.extend(
        _Symbol(enum.name, 10, enum.location, f"enum {enum.name}")
        for enum in program.enums
    )
    return tuple(sorted(result, key=lambda item: (item.name, item.kind)))


class LanguageServer:
    """In-process LSP V1 facade; transport and workspace management stay external."""

    def __init__(self) -> None:
        self._documents: dict[str, _Document] = {}

    def initialize(self) -> dict[str, object]:
        return {
            "capabilities": {
                "textDocumentSync": 1,
                "hoverProvider": True,
                "definitionProvider": True,
                "documentSymbolProvider": True,
                "completionProvider": {"triggerCharacters": ["."]},
            },
            "serverInfo": {"name": "s3-language-server", "version": "1"},
        }

    def did_open(self, uri: str, text: str, version: int = 1) -> dict[str, object]:
        self._set_document(uri, text, version)
        return self._publish(uri)

    def did_change(
        self,
        uri: str,
        changes: str | list[Mapping[str, object]],
        version: int,
    ) -> dict[str, object]:
        if isinstance(changes, str):
            text = changes
        elif isinstance(changes, list) and len(changes) == 1 and isinstance(changes[0], Mapping):
            text = changes[0].get("text")
            if not isinstance(text, str) or "range" in changes[0]:
                raise LspError("M1.58 accepts only one full-document change")
        else:
            raise LspError("M1.58 accepts only one full-document change")
        self._set_document(uri, text, version)
        return self._publish(uri)

    def did_close(self, uri: str) -> None:
        self._documents.pop(uri, None)

    def hover(self, uri: str, position: Mapping[str, int]) -> dict[str, object] | None:
        document = self._document(uri)
        word = _word_at(document.text, position)
        symbol = next((item for item in document.symbols if item.name == word), None)
        if symbol is None:
            return None
        return {
            "contents": {"kind": "markdown", "value": f"```s3\n{symbol.detail}\n```"},
            "range": _range(symbol.location, length=len(symbol.name)),
        }

    def definition(self, uri: str, position: Mapping[str, int]) -> list[dict[str, object]]:
        document = self._document(uri)
        word = _word_at(document.text, position)
        symbol = next((item for item in document.symbols if item.name == word), None)
        if symbol is None:
            return []
        return [{"uri": uri, "range": _range(symbol.location, length=len(symbol.name))}]

    def document_symbols(self, uri: str) -> list[dict[str, object]]:
        document = self._document(uri)
        return [
            {
                "name": symbol.name,
                "kind": symbol.kind,
                "range": _range(symbol.location, length=len(symbol.name)),
                "selectionRange": _range(symbol.location, length=len(symbol.name)),
                "detail": symbol.detail,
            }
            for symbol in document.symbols
        ]

    def completion(self, uri: str, position: Mapping[str, int]) -> list[dict[str, object]]:
        document = self._document(uri)
        offset = _location_from_position(document.text, position)
        prefix_match = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", document.text[:offset])
        prefix = prefix_match.group(0) if prefix_match else ""
        return [
            {"label": symbol.name, "kind": symbol.kind, "detail": symbol.detail}
            for symbol in document.symbols
            if symbol.name.startswith(prefix)
        ]

    def _set_document(self, uri: str, text: str, version: int) -> None:
        if not isinstance(uri, str) or not uri:
            raise LspError("document uri must be non-empty")
        if isinstance(version, bool) or not isinstance(version, int):
            raise LspError("document version must be an integer")
        current = self._documents.get(uri)
        if current is not None and version <= current.version:
            raise LspError("document version must increase monotonically")
        try:
            program = parse(text)
            symbols = _symbols(program)
        except S3Error:
            symbols = ()
        self._documents[uri] = _Document(uri, text, version, symbols)

    def _publish(self, uri: str) -> dict[str, object]:
        document = self._document(uri)
        diagnostics: list[dict[str, object]] = []
        try:
            compile_source(document.text)
        except S3Error as error:
            location = error.location or SourceLocation(0, 1, 1)
            diagnostic = diagnostic_from_exception(error, file=uri)
            diagnostics.append(
                {
                    "range": _range(location),
                    "severity": 1,
                    "code": diagnostic.code.value,
                    "source": "s3",
                    "message": diagnostic.message,
                }
            )
        return {"uri": uri, "version": document.version, "diagnostics": diagnostics}

    def _document(self, uri: str) -> _Document:
        try:
            return self._documents[uri]
        except KeyError as error:
            raise LspError(f"document is not open: {uri}") from error
