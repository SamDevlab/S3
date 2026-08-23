"""Deterministic workspace-level semantic identities for M2.41.

The existing :mod:`module_graph` owns module and import topology.  This module
adds the semantic namespace that sits above that topology without making
filesystem discovery or document-open order observable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from . import ast
from .module_graph import (
    ImportEdge,
    ModuleGraph,
    ModuleId,
    SourceUnit,
    import_edges_from_program,
    normalize_logical_path,
    source_unit_from_program,
)
from .parser import parse


class WorkspaceSemanticError(ValueError):
    """Raised when workspace semantic identities cannot be resolved safely."""


class SymbolKind(StrEnum):
    FUNCTION = "function"
    FOREIGN_FUNCTION = "foreign_function"
    TYPE = "type"


@dataclass(frozen=True, order=True, slots=True)
class SymbolIdentity:
    """A stable semantic identity independent of source path or open order."""

    module: ModuleId
    namespace: str
    name: str

    def __post_init__(self) -> None:
        if self.namespace not in {"value", "type"}:
            raise WorkspaceSemanticError("symbol namespace must be value or type")
        if not self.name:
            raise WorkspaceSemanticError("symbol name must be non-empty")

    @property
    def canonical(self) -> str:
        return f"{self.module}::{self.namespace}::{self.name}"


@dataclass(frozen=True, order=True, slots=True)
class TypeIdentity:
    """Nominal type identity; aliases never create a second type identity."""

    module: ModuleId
    name: str

    @property
    def canonical(self) -> str:
        return SymbolIdentity(self.module, "type", self.name).canonical


@dataclass(frozen=True, slots=True)
class SemanticSymbol:
    identity: SymbolIdentity
    kind: SymbolKind
    declaration_kind: str
    logical_path: str
    exported: bool
    type_identity: TypeIdentity | None = None

    @property
    def name(self) -> str:
        return self.identity.name

    @property
    def module(self) -> ModuleId:
        return self.identity.module

    @property
    def reference_identity(self) -> str:
        """Canonical identity used by references and imported aliases."""

        return self.identity.canonical


@dataclass(frozen=True, slots=True)
class WorkspaceDocument:
    logical_path: str
    source_digest: str
    module: ModuleId


@dataclass(frozen=True, slots=True)
class ModuleSemanticUnit:
    module: ModuleId
    logical_path: str
    source_digest: str
    symbols: tuple[SemanticSymbol, ...]
    imports: tuple[ImportEdge, ...]

    @property
    def dependencies(self) -> tuple[ModuleId, ...]:
        return tuple(sorted({edge.imported_module for edge in self.imports}))


@dataclass(frozen=True, slots=True)
class InvalidationResult:
    changed_modules: tuple[ModuleId, ...]
    invalidated_modules: tuple[ModuleId, ...]
    graph: "WorkspaceSemanticGraph"


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _module_sort_key(module: ModuleId) -> str:
    return str(module)


def _symbol_from_declaration(
    module: ModuleId,
    logical_path: str,
    declaration: object,
) -> SemanticSymbol:
    if isinstance(declaration, ast.FunctionDeclaration):
        return SemanticSymbol(
            SymbolIdentity(module, "value", declaration.name),
            SymbolKind.FUNCTION,
            "function",
            logical_path,
            declaration.exported,
        )
    if isinstance(declaration, ast.ForeignFunctionDeclaration):
        return SemanticSymbol(
            SymbolIdentity(module, "value", declaration.name),
            SymbolKind.FOREIGN_FUNCTION,
            "foreign_function",
            logical_path,
            False,
        )
    if isinstance(declaration, ast.RecordDeclaration):
        return SemanticSymbol(
            SymbolIdentity(module, "type", declaration.name),
            SymbolKind.TYPE,
            "record",
            logical_path,
            declaration.exported,
            TypeIdentity(module, declaration.name),
        )
    if isinstance(declaration, ast.EnumDeclaration):
        return SemanticSymbol(
            SymbolIdentity(module, "type", declaration.name),
            SymbolKind.TYPE,
            "enum",
            logical_path,
            declaration.exported,
            TypeIdentity(module, declaration.name),
        )
    raise WorkspaceSemanticError(
        f"unsupported declaration in module '{module}'"
    )


def _program_symbols(
    module: ModuleId,
    logical_path: str,
    program: ast.Program,
) -> tuple[SemanticSymbol, ...]:
    declarations = (
        *program.functions,
        *program.foreign_functions,
        *program.records,
        *program.enums,
    )
    symbols = tuple(
        sorted(
            (_symbol_from_declaration(module, logical_path, item) for item in declarations),
            key=lambda item: (item.identity.namespace, item.name, item.declaration_kind),
        )
    )
    seen: dict[str, SemanticSymbol] = {}
    for symbol in symbols:
        key = symbol.name
        previous = seen.get(key)
        if previous is not None:
            if previous.declaration_kind == symbol.declaration_kind:
                raise WorkspaceSemanticError(
                    f"duplicate {symbol.declaration_kind} '{symbol.name}' in module '{module}'"
                )
            raise WorkspaceSemanticError(
                f"symbol '{symbol.name}' in module '{module}' is ambiguous between "
                f"{previous.declaration_kind} and {symbol.declaration_kind}"
            )
        seen[key] = symbol
    return symbols


def _dependent_closure(
    modules: set[ModuleId],
    imports: tuple[ImportEdge, ...],
    roots: set[ModuleId],
) -> tuple[ModuleId, ...]:
    dependents: dict[ModuleId, set[ModuleId]] = {module: set() for module in modules}
    for edge in imports:
        dependents.setdefault(edge.imported_module, set()).add(edge.importing_module)
    pending = sorted(roots, key=_module_sort_key)
    result: set[ModuleId] = set()
    while pending:
        module = pending.pop(0)
        if module in result:
            continue
        result.add(module)
        pending.extend(
            sorted(dependents.get(module, ()), key=_module_sort_key)
        )
    return tuple(sorted(result, key=_module_sort_key))


@dataclass(frozen=True, slots=True)
class WorkspaceSemanticGraph:
    """A complete, deterministic semantic snapshot of workspace documents."""

    documents: tuple[WorkspaceDocument, ...]
    modules: tuple[ModuleSemanticUnit, ...]
    imports: tuple[ImportEdge, ...]
    ordered_modules: tuple[ModuleId, ...]
    unresolved_imports: tuple[ImportEdge, ...] = ()

    @classmethod
    def from_sources(
        cls,
        sources: Mapping[str, str],
        *,
        entry_module: str | ModuleId | None = None,
        allow_unresolved_imports: bool = False,
    ) -> "WorkspaceSemanticGraph":
        if not sources:
            raise WorkspaceSemanticError("workspace requires at least one source")
        normalized_sources: dict[str, str] = {}
        for raw_path, source in sources.items():
            try:
                path = normalize_logical_path(raw_path)
            except (TypeError, ValueError) as error:
                raise WorkspaceSemanticError(str(error)) from error
            if not isinstance(source, str):
                raise WorkspaceSemanticError(f"source for '{path}' must be text")
            if path in normalized_sources:
                raise WorkspaceSemanticError(f"duplicate workspace source '{path}'")
            normalized_sources[path] = source

        source_units: list[SourceUnit] = []
        parsed: dict[str, ast.Program] = {}
        for logical_path in sorted(normalized_sources):
            source = normalized_sources[logical_path]
            try:
                program = parse(source)
            except Exception as error:
                raise WorkspaceSemanticError(
                    f"cannot parse workspace source '{logical_path}': {error}"
                ) from error
            parsed[logical_path] = program
            source_units.append(source_unit_from_program(logical_path, source, program))

        module_names = {unit.module_id for unit in source_units}
        all_imports: list[ImportEdge] = []
        units: list[ModuleSemanticUnit] = []
        for unit in source_units:
            program = parsed[unit.logical_path]
            imports = import_edges_from_program(unit.module_id, program)
            symbols = _program_symbols(unit.module_id, unit.logical_path, program)
            units.append(
                ModuleSemanticUnit(
                    unit.module_id,
                    unit.logical_path,
                    _source_digest(unit.source),
                    symbols,
                    tuple(sorted(imports, key=lambda edge: (str(edge.imported_module), edge.symbol, edge.local_name))),
                )
            )
            all_imports.extend(imports)

        imports = tuple(sorted(all_imports, key=lambda edge: (
            str(edge.importing_module), str(edge.imported_module), edge.symbol, edge.local_name
        )))
        unresolved = tuple(edge for edge in imports if edge.imported_module not in module_names)
        if unresolved and not allow_unresolved_imports:
            edge = unresolved[0]
            raise WorkspaceSemanticError(
                f"module '{edge.imported_module}' imported by '{edge.importing_module}' was not opened"
            )

        filtered_imports = tuple(edge for edge in imports if edge not in unresolved)
        if entry_module is None:
            entry = ModuleId.parse("main") if ModuleId.parse("main") in module_names else min(module_names, key=_module_sort_key)
        elif isinstance(entry_module, str):
            entry = ModuleId.parse(entry_module)
        else:
            entry = entry_module
        topology_entry = entry
        if allow_unresolved_imports and topology_entry not in module_names:
            topology_entry = min(module_names, key=_module_sort_key)
        try:
            topology = ModuleGraph.build(
                tuple(source_units),
                filtered_imports,
                entry_module=topology_entry,
            )
        except Exception as error:
            raise WorkspaceSemanticError(str(error)) from error

        by_module = {unit.module: unit for unit in units}
        graph = cls(
            tuple(
                WorkspaceDocument(item.logical_path, item.source_digest, item.module)
                for item in sorted(units, key=lambda item: item.logical_path)
            ),
            tuple(sorted(units, key=lambda item: _module_sort_key(item.module))),
            imports,
            topology.ordered_modules,
            unresolved,
        )
        graph._validate_import_symbols(by_module)
        return graph

    def _validate_import_symbols(
        self,
        by_module: Mapping[ModuleId, ModuleSemanticUnit],
    ) -> None:
        local_names: set[tuple[ModuleId, str, str]] = set()
        for unit in self.modules:
            for symbol in unit.symbols:
                local_names.add((unit.module, symbol.identity.namespace, symbol.name))
        imported_names: set[tuple[ModuleId, str]] = set()
        for edge in self.imports:
            if edge in self.unresolved_imports:
                continue
            provider = by_module[edge.imported_module]
            matches = tuple(symbol for symbol in provider.symbols if symbol.name == edge.symbol)
            if not matches:
                raise WorkspaceSemanticError(
                    f"module '{edge.imported_module}' does not define imported symbol '{edge.symbol}'"
                )
            if len(matches) > 1:
                raise WorkspaceSemanticError(
                    f"imported symbol '{edge.symbol}' in module '{edge.imported_module}' is ambiguous"
                )
            symbol = matches[0]
            if not symbol.exported:
                raise WorkspaceSemanticError(
                    f"symbol '{edge.symbol}' in module '{edge.imported_module}' is private"
                )
            local = (edge.importing_module, edge.local_name)
            if any(module == edge.importing_module and name == edge.local_name for module, _namespace, name in local_names):
                raise WorkspaceSemanticError(
                    f"import local name '{edge.local_name}' conflicts in module '{edge.importing_module}'"
                )
            if local in imported_names:
                raise WorkspaceSemanticError(
                    f"duplicate import local name '{edge.local_name}' in module '{edge.importing_module}'"
                )
            imported_names.add(local)

    @property
    def module_ids(self) -> tuple[ModuleId, ...]:
        return tuple(sorted((unit.module for unit in self.modules), key=_module_sort_key))

    @property
    def resolution_payload(self) -> dict[str, object]:
        return {
            "format": "s3.workspace-semantic.v1",
            "documents": [
                {"path": item.logical_path, "digest": item.source_digest, "module": str(item.module)}
                for item in self.documents
            ],
            "modules": [
                {
                    "module": str(unit.module),
                    "path": unit.logical_path,
                    "digest": unit.source_digest,
                    "symbols": [
                        {
                            "identity": symbol.identity.canonical,
                            "kind": symbol.kind.value,
                            "declaration_kind": symbol.declaration_kind,
                            "exported": symbol.exported,
                        }
                        for symbol in unit.symbols
                    ],
                }
                for unit in self.modules
            ],
            "imports": [
                {
                    "from": str(edge.importing_module),
                    "module": str(edge.imported_module),
                    "symbol": edge.symbol,
                    "alias": edge.alias,
                }
                for edge in self.imports
            ],
            "ordered_modules": [str(module) for module in self.ordered_modules],
            "unresolved_imports": [
                {
                    "from": str(edge.importing_module),
                    "module": str(edge.imported_module),
                    "symbol": edge.symbol,
                    "alias": edge.alias,
                }
                for edge in self.unresolved_imports
            ],
        }

    @property
    def resolution_digest(self) -> str:
        return _digest(self.resolution_payload)

    @property
    def complete(self) -> bool:
        return not self.unresolved_imports

    def module(self, module: ModuleId | str) -> ModuleSemanticUnit:
        identity = ModuleId.parse(module) if isinstance(module, str) else module
        for unit in self.modules:
            if unit.module == identity:
                return unit
        raise WorkspaceSemanticError(f"unknown workspace module '{identity}'")

    def symbol(
        self,
        module: ModuleId | str,
        name: str,
        *,
        namespace: str | None = None,
    ) -> SemanticSymbol:
        unit = self.module(module)
        matches = tuple(
            item for item in unit.symbols
            if item.name == name and (namespace is None or item.identity.namespace == namespace)
        )
        if len(matches) != 1:
            raise WorkspaceSemanticError(
                f"symbol '{name}' is not uniquely defined in module '{unit.module}'"
            )
        return matches[0]

    def resolve(self, module: ModuleId | str, name: str) -> SemanticSymbol:
        module_id = ModuleId.parse(module) if isinstance(module, str) else module
        unit = self.module(module_id)
        local = tuple(item for item in unit.symbols if item.name == name)
        if local:
            if len(local) != 1:
                raise WorkspaceSemanticError(f"symbol '{name}' is ambiguous in module '{module_id}'")
            return local[0]
        imports = tuple(edge for edge in self.imports if edge.importing_module == module_id and edge.local_name == name)
        if len(imports) != 1:
            raise WorkspaceSemanticError(f"symbol '{name}' is not visible in module '{module_id}'")
        edge = imports[0]
        return self.symbol(edge.imported_module, edge.symbol)

    def type_identity(self, module: ModuleId | str, name: str) -> TypeIdentity:
        symbol = self.resolve(module, name)
        if symbol.type_identity is None:
            raise WorkspaceSemanticError(f"symbol '{name}' is not a nominal type")
        return symbol.type_identity

    def invalidated_by(self, changed: tuple[ModuleId, ...]) -> tuple[ModuleId, ...]:
        return _dependent_closure(set(self.module_ids), self.imports, set(changed))


class WorkspaceSemanticIndex:
    """Open-order-independent document index with explicit invalidation results."""

    def __init__(self, *, entry_module: str | ModuleId | None = None) -> None:
        self._entry_module = entry_module
        self._sources: dict[str, str] = {}
        self._graph: WorkspaceSemanticGraph | None = None

    @property
    def graph(self) -> WorkspaceSemanticGraph:
        if self._graph is None:
            raise WorkspaceSemanticError("workspace has no opened documents")
        return self._graph

    @property
    def complete(self) -> bool:
        return self._graph is not None and self._graph.complete

    def open_document(self, logical_path: str, source: str) -> InvalidationResult:
        try:
            path = normalize_logical_path(logical_path)
        except (TypeError, ValueError) as error:
            raise WorkspaceSemanticError(str(error)) from error
        old_graph = self._graph
        old_sources = dict(self._sources)
        old_module = None if old_graph is None else next(
            (item.module for item in old_graph.documents if item.logical_path == path), None
        )
        self._sources[path] = source
        try:
            candidate = WorkspaceSemanticGraph.from_sources(
                self._sources,
                entry_module=self._entry_module,
                allow_unresolved_imports=True,
            )
        except Exception:
            self._sources = old_sources
            raise
        new_module = next(
            item.module for item in candidate.documents if item.logical_path == path
        )
        changed: set[ModuleId] = {new_module}
        if old_module is not None:
            changed.add(old_module)
        previous_source = old_sources.get(path)
        if previous_source == source and old_module == new_module:
            changed.clear()
        combined_imports = candidate.imports if old_graph is None else tuple(
            sorted(set(candidate.imports + old_graph.imports), key=lambda edge: (
                str(edge.importing_module), str(edge.imported_module), edge.symbol, edge.local_name
            ))
        )
        modules = set(candidate.module_ids)
        if old_graph is not None:
            modules.update(old_graph.module_ids)
        invalidated = _dependent_closure(modules, combined_imports, changed)
        self._graph = candidate
        return InvalidationResult(
            tuple(sorted(changed, key=_module_sort_key)),
            invalidated,
            candidate,
        )

    def close_document(self, logical_path: str) -> InvalidationResult:
        try:
            path = normalize_logical_path(logical_path)
        except (TypeError, ValueError) as error:
            raise WorkspaceSemanticError(str(error)) from error
        if path not in self._sources:
            raise WorkspaceSemanticError(f"document '{path}' is not open")
        old_graph = self.graph
        old_module = next(item.module for item in old_graph.documents if item.logical_path == path)
        old_sources = dict(self._sources)
        del self._sources[path]
        if not self._sources:
            self._graph = None
            raise WorkspaceSemanticError("workspace cannot close its last document")
        try:
            candidate = WorkspaceSemanticGraph.from_sources(
                self._sources,
                entry_module=self._entry_module,
                allow_unresolved_imports=True,
            )
        except Exception:
            self._sources = old_sources
            raise
        modules = set(candidate.module_ids) | set(old_graph.module_ids)
        imports = tuple(sorted(set(candidate.imports + old_graph.imports), key=lambda edge: (
            str(edge.importing_module), str(edge.imported_module), edge.symbol, edge.local_name
        )))
        invalidated = _dependent_closure(modules, imports, {old_module})
        self._graph = candidate
        return InvalidationResult((old_module,), invalidated, candidate)
