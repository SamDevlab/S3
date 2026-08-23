"""Bounded deterministic in-process Language Server Protocol surface for M1.58."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import unquote, urlparse

from . import ast
from .diagnostics import S3Error, SourceLocation, diagnostic_from_exception
from .lexer import TokenKind, tokenize
from .parser import parse
from .pipeline import compile_source
from .workspace_semantic import (
    SemanticSymbol,
    WorkspaceSemanticError,
    WorkspaceSemanticIndex,
)


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
    logical_path: str
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


def _identifier_locations(text: str, name: str) -> tuple[SourceLocation, ...]:
    """Use lexer identifiers so comments and string contents are not references."""

    return tuple(
        SourceLocation(token.position, token.line, token.column)
        for token in tokenize(text)
        if token.kind is TokenKind.IDENTIFIER and token.text == name
    )


def _logical_path(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path = unquote(parsed.path).lstrip("/")
        if parsed.netloc:
            path = f"{parsed.netloc}/{path}"
    else:
        path = unquote(uri)
    if len(path) >= 2 and path[1] == ":":
        path = path[2:].lstrip("/")
    path = path.replace("\\", "/")
    if not path:
        raise LspError("document uri must identify a logical path")
    return path


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
        self._semantic_index = WorkspaceSemanticIndex()
        self._workspace_errors: dict[str, str] = {}

    def initialize(self) -> dict[str, object]:
        return {
            "capabilities": {
                "textDocumentSync": 1,
                "hoverProvider": True,
                "definitionProvider": True,
                "documentSymbolProvider": True,
                "completionProvider": {"triggerCharacters": ["."]},
                "referencesProvider": True,
                "renameProvider": True,
                "workspaceSymbolProvider": True,
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
        document = self._documents.pop(uri, None)
        self._workspace_errors.pop(uri, None)
        if document is None:
            return
        try:
            self._semantic_index.graph.module_for_path(document.logical_path)
            self._semantic_index.close_document(document.logical_path)
        except WorkspaceSemanticError:
            # Rebuild from the remaining valid documents if the closed document
            # was rejected by the last candidate snapshot.
            self._semantic_index = WorkspaceSemanticIndex()
            for remaining in sorted(
                self._documents.values(), key=lambda item: item.logical_path
            ):
                try:
                    self._semantic_index.open_document(
                        remaining.logical_path,
                        remaining.text,
                    )
                except WorkspaceSemanticError:
                    break

    def hover(self, uri: str, position: Mapping[str, int]) -> dict[str, object] | None:
        document = self._document(uri)
        word = _word_at(document.text, position)
        resolved = self._resolve_symbol(uri, word)
        if resolved is None:
            return None
        declaration, symbol = resolved
        return {
            "contents": {"kind": "markdown", "value": f"```s3\n{symbol.detail}\n```"},
            "range": _range(symbol.location, length=len(symbol.name)),
        }

    def definition(self, uri: str, position: Mapping[str, int]) -> list[dict[str, object]]:
        document = self._document(uri)
        word = _word_at(document.text, position)
        resolved = self._resolve_symbol(uri, word)
        if resolved is None:
            return []
        declaration, symbol = resolved
        return [{"uri": declaration.uri, "range": _range(symbol.location, length=len(symbol.name))}]

    def workspace_symbols(self, query: str = "") -> list[dict[str, object]]:
        if not isinstance(query, str):
            raise LspError("workspace symbol query must be a string")
        result: list[dict[str, object]] = []
        for uri in sorted(self._documents):
            document = self._documents[uri]
            for symbol in document.symbols:
                if query.casefold() not in symbol.name.casefold():
                    continue
                result.append(
                    {
                        "name": symbol.name,
                        "kind": symbol.kind,
                        "uri": uri,
                        "range": _range(symbol.location, length=len(symbol.name)),
                        "containerName": uri,
                    }
                )
        return result

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

    def references(self, uri: str, position: Mapping[str, int]) -> list[dict[str, object]]:
        document = self._document(uri)
        word = _word_at(document.text, position)
        resolved = self._resolve_symbol(uri, word)
        if resolved is None:
            return []
        documents = self._reference_documents(word or "", uri)
        return [
            {"uri": item_uri, "range": _range(location, length=len(name))}
            for item_uri in sorted(documents)
            for name in documents[item_uri]
            for location in _identifier_locations(self._documents[item_uri].text, name)
        ]

    def rename(
        self,
        uri: str,
        position: Mapping[str, int],
        new_name: str,
    ) -> dict[str, object]:
        if _WORD.fullmatch(new_name) is None:
            raise LspError("rename target must be an identifier")
        document = self._document(uri)
        word = _word_at(document.text, position)
        if self._resolve_symbol(uri, word) is None:
            raise LspError("rename target is not a known semantic symbol")
        documents = self._reference_documents(word or "", uri)
        return {
            "changes": {
                item_uri: [
                    {
                        "range": _range(location, length=len(name)),
                        "newText": new_name,
                    }
                    for name in documents[item_uri]
                    for location in _identifier_locations(self._documents[item_uri].text, name)
                ]
                for item_uri in sorted(documents)
            }
        }

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
        logical_path = _logical_path(uri)
        try:
            self._semantic_index.open_document(logical_path, text)
            self._workspace_errors.pop(uri, None)
        except WorkspaceSemanticError as error:
            self._workspace_errors[uri] = str(error)
        self._documents[uri] = _Document(uri, logical_path, text, version, symbols)

    def _publish(self, uri: str) -> dict[str, object]:
        document = self._document(uri)
        diagnostics: list[dict[str, object]] = []
        workspace_error = self._workspace_errors.get(uri)
        if workspace_error is not None:
            diagnostics.append(
                {
                    "range": _range(SourceLocation(0, 1, 1)),
                    "severity": 1,
                    "code": "S3E_SEMANTIC_INVALID_PROGRAM",
                    "source": "s3",
                    "message": workspace_error,
                }
            )
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

    def _resolve_symbol(self, uri: str, name: str | None) -> tuple[_Document, _Symbol] | None:
        if not name:
            return None
        document = self._document(uri)
        semantic = self._semantic_symbol(uri, name)
        if semantic is not None:
            for candidate in self._documents.values():
                if candidate.logical_path != semantic.logical_path:
                    continue
                symbol = next(
                    (item for item in candidate.symbols if item.name == semantic.name),
                    None,
                )
                if symbol is not None:
                    return candidate, symbol
            return None
        try:
            if not self._semantic_index.graph.complete:
                return None
        except WorkspaceSemanticError:
            pass
        local = next((item for item in document.symbols if item.name == name), None)
        declarations = [
            (candidate, symbol)
            for candidate_uri in sorted(self._documents)
            for candidate in (self._documents[candidate_uri],)
            for symbol in candidate.symbols
            if symbol.name == name
        ]
        if len(declarations) == 1:
            return declarations[0]
        if local is not None:
            return document, local
        return None

    def _semantic_symbol(self, uri: str, name: str) -> SemanticSymbol | None:
        try:
            graph = self._semantic_index.graph
            module = graph.module_for_path(self._document(uri).logical_path)
            return graph.resolve(module, name)
        except WorkspaceSemanticError:
            return None

    def _reference_documents(self, name: str, uri: str) -> dict[str, tuple[str, ...]]:
        semantic = self._semantic_symbol(uri, name)
        if semantic is not None:
            try:
                graph = self._semantic_index.graph
            except WorkspaceSemanticError:
                graph = None
            if graph is not None:
                result: dict[str, tuple[str, ...]] = {}
                for candidate in self._documents.values():
                    names: set[str] = set()
                    if candidate.logical_path == semantic.logical_path:
                        names.add(semantic.name)
                    try:
                        module = graph.module_for_path(candidate.logical_path)
                    except WorkspaceSemanticError:
                        continue
                    unit = graph.module(module)
                    for symbol in unit.symbols:
                        try:
                            resolved = graph.resolve(module, symbol.name)
                        except WorkspaceSemanticError:
                            continue
                        if resolved.identity == semantic.identity:
                            names.add(symbol.name)
                    for edge in unit.imports:
                        try:
                            resolved = graph.resolve(module, edge.local_name)
                        except WorkspaceSemanticError:
                            continue
                        if resolved.identity == semantic.identity:
                            names.add(edge.local_name)
                    if names:
                        result[candidate.uri] = tuple(sorted(names))
                return result
        documents = self._documents_for_symbol(name, uri)
        return {item_uri: (name,) for item_uri in documents}

    def _documents_for_symbol(self, name: str, uri: str) -> dict[str, _Document]:
        declarations = [
            (candidate_uri, document)
            for candidate_uri in sorted(self._documents)
            for document in (self._documents[candidate_uri],)
            for symbol in document.symbols
            if symbol.name == name
        ]
        if len(declarations) == 1:
            return dict((candidate_uri, document) for candidate_uri, document in self._documents.items())
        return {uri: self._document(uri)}
