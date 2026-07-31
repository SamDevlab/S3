"""Deterministic module graph for multi-source S3 compilation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from . import ast
from .diagnostics import DiagnosticCode, SemanticError, SourceLocation

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(value: str, *, label: str) -> None:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"invalid {label}: {value!r}")


@dataclass(frozen=True, order=True, slots=True)
class ModuleId:
    parts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.parts:
            raise ValueError("module id must contain at least one part")
        for part in self.parts:
            _validate_identifier(part, label="module id part")

    @classmethod
    def parse(cls, value: str) -> ModuleId:
        parts = tuple(value.split("."))
        return cls(parts)

    @classmethod
    def from_logical_path(cls, logical_path: str) -> ModuleId:
        normalized = normalize_logical_path(logical_path)
        path = PurePosixPath(normalized)
        parts = list(path.parts)
        if parts[-1].endswith(".s3"):
            parts[-1] = parts[-1][:-3]
        return cls(tuple(parts))

    def __str__(self) -> str:
        return ".".join(self.parts)


@dataclass(frozen=True, slots=True)
class SourceUnit:
    logical_path: str
    source: str
    declared_module: ModuleId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "logical_path",
            normalize_logical_path(self.logical_path),
        )

    @property
    def module_id(self) -> ModuleId:
        if self.declared_module is not None:
            return self.declared_module
        return ModuleId.from_logical_path(self.logical_path)


@dataclass(frozen=True, slots=True)
class ImportEdge:
    importing_module: ModuleId
    imported_module: ModuleId
    symbol: str
    alias: str | None = None
    location: SourceLocation | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.symbol, label="imported symbol")
        if self.alias is not None:
            _validate_identifier(self.alias, label="import alias")

    @property
    def local_name(self) -> str:
        return self.symbol if self.alias is None else self.alias


@dataclass(frozen=True, slots=True)
class ModuleGraph:
    units: tuple[SourceUnit, ...]
    imports: tuple[ImportEdge, ...]
    entry_module: ModuleId
    ordered_modules: tuple[ModuleId, ...]

    @classmethod
    def build(
        cls,
        units: tuple[SourceUnit, ...],
        imports: tuple[ImportEdge, ...] = (),
        *,
        entry_module: ModuleId | str = "main",
    ) -> ModuleGraph:
        entry = (
            ModuleId.parse(entry_module)
            if isinstance(entry_module, str)
            else entry_module
        )
        unit_by_module = _collect_units(units)
        if entry not in unit_by_module:
            raise _semantic_error(
                f"entry module '{entry}' was not provided",
                DiagnosticCode.MODULE_ENTRY_INVALID,
            )
        _validate_imports(imports, unit_by_module)
        ordered = _topological_order(tuple(unit_by_module), imports)
        return cls(
            units=tuple(unit_by_module[module] for module in ordered),
            imports=tuple(sorted(imports, key=_import_sort_key)),
            entry_module=entry,
            ordered_modules=ordered,
        )


def normalize_logical_path(logical_path: str) -> str:
    if not logical_path:
        raise ValueError("logical path must be non-empty")
    path = logical_path.replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ValueError("logical path must be relative")
    parts: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError("logical path must not contain '..'")
        parts.append(part)
    if not parts:
        raise ValueError("logical path must contain a file name")
    return "/".join(parts)


def source_unit_from_program(
    logical_path: str,
    source: str,
    program: ast.Program,
) -> SourceUnit:
    declared = (
        ModuleId.parse(program.module.name)
        if program.module is not None
        else None
    )
    return SourceUnit(logical_path, source, declared)


def import_edges_from_program(
    module: ModuleId,
    program: ast.Program,
) -> tuple[ImportEdge, ...]:
    return tuple(
        ImportEdge(
            importing_module=module,
            imported_module=ModuleId.parse(declaration.module_name),
            symbol=declaration.symbol_name,
            alias=declaration.alias,
            location=declaration.location,
        )
        for declaration in program.imports
    )


def _collect_units(units: tuple[SourceUnit, ...]) -> dict[ModuleId, SourceUnit]:
    unit_by_module: dict[ModuleId, SourceUnit] = {}
    for unit in sorted(units, key=lambda item: item.logical_path):
        module = unit.module_id
        if module in unit_by_module:
            previous = unit_by_module[module]
            raise _semantic_error(
                (
                    f"duplicate module '{module}' in '{previous.logical_path}' "
                    f"and '{unit.logical_path}'"
                ),
                DiagnosticCode.MODULE_DUPLICATE,
            )
        unit_by_module[module] = unit
    return unit_by_module


def _validate_imports(
    imports: tuple[ImportEdge, ...],
    unit_by_module: dict[ModuleId, SourceUnit],
) -> None:
    seen_edges: set[tuple[ModuleId, ModuleId, str, str]] = set()
    local_names: dict[tuple[ModuleId, str], ImportEdge] = {}
    for edge in sorted(imports, key=_import_sort_key):
        if edge.importing_module not in unit_by_module:
            raise _semantic_error(
                f"importing module '{edge.importing_module}' was not provided",
                DiagnosticCode.MODULE_NOT_FOUND,
                edge.location,
            )
        if edge.imported_module not in unit_by_module:
            raise _semantic_error(
                f"module '{edge.imported_module}' was not found",
                DiagnosticCode.MODULE_NOT_FOUND,
                edge.location,
            )
        key = (
            edge.importing_module,
            edge.imported_module,
            edge.symbol,
            edge.local_name,
        )
        if key in seen_edges:
            raise _semantic_error(
                (
                    f"duplicate import of '{edge.symbol}' from "
                    f"'{edge.imported_module}' in '{edge.importing_module}'"
                ),
                DiagnosticCode.IMPORT_DUPLICATE,
                edge.location,
            )
        seen_edges.add(key)

        local_key = (edge.importing_module, edge.local_name)
        previous = local_names.get(local_key)
        if previous is not None:
            raise _semantic_error(
                (
                    f"import local name '{edge.local_name}' conflicts in "
                    f"module '{edge.importing_module}'"
                ),
                DiagnosticCode.IMPORT_CONFLICT,
                edge.location,
            )
        local_names[local_key] = edge


def _topological_order(
    modules: tuple[ModuleId, ...],
    imports: tuple[ImportEdge, ...],
) -> tuple[ModuleId, ...]:
    dependencies: dict[ModuleId, set[ModuleId]] = {
        module: set() for module in modules
    }
    dependents: dict[ModuleId, set[ModuleId]] = {
        module: set() for module in modules
    }
    for edge in imports:
        dependencies[edge.importing_module].add(edge.imported_module)
        dependents[edge.imported_module].add(edge.importing_module)

    ready = sorted(
        module for module, deps in dependencies.items() if not deps
    )
    ordered: list[ModuleId] = []
    while ready:
        module = ready.pop(0)
        ordered.append(module)
        for dependent in sorted(dependents[module]):
            dependencies[dependent].remove(module)
            if not dependencies[dependent]:
                ready.append(dependent)
                ready.sort()

    if len(ordered) != len(modules):
        cycle = _find_cycle(modules, imports)
        raise _semantic_error(
            "module import cycle: " + " -> ".join(str(module) for module in cycle),
            DiagnosticCode.MODULE_CYCLE,
        )
    return tuple(ordered)


def _find_cycle(
    modules: tuple[ModuleId, ...],
    imports: tuple[ImportEdge, ...],
) -> tuple[ModuleId, ...]:
    adjacency: dict[ModuleId, list[ModuleId]] = {
        module: [] for module in modules
    }
    for edge in sorted(imports, key=_import_sort_key):
        adjacency[edge.importing_module].append(edge.imported_module)

    visiting: set[ModuleId] = set()
    visited: set[ModuleId] = set()
    stack: list[ModuleId] = []

    def visit(module: ModuleId) -> tuple[ModuleId, ...] | None:
        if module in visiting:
            start = stack.index(module)
            return tuple(stack[start:] + [module])
        if module in visited:
            return None
        visiting.add(module)
        stack.append(module)
        for dependency in sorted(adjacency[module]):
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        stack.pop()
        visiting.remove(module)
        visited.add(module)
        return None

    for module in sorted(modules):
        cycle = visit(module)
        if cycle is not None:
            return cycle
    return tuple()


def _import_sort_key(edge: ImportEdge) -> tuple[str, str, str, str]:
    return (
        str(edge.importing_module),
        str(edge.imported_module),
        edge.symbol,
        edge.local_name,
    )


def _semantic_error(
    message: str,
    code: DiagnosticCode,
    location: SourceLocation | None = None,
) -> SemanticError:
    return SemanticError(
        message,
        location,
        diagnostic_code=code,
    )
