"""Bridge the independent source frontend into whole-program registration.

This module intentionally stops after program registration.  It converts the
generic SyntaxArena produced by the source frontend into deterministic
ModuleSpec/FunctionSpec/NominalTypeSpec values without invoking semantic
analysis, lowering, or emission.
"""

from __future__ import annotations

from dataclasses import dataclass

from .generic_syntax import (
    DeclarationPayload,
    FunctionPayload,
    NodeKind,
    SymbolPayload,
    SyntaxArena,
    SyntaxNode,
)
from .source_frontend import (
    SourceBundleFrontendResult,
    SourceUnitFrontendResult,
)
from .module_graph import ModuleId as SourceModuleId
from .whole_program import (
    ExportSpec,
    FieldSpec,
    FunctionSpec,
    ImportSpec,
    ModuleSpec,
    NominalTypeSpec,
    ParameterSpec,
    ProgramRegistry,
    TypeKind,
    VariantSpec,
)


class FrontendRegistrationError(ValueError):
    """Generic frontend syntax cannot be projected into program registration."""


@dataclass(frozen=True, slots=True)
class FrontendNodeRange:
    file_id: int
    first: int
    count: int


@dataclass(frozen=True, slots=True)
class FrontendSyntaxIndex:
    """Whole-program direct NodeIds over per-file SyntaxArena local IDs."""

    ranges: tuple[FrontendNodeRange, ...]

    @classmethod
    def from_frontend(
        cls,
        frontend: SourceBundleFrontendResult,
    ) -> "FrontendSyntaxIndex":
        ranges: list[FrontendNodeRange] = []
        first = 0
        for unit in frontend.units:
            count = len(unit.syntax_arena.nodes)
            ranges.append(FrontendNodeRange(unit.file_id, first, count))
            first += count
        return cls(tuple(ranges))

    @property
    def node_count(self) -> int:
        return sum(item.count for item in self.ranges)

    def global_id(self, file_id: int, local_node_id: int) -> int:
        for item in self.ranges:
            if item.file_id == file_id:
                if local_node_id < 0 or local_node_id >= item.count:
                    raise FrontendRegistrationError(
                        f"local node ID {local_node_id} is outside file {file_id}"
                    )
                return item.first + local_node_id
        raise FrontendRegistrationError(f"unknown frontend file ID {file_id}")

    def local_ref(self, global_node_id: int) -> tuple[int, int]:
        if global_node_id < 0:
            raise FrontendRegistrationError("global node ID must be non-negative")
        for item in self.ranges:
            if item.first <= global_node_id < item.first + item.count:
                return item.file_id, global_node_id - item.first
        raise FrontendRegistrationError(
            f"unknown whole-program node ID {global_node_id}"
        )


@dataclass(frozen=True, slots=True)
class FrontendRegistrationPlan:
    modules: tuple[ModuleSpec, ...]
    symbol_names: tuple[str, ...]
    synthetic_symbol_first: int
    syntax_index: FrontendSyntaxIndex

    def register(self, registry: ProgramRegistry) -> tuple[object, ...]:
        return registry.register(self.modules)


_TYPE_NODE_KINDS = {
    NodeKind.TYPE_NAME,
    NodeKind.ARRAY_TYPE,
    NodeKind.VECTOR_TYPE,
    NodeKind.NOMINAL_TYPE,
    NodeKind.REFERENCE_TYPE,
    NodeKind.SLICE_TYPE,
    NodeKind.TYPE_PARAMETER_TYPE,
}


def _payload(arena: SyntaxArena, node: SyntaxNode) -> object | None:
    return arena.payload(node)


def _declaration_payload(
    arena: SyntaxArena,
    node: SyntaxNode,
) -> DeclarationPayload:
    payload = _payload(arena, node)
    if not isinstance(payload, DeclarationPayload):
        raise FrontendRegistrationError(
            f"node {node.id} ({node.kind.value}) lacks declaration payload"
        )
    return payload


def _function_payload(
    arena: SyntaxArena,
    node: SyntaxNode,
) -> FunctionPayload:
    payload = _payload(arena, node)
    if not isinstance(payload, FunctionPayload):
        raise FrontendRegistrationError(
            f"node {node.id} ({node.kind.value}) lacks function payload"
        )
    return payload


def _symbol_payload(
    arena: SyntaxArena,
    node: SyntaxNode,
) -> SymbolPayload:
    payload = _payload(arena, node)
    if not isinstance(payload, SymbolPayload):
        raise FrontendRegistrationError(
            f"node {node.id} ({node.kind.value}) lacks symbol payload"
        )
    return payload


def _span(node: SyntaxNode) -> tuple[int, int, int]:
    return (node.span.file_id, node.span.start, node.span.end)


def _type_child(
    arena: SyntaxArena,
    node_id: int,
    *,
    file_id: int,
    syntax_index: FrontendSyntaxIndex,
) -> int:
    children = arena.child_ids(node_id)
    if len(children) != 1:
        raise FrontendRegistrationError(
            f"declaration node {node_id} must own exactly one type child"
        )
    child = arena.node(children[0])
    if child.kind not in _TYPE_NODE_KINDS:
        raise FrontendRegistrationError(
            f"declaration node {node_id} child is not a source type"
        )
    return syntax_index.global_id(file_id, child.id)


