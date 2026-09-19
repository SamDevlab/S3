"""Resolve generic frontend type syntax into compiler-owned TypeIds.

This module is the hosted TYPE phase bridge between source registration and the
future semantic-expression pass.  It consumes only generic SyntaxArena nodes,
the deterministic FrontendRegistrationPlan, ProgramRegistry, TypeArena, and
SemanticState.  It does not call the reference AST/semantic analyzer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .frontend_registration import FrontendRegistrationPlan
from .generic_syntax import (
    DeclarationPayload,
    IntegerPayload,
    NodeKind,
    SymbolPayload,
    SyntaxArena,
)
from .source_frontend import SourceBundleFrontendResult
from .whole_program import (
    FunctionId,
    FunctionSignature,
    ModuleId,
    NominalTypeId,
    NodeId,
    ProgramRegistry,
    SemanticState,
    TypeArena,
    TypeArenaError,
    TypeId,
    TypeKind,
    TypeSpec,
)


class FrontendTypeError(TypeArenaError):
    """Generic source type syntax cannot be resolved deterministically."""


@dataclass(frozen=True, slots=True)
class ResolvedFieldType:
    field_id: int
    nominal_type_id: NominalTypeId
    type_id: TypeId


@dataclass(frozen=True, slots=True)
class ResolvedVariantPayload:
    variant_id: int
    nominal_type_id: NominalTypeId
    type_ids: tuple[TypeId, ...]


@dataclass(frozen=True, slots=True)
class FrontendTypeResolutionResult:
    syntax_types: tuple[tuple[int, TypeId], ...]
    nominal_types: tuple[tuple[NominalTypeId, TypeId], ...]
    function_signatures: tuple[FunctionSignature, ...]
    fields: tuple[ResolvedFieldType, ...]
    variants: tuple[ResolvedVariantPayload, ...]
    type_parameters: tuple[tuple[str, int, int, TypeId], ...]

    @property
    def resolved_syntax_count(self) -> int:
        return len(self.syntax_types)


_PRIMITIVES: dict[str, TypeKind] = {
    "trit": TypeKind.TRIT,
    "tryte": TypeKind.TRYTE,
    "i64": TypeKind.I64,
    "f64": TypeKind.F64,
    "string": TypeKind.STRING,
    "bytes": TypeKind.BYTES,
    "text": TypeKind.TEXT,
    "host_capability": TypeKind.HOST_CAPABILITY,
    "resource_handle": TypeKind.RESOURCE_HANDLE,
}


class _FrontendTypeResolver:
    def __init__(
        self,
        frontend: SourceBundleFrontendResult,
        plan: FrontendRegistrationPlan,
        registry: ProgramRegistry,
        types: TypeArena,
        semantic: SemanticState,
    ) -> None:
        self.frontend = frontend
        self.plan = plan
        self.registry = registry
        self.types = types
        self.semantic = semantic
        self.symbols = plan.symbol_names
        self.symbol_to_id = {
            name: symbol_id for symbol_id, name in enumerate(self.symbols)
        }
        self.units = {unit.file_id: unit for unit in frontend.units}
        self.module_by_file = {
            record.source_file_id: ModuleId(record.id)
            for _, record in registry.modules.items()
        }
        self.module_by_symbol = {
            record.symbol_id: ModuleId(record.id)
            for _, record in registry.modules.items()
        }
        self.nominal_by_namespace = {
            (int(record.module_id), record.name_symbol_id): NominalTypeId(record.id)
            for _, record in registry.nominal_types.items()
        }
        self.nominal_type_ids: dict[int, TypeId] = {}
        self.syntax_types: dict[int, TypeId] = {}
        self.owner_type_parameters: dict[
            tuple[str, int], dict[int, TypeId]
        ] = {}
        self.type_parameter_rows: list[tuple[str, int, int, TypeId]] = []

    def resolve(self) -> FrontendTypeResolutionResult:
        self._intern_nominal_identities()
        self._intern_type_parameters()

        signatures: list[FunctionSignature] = []
        for _, function in self.registry.functions.items():
            environment = self.owner_type_parameters.get(
                ("function", int(function.id)), {}
            )
            parameters = tuple(
                self.registry.parameters.get(parameter_id)
                for parameter_id in range(
                    function.parameter_range.first,
                    function.parameter_range.first
                    + function.parameter_range.count,
                )
            )
            parameter_types = tuple(
                self._resolve_global_type(
                    parameter.type_syntax_id,
                    function.module_id,
                    environment,
                )
                for parameter in parameters
            )
            result_type = self._resolve_global_type(
                function.declared_result_type_syntax_id,
                function.module_id,
                environment,
            )
            signature = FunctionSignature(
                FunctionId(function.id),
                parameter_types,
                (result_type,),
                function.external,
            )
            self.semantic.add_signature(signature)
            signatures.append(signature)

        field_rows: list[ResolvedFieldType] = []
        variant_rows: list[ResolvedVariantPayload] = []
        for _, nominal in self.registry.nominal_types.items():
            environment = self.owner_type_parameters.get(
                ("nominal", int(nominal.id)), {}
            )
            for field_id in range(
                nominal.field_range.first,
                nominal.field_range.first + nominal.field_range.count,
            ):
                field = self.registry.fields.get(field_id)
                if field.type_syntax_id < 0:
                    raise FrontendTypeError(
                        "S3E_TYPE_SYNTAX_MISSING: record field has no type syntax"
                    )
                type_id = self._resolve_global_type(
                    field.type_syntax_id,
                    nominal.module_id,
                    environment,
                )
                field_rows.append(
                    ResolvedFieldType(field_id, NominalTypeId(nominal.id), type_id)
                )

            for variant_id in range(
                nominal.variant_range.first,
                nominal.variant_range.first + nominal.variant_range.count,
            ):
                variant = self.registry.variants.get(variant_id)
                type_ids = tuple(
                    self._resolve_global_type(
                        syntax_id,
                        nominal.module_id,
                        environment,
                    )
                    for syntax_id in variant.payload_type_syntax_ids
                )
                variant_rows.append(
                    ResolvedVariantPayload(
                        variant_id,
                        NominalTypeId(nominal.id),
                        type_ids,
                    )
                )

        for syntax_id, type_id in sorted(self.syntax_types.items()):
            self.semantic.associate_node_type(NodeId(syntax_id), type_id)

        return FrontendTypeResolutionResult(
            tuple(sorted(self.syntax_types.items())),
            tuple(
                (NominalTypeId(nominal_id), type_id)
                for nominal_id, type_id in sorted(self.nominal_type_ids.items())
            ),
            tuple(signatures),
            tuple(field_rows),
            tuple(variant_rows),
            tuple(self.type_parameter_rows),
        )

    # ------------------------------------------------------------------
    # Identity/bootstrap
    # ------------------------------------------------------------------

    def _intern_nominal_identities(self) -> None:
        for _, nominal in self.registry.nominal_types.items():
            name = self._symbol_name(nominal.name_symbol_id)
            type_id = self.types.nominal(
                nominal.kind,
                nominal.module_id,
                NominalTypeId(nominal.id),
                name=name,
            )
            self.nominal_type_ids[int(nominal.id)] = type_id

    def _intern_type_parameters(self) -> None:
        for _, nominal in self.registry.nominal_types.items():
            self._intern_owner_parameters(
                "nominal",
                int(nominal.id),
                nominal.syntax_node_id,
                nominal.module_id,
            )
        for _, function in self.registry.functions.items():
            self._intern_owner_parameters(
                "function",
                int(function.id),
                function.syntax_node_id,
                function.module_id,
            )

    def _intern_owner_parameters(
        self,
        owner_kind: str,
        owner_id: int,
        syntax_node_id: int,
        module_id: ModuleId,
    ) -> None:
        arena, node_id = self._arena_for_global(syntax_node_id)
        owner_node = arena.node(node_id)
        parameters: dict[int, TypeId] = {}
        ordinal = 0
        for child_id in arena.child_ids(owner_node.id):
            child = arena.node(child_id)
            if child.kind is not NodeKind.TYPE_PARAMETER:
                continue
            payload = arena.payload(child)
            if not isinstance(payload, DeclarationPayload):
                raise FrontendTypeError(
                    "S3E_TYPE_PARAMETER_INVALID: type parameter lacks declaration payload"
                )
            if payload.symbol_id in parameters:
                raise FrontendTypeError(
                    "S3E_TYPE_PARAMETER_DUPLICATE: duplicate type parameter"
                )
            type_id = self.types.intern(
                TypeSpec(
                    TypeKind.TYPE_PARAMETER,
                    owner_id=owner_id,
                    parameter_ordinal=ordinal,
                    name=self._symbol_name(payload.symbol_id),
                    owner_kind=owner_kind,
                )
            )
            parameters[payload.symbol_id] = type_id
            global_child = self.plan.syntax_index.global_id(
                owner_node.span.file_id, child.id
            )
            self.syntax_types[global_child] = type_id
            self.type_parameter_rows.append(
                (owner_kind, owner_id, ordinal, type_id)
            )
            ordinal += 1
        self.owner_type_parameters[(owner_kind, owner_id)] = parameters

    # ------------------------------------------------------------------
    # Type syntax
    # ------------------------------------------------------------------

    def _resolve_global_type(
        self,
        syntax_id: int,
        module_id: ModuleId,
        type_parameters: dict[int, TypeId],
    ) -> TypeId:
        existing = self.syntax_types.get(syntax_id)
        if existing is not None:
            return existing

        arena, local_id = self._arena_for_global(syntax_id)
        node = arena.node(local_id)
        result = self._resolve_node(arena, node.id, module_id, type_parameters)
        self.syntax_types[syntax_id] = result
        return result

    def _resolve_local_type(
        self,
        arena: SyntaxArena,
        local_id: int,
        module_id: ModuleId,
        type_parameters: dict[int, TypeId],
    ) -> TypeId:
        node = arena.node(local_id)
        global_id = self.plan.syntax_index.global_id(node.span.file_id, local_id)
        return self._resolve_global_type(global_id, module_id, type_parameters)

    def _resolve_node(
        self,
        arena: SyntaxArena,
        node_id: int,
        module_id: ModuleId,
        type_parameters: dict[int, TypeId],
    ) -> TypeId:
        node = arena.node(node_id)
        payload = arena.payload(node)

        if node.kind is NodeKind.TYPE_NAME:
            if not isinstance(payload, SymbolPayload):
                raise FrontendTypeError(
                    "S3E_TYPE_SYNTAX_INVALID: TYPE_NAME lacks symbol payload"
                )
            name = self._symbol_name(payload.symbol_id)
            primitive = _PRIMITIVES.get(name)
            if primitive is not None:
                return self.types.primitive(primitive)
            if name == "tryte_vector":
                return self.types.intern(
                    TypeSpec(
                        TypeKind.VECTOR,
                        element_type_id=int(self.types.primitive(TypeKind.TRYTE)),
                    )
                )
            if name == "i64_vector":
                return self.types.intern(
                    TypeSpec(
                        TypeKind.VECTOR,
                        element_type_id=int(self.types.primitive(TypeKind.I64)),
                    )
                )
            if name == "f64_vector":
                return self.types.intern(
                    TypeSpec(
                        TypeKind.VECTOR,
                        element_type_id=int(self.types.primitive(TypeKind.F64)),
                    )
                )
            if name == "i64_map":
                i64 = int(self.types.primitive(TypeKind.I64))
                return self.types.intern(
                    TypeSpec(
                        TypeKind.MAP,
                        element_type_id=i64,
                        type_arguments=(i64,),
                    )
                )
            if name == "i64_set":
                return self.types.intern(
                    TypeSpec(
                        TypeKind.SET,
                        element_type_id=int(self.types.primitive(TypeKind.I64)),
                    )
                )
            raise FrontendTypeError(
                f"S3E_TYPE_UNKNOWN: unknown primitive/closed type {name!r}"
            )

        if node.kind is NodeKind.TYPE_PARAMETER_TYPE:
            if not isinstance(payload, SymbolPayload):
                raise FrontendTypeError(
                    "S3E_TYPE_PARAMETER_INVALID: type parameter reference lacks symbol"
                )
            type_id = type_parameters.get(payload.symbol_id)
            if type_id is None:
                raise FrontendTypeError(
                    f"S3E_TYPE_PARAMETER_UNKNOWN: unknown type parameter {self._symbol_name(payload.symbol_id)!r}"
                )
            return type_id

        if node.kind is NodeKind.ARRAY_TYPE:
            if not isinstance(payload, IntegerPayload):
                raise FrontendTypeError(
                    "S3E_TYPE_SYNTAX_INVALID: array type lacks length payload"
                )
            element = self._single_type_child(
                arena, node.id, module_id, type_parameters
            )
            return self.types.intern(
                TypeSpec(
                    TypeKind.ARRAY,
                    element_type_id=int(element),
                    array_length=payload.value,
                )
            )

        if node.kind is NodeKind.VECTOR_TYPE:
            element = self._single_type_child(
                arena, node.id, module_id, type_parameters
            )
            return self.types.intern(
                TypeSpec(TypeKind.VECTOR, element_type_id=int(element))
            )

        if node.kind in (NodeKind.REFERENCE_TYPE, NodeKind.SLICE_TYPE):
            if not isinstance(payload, IntegerPayload):
                raise FrontendTypeError(
                    "S3E_TYPE_SYNTAX_INVALID: reference/slice lacks mutability payload"
                )
            element = self._single_type_child(
                arena, node.id, module_id, type_parameters
            )
            kind = (
                TypeKind.REFERENCE
                if node.kind is NodeKind.REFERENCE_TYPE
                else TypeKind.SLICE
            )
            return self.types.intern(
                TypeSpec(
                    kind,
                    element_type_id=int(element),
                    mutable=bool(payload.value),
                )
            )

        if node.kind is NodeKind.NOMINAL_TYPE:
            if not isinstance(payload, SymbolPayload):
                raise FrontendTypeError(
                    "S3E_TYPE_SYNTAX_INVALID: nominal type lacks symbol payload"
                )
            name = self._symbol_name(payload.symbol_id)
            argument_ids = tuple(
                self._resolve_local_type(
                    arena, child_id, module_id, type_parameters
                )
                for child_id in arena.child_ids(node.id)
            )

            if name in {"vector", "set"}:
                if len(argument_ids) != 1:
                    raise FrontendTypeError(
                        f"S3E_TYPE_ARGUMENT_COUNT: {name} expects one type argument"
                    )
                return self.types.intern(
                    TypeSpec(
                        TypeKind.VECTOR if name == "vector" else TypeKind.SET,
                        element_type_id=int(argument_ids[0]),
                    )
                )
            if name == "map":
                if len(argument_ids) != 2:
                    raise FrontendTypeError(
                        "S3E_TYPE_ARGUMENT_COUNT: map expects two type arguments"
                    )
                return self.types.intern(
                    TypeSpec(
                        TypeKind.MAP,
                        element_type_id=int(argument_ids[0]),
                        type_arguments=(int(argument_ids[1]),),
                    )
                )

            nominal_id = self._resolve_nominal_identity(
                module_id, payload.symbol_id, name
            )
            record = self.registry.nominal_types.get(int(nominal_id))
            if len(argument_ids) != record.generic_arity:
                raise FrontendTypeError(
                    f"S3E_TYPE_ARGUMENT_COUNT: nominal type {name!r} expects "
                    f"{record.generic_arity} type arguments, got {len(argument_ids)}"
                )
            if not argument_ids:
                return self.nominal_type_ids[int(nominal_id)]
            return self.types.intern(
                TypeSpec(
                    TypeKind.INSTANTIATED,
                    module_id=int(record.module_id),
                    nominal_declaration_id=int(nominal_id),
                    type_arguments=tuple(int(item) for item in argument_ids),
                    name=self._symbol_name(record.name_symbol_id),
                )
            )

        raise FrontendTypeError(
            f"S3E_TYPE_SYNTAX_INVALID: node {node.id} ({node.kind.value}) is not type syntax"
        )

    def _single_type_child(
        self,
        arena: SyntaxArena,
        node_id: int,
        module_id: ModuleId,
        type_parameters: dict[int, TypeId],
    ) -> TypeId:
        children = arena.child_ids(node_id)
        if len(children) != 1:
            raise FrontendTypeError(
                f"S3E_TYPE_SYNTAX_INVALID: type node {node_id} must have one child"
            )
        return self._resolve_local_type(
            arena, children[0], module_id, type_parameters
        )

    # ------------------------------------------------------------------
    # Nominal lookup
    # ------------------------------------------------------------------

    def _resolve_nominal_identity(
        self,
        module_id: ModuleId,
        symbol_id: int,
        name: str,
    ) -> NominalTypeId:
        local = self.nominal_by_namespace.get((int(module_id), symbol_id))
        if local is not None:
            return local

        if "." in name:
            module_name, type_name = name.rsplit(".", 1)
            module_symbol = self.symbol_to_id.get(module_name)
            type_symbol = self.symbol_to_id.get(type_name)
            if module_symbol is None or type_symbol is None:
                raise FrontendTypeError(
                    f"S3E_TYPE_UNKNOWN: unknown qualified nominal type {name!r}"
                )
            target_module = self.module_by_symbol.get(module_symbol)
            if target_module is None:
                raise FrontendTypeError(
                    f"S3E_TYPE_UNKNOWN: unknown module in nominal type {name!r}"
                )
            target = self.nominal_by_namespace.get(
                (int(target_module), type_symbol)
            )
            if target is None:
                raise FrontendTypeError(
                    f"S3E_TYPE_UNKNOWN: unknown nominal type {name!r}"
                )
            return target

        candidates: list[NominalTypeId] = []
        for _, imported in self.registry.imports.items():
            if int(imported.source_module_id) != int(module_id):
                continue
            if imported.alias_symbol_id != symbol_id:
                continue
            candidate = self.nominal_by_namespace.get(
                (int(imported.target_module_id), imported.imported_symbol_id)
            )
            if candidate is not None:
                candidates.append(candidate)

        unique = tuple(sorted(set(int(item) for item in candidates)))
        if len(unique) == 1:
            return NominalTypeId(unique[0])
        if len(unique) > 1:
            raise FrontendTypeError(
                f"S3E_TYPE_AMBIGUOUS: ambiguous nominal type {name!r}"
            )
        raise FrontendTypeError(
            f"S3E_TYPE_UNKNOWN: unknown nominal type {name!r}"
        )

    # ------------------------------------------------------------------
    # Source/symbol helpers
    # ------------------------------------------------------------------

    def _arena_for_global(self, global_node_id: int) -> tuple[SyntaxArena, int]:
        file_id, local_id = self.plan.syntax_index.local_ref(global_node_id)
        try:
            unit = self.units[file_id]
        except KeyError as error:
            raise FrontendTypeError(
                f"S3E_TYPE_SYNTAX_INVALID: unknown file ID {file_id}"
            ) from error
        return unit.syntax_arena, local_id

    def _symbol_name(self, symbol_id: int) -> str:
        if symbol_id < 0 or symbol_id >= len(self.symbols):
            raise FrontendTypeError(
                f"S3E_TYPE_SYMBOL_INVALID: unknown symbol ID {symbol_id}"
            )
        return self.symbols[symbol_id]


def resolve_frontend_types(
    frontend: SourceBundleFrontendResult,
    plan: FrontendRegistrationPlan,
    registry: ProgramRegistry,
    types: TypeArena,
    semantic: SemanticState,
) -> FrontendTypeResolutionResult:
    """Resolve all registered declaration type syntax into canonical TypeIds."""

    return _FrontendTypeResolver(
        frontend,
        plan,
        registry,
        types,
        semantic,
    ).resolve()


__all__ = [
    "FrontendTypeError",
    "FrontendTypeResolutionResult",
    "ResolvedFieldType",
    "ResolvedVariantPayload",
    "resolve_frontend_types",
]