def _function_spec(
    arena: SyntaxArena,
    node: SyntaxNode,
    *,
    file_id: int,
    syntax_index: FrontendSyntaxIndex,
    ordinal: int,
) -> FunctionSpec:
    payload = _function_payload(arena, node)
    children = arena.child_ids(node.id)
    parameters: list[ParameterSpec] = []
    type_parameters = 0
    result_type_syntax_id = -1

    for child_id in children:
        child = arena.node(child_id)
        if child.kind is NodeKind.TYPE_PARAMETER:
            type_parameters += 1
            continue
        if child.kind is NodeKind.PARAMETER:
            declaration = _declaration_payload(arena, child)
            parameters.append(
                ParameterSpec(
                    declaration.symbol_id,
                    _type_child(
                        arena,
                        child.id,
                        file_id=file_id,
                        syntax_index=syntax_index,
                    ),
                    len(parameters),
                )
            )
            continue
        if child.kind in _TYPE_NODE_KINDS:
            result_type_syntax_id = syntax_index.global_id(file_id, child.id)

    if result_type_syntax_id < 0:
        raise FrontendRegistrationError(
            f"function node {node.id} has no declared result type syntax"
        )

    return FunctionSpec(
        payload.symbol_id,
        syntax_index.global_id(file_id, node.id),
        tuple(parameters),
        result_type_syntax_id,
        ordinal,
        bool(payload.flags & 1),
        node.kind is NodeKind.FOREIGN_FUNCTION,
        type_parameters,
    )


def _record_spec(
    arena: SyntaxArena,
    node: SyntaxNode,
    *,
    file_id: int,
    syntax_index: FrontendSyntaxIndex,
    ordinal: int,
) -> NominalTypeSpec:
    declaration = _declaration_payload(arena, node)
    fields: list[FieldSpec] = []
    generic_arity = 0

    for child_id in arena.child_ids(node.id):
        child = arena.node(child_id)
        if child.kind is NodeKind.TYPE_PARAMETER:
            generic_arity += 1
        elif child.kind is NodeKind.RECORD_FIELD:
            field = _declaration_payload(arena, child)
            # TypeId does not exist yet at registration time. -1 is the
            # explicit unresolved sentinel; type_syntax_id retains the source
            # identity for the later TYPE phase.
            type_syntax_id = _type_child(
                        arena,
                        child.id,
                        file_id=file_id,
                        syntax_index=syntax_index,
                    )
            fields.append(
                FieldSpec(
                    field.symbol_id,
                    -1,
                    len(fields),
                    False,
                    _span(child),
                    type_syntax_id,
                )
            )

    return NominalTypeSpec(
        declaration.symbol_id,
        syntax_index.global_id(file_id, node.id),
        TypeKind.RECORD,
        tuple(fields),
        (),
        generic_arity,
        ordinal,
    )


def _enum_spec(
    arena: SyntaxArena,
    node: SyntaxNode,
    *,
    file_id: int,
    syntax_index: FrontendSyntaxIndex,
    ordinal: int,
) -> NominalTypeSpec:
    declaration = _declaration_payload(arena, node)
    variants: list[VariantSpec] = []
    generic_arity = 0

    for child_id in arena.child_ids(node.id):
        child = arena.node(child_id)
        if child.kind is NodeKind.TYPE_PARAMETER:
            generic_arity += 1
            continue
        if child.kind is not NodeKind.ENUM_VARIANT:
            continue
        variant = _declaration_payload(arena, child)
        payload_fields = tuple(
            arena.node(payload_id)
            for payload_id in arena.child_ids(child.id)
        )
        payload_type_syntax_ids: list[int] = []
        for payload_field in payload_fields:
            if payload_field.kind is not NodeKind.RECORD_FIELD:
                raise FrontendRegistrationError(
                    f"enum variant node {child.id} has non-field payload syntax"
                )
            payload_type_syntax_ids.append(
                _type_child(arena, payload_field.id)
            )
        variants.append(
            VariantSpec(
                variant.symbol_id,
                len(variants),
                len(variants),
                tuple(-1 for _ in payload_fields),
                tuple(payload_type_syntax_ids),
            )
        )

    return NominalTypeSpec(
        declaration.symbol_id,
        syntax_index.global_id(file_id, node.id),
        TypeKind.ENUM,
        (),
        tuple(variants),
        generic_arity,
        ordinal,
    )


def _import_spec(
    arena: SyntaxArena,
    node: SyntaxNode,
    *,
    ordinal: int,
) -> ImportSpec:
    children = arena.child_ids(node.id)
    if len(children) not in (2, 3):
        raise FrontendRegistrationError(
            f"import node {node.id} has invalid child shape"
        )
    target = _symbol_payload(arena, arena.node(children[0]))
    imported = _symbol_payload(arena, arena.node(children[1]))
    alias = -1
    if len(children) == 3:
        alias = _symbol_payload(arena, arena.node(children[2])).symbol_id
    return ImportSpec(
        target.symbol_id,
        imported.symbol_id,
        alias,
        ordinal,
        _span(node),
    )


def _module_symbol_id(
    unit: SourceUnitFrontendResult,
    symbols: list[str],
    symbol_to_id: dict[str, int],
) -> int:
    arena = unit.syntax_arena
    root = arena.node(unit.root_id)
    for child_id in arena.child_ids(root.id):
        child = arena.node(child_id)
        if child.kind is NodeKind.MODULE_DECLARATION:
            return _declaration_payload(arena, child).symbol_id

    synthetic_name = str(SourceModuleId.from_logical_path(unit.path))
    existing = symbol_to_id.get(synthetic_name)
    if existing is not None:
        return existing
    symbol_id = len(symbols)
    symbols.append(synthetic_name)
    symbol_to_id[synthetic_name] = symbol_id
    return symbol_id


def _module_spec(
    unit: SourceUnitFrontendResult,
    *,
    module_symbol_id: int,
    syntax_index: FrontendSyntaxIndex,
) -> ModuleSpec:
    arena = unit.syntax_arena
    arena.validate()
    root = arena.node(unit.root_id)
    if root.kind is not NodeKind.PROGRAM:
        raise FrontendRegistrationError(
            f"source unit {unit.path!r} root is not PROGRAM"
        )

    functions: list[FunctionSpec] = []
    nominal_types: list[NominalTypeSpec] = []
    imports: list[ImportSpec] = []
    exports: list[ExportSpec] = []

    for child_id in arena.child_ids(root.id):
        child = arena.node(child_id)
        if child.kind in (NodeKind.FUNCTION, NodeKind.FOREIGN_FUNCTION):
            function = _function_spec(
                arena,
                child,
                file_id=unit.file_id,
                syntax_index=syntax_index,
                ordinal=len(functions),
            )
            functions.append(function)
            if function.exported:
                exports.append(
                    ExportSpec(
                        function.name_symbol_id,
                        "function",
                        len(exports),
                    )
                )
        elif child.kind is NodeKind.RECORD_DECLARATION:
            nominal = _record_spec(
                arena,
                child,
                file_id=unit.file_id,
                syntax_index=syntax_index,
                ordinal=len(nominal_types),
            )
            nominal_types.append(nominal)
            if _declaration_payload(arena, child).flags & 1:
                exports.append(
                    ExportSpec(
                        nominal.name_symbol_id,
                        "record",
                        len(exports),
                    )
                )
        elif child.kind is NodeKind.ENUM_DECLARATION:
            nominal = _enum_spec(
                arena,
                child,
                file_id=unit.file_id,
                syntax_index=syntax_index,
                ordinal=len(nominal_types),
            )
            nominal_types.append(nominal)
            if _declaration_payload(arena, child).flags & 1:
                exports.append(
                    ExportSpec(
                        nominal.name_symbol_id,
                        "enum",
                        len(exports),
                    )
                )
        elif child.kind is NodeKind.IMPORT_DECLARATION:
            imports.append(
                _import_spec(
                    arena,
                    child,
                    ordinal=len(imports),
                )
            )
        elif child.kind is NodeKind.MODULE_DECLARATION:
            continue
        else:
            raise FrontendRegistrationError(
                f"unexpected top-level syntax kind {child.kind.value}"
            )

    return ModuleSpec(
        module_symbol_id,
        unit.file_id,
        syntax_index.global_id(unit.file_id, root.id),
        tuple(functions),
        tuple(nominal_types),
        tuple(imports),
        tuple(exports),
        unit.file_id,
    )


def build_registration_plan(
    frontend: SourceBundleFrontendResult,
) -> FrontendRegistrationPlan:
    """Create deterministic registration specs from generic frontend output."""

    symbols = list(frontend.symbol_names)
    symbol_to_id = {name: symbol_id for symbol_id, name in enumerate(symbols)}
    if len(symbol_to_id) != len(symbols):
        raise FrontendRegistrationError("frontend symbol table is not unique")

    synthetic_symbol_first = len(symbols)
    syntax_index = FrontendSyntaxIndex.from_frontend(frontend)
    modules: list[ModuleSpec] = []
    seen_module_symbols: set[int] = set()

    for unit in frontend.units:
        module_symbol_id = _module_symbol_id(
            unit,
            symbols,
            symbol_to_id,
        )
        if module_symbol_id in seen_module_symbols:
            raise FrontendRegistrationError(
                "duplicate module identity in frontend registration plan"
            )
        seen_module_symbols.add(module_symbol_id)
        modules.append(
            _module_spec(
                unit,
                module_symbol_id=module_symbol_id,
                syntax_index=syntax_index,
            )
        )

    return FrontendRegistrationPlan(
        tuple(modules),
        tuple(symbols),
        synthetic_symbol_first,
        syntax_index,
    )


__all__ = [
    "FrontendRegistrationError",
    "FrontendNodeRange",
    "FrontendRegistrationPlan",
    "FrontendSyntaxIndex",
    "build_registration_plan",
]