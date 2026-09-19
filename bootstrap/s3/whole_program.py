"""Deterministic whole-program composition control plane.

The control plane owns program identities, canonical type identities, semantic
associations, structured diagnostics, phase transactions, and the final
composition digest.

Two explicit entry paths coexist:

* prepared-artifact composition for architecture and verifier tests; and
* real hosted source ingestion through the independent generic frontend,
  currently committing INPUT, SYNTAX, and REGISTRATION before failing closed
  at TYPE because generic type/semantic resolution is not implemented.

Neither path fabricates lowering or emission.  The default production Python
compiler remains separate, and this module does not constitute Stage1 or a
self-hosted compiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping, NewType

from .compiler_substrate import CapacityError, OutputSink, SourceBundle, StableArena
from .generic_ir import IRProgram
from .generic_verifier import VerificationResult, verify_ir_program


ProgramId = NewType("ProgramId", int)
ModuleId = NewType("ModuleId", int)
FunctionId = NewType("FunctionId", int)
NominalTypeId = NewType("NominalTypeId", int)
TypeId = NewType("TypeId", int)
ScopeId = NewType("ScopeId", int)
DeclarationId = NewType("DeclarationId", int)
StorageId = NewType("StorageId", int)
NodeId = NewType("NodeId", int)
BlockId = NewType("BlockId", int)
ValueId = NewType("ValueId", int)
InstructionId = NewType("InstructionId", int)
DiagnosticId = NewType("DiagnosticId", int)
PhaseId = NewType("PhaseId", int)


def _integer(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CompositionError(f"{label} must be a non-negative integer")
    return value


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    return value


def _digest(value: object) -> str:
    encoded = json.dumps(
        _canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _error_code(error: BaseException) -> str:
    text = str(error)
    if text.startswith("S3E_") and ":" in text:
        return text.split(":", 1)[0]
    return "S3E_COMPOSITION_FAILURE"


class CompositionError(RuntimeError):
    """Base class for fail-closed composition errors."""


class RegistrationError(CompositionError):
    pass


class TypeArenaError(CompositionError):
    pass


class SemanticStateError(CompositionError):
    pass


class PhaseTransitionError(CompositionError):
    pass


class TypeKind(str, Enum):
    TRIT = "trit"
    TRYTE = "tryte"
    I64 = "i64"
    F64 = "f64"
    STRING = "string"
    BYTES = "bytes"
    TEXT = "text"
    VECTOR = "vector"
    MAP = "map"
    SET = "set"
    ARRAY = "array"
    RECORD = "record"
    ENUM = "enum"
    REFERENCE = "reference"
    SLICE = "slice"
    TYPE_PARAMETER = "type_parameter"
    INSTANTIATED = "instantiated"


class PhaseKind(str, Enum):
    INPUT = "input"
    SYNTAX = "syntax"
    REGISTRATION = "registration"
    TYPE = "type"
    SEMANTIC = "semantic"
    LOWERING = "lowering"
    VERIFICATION = "verification"
    EMITTER = "emitter"
    OUTPUT = "output"
    FINALIZE = "finalize"


class PhaseStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMMITTED = "committed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class IdRange:
    first: int
    count: int

    def __post_init__(self) -> None:
        if self.first < 0 or self.count < 0:
            raise ValueError("ID range must be non-negative")


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    symbol_id: int
    type_syntax_id: int = -1
    ordinal: int = 0


@dataclass(frozen=True, slots=True)
class FieldSpec:
    symbol_id: int
    type_id: int
    ordinal: int = 0
    mutable: bool = False
    span: tuple[int, int, int] | None = None
    type_syntax_id: int = -1


@dataclass(frozen=True, slots=True)
class VariantSpec:
    symbol_id: int
    discriminant: int
    ordinal: int = 0
    payload_type_ids: tuple[int, ...] = ()
    payload_type_syntax_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    name_symbol_id: int
    syntax_node_id: int
    parameters: tuple[ParameterSpec, ...] = ()
    declared_result_type_syntax_id: int = -1
    ordinal: int = 0
    exported: bool = False
    external: bool = False
    generic_arity: int = 0


@dataclass(frozen=True, slots=True)
class NominalTypeSpec:
    name_symbol_id: int
    syntax_node_id: int
    kind: TypeKind
    fields: tuple[FieldSpec, ...] = ()
    variants: tuple[VariantSpec, ...] = ()
    generic_arity: int = 0
    ordinal: int = 0


@dataclass(frozen=True, slots=True)
class ImportSpec:
    target_module_symbol_id: int
    imported_symbol_id: int
    alias_symbol_id: int = -1
    ordinal: int = 0
    span: tuple[int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class ExportSpec:
    symbol_id: int
    kind: str = "function"
    ordinal: int = 0


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    module_symbol_id: int
    source_file_id: int
    root_node_id: int
    functions: tuple[FunctionSpec, ...] = ()
    nominal_types: tuple[NominalTypeSpec, ...] = ()
    imports: tuple[ImportSpec, ...] = ()
    exports: tuple[ExportSpec, ...] = ()
    manifest_ordinal: int = 0


@dataclass(frozen=True, slots=True)
class ModuleRecord:
    id: ModuleId
    symbol_id: int
    source_file_id: int
    root_node_id: int
    function_range: IdRange
    nominal_type_range: IdRange
    import_range: IdRange
    export_range: IdRange


@dataclass(frozen=True, slots=True)
class FunctionRecord:
    id: FunctionId
    module_id: ModuleId
    name_symbol_id: int
    syntax_node_id: int
    parameter_range: IdRange
    declared_result_type_syntax_id: int
    exported: bool
    external: bool
    generic_arity: int = 0


@dataclass(frozen=True, slots=True)
class ParameterRecord:
    id: int
    function_id: FunctionId
    symbol_id: int
    type_syntax_id: int
    ordinal: int


@dataclass(frozen=True, slots=True)
class NominalTypeRecord:
    id: NominalTypeId
    module_id: ModuleId
    name_symbol_id: int
    syntax_node_id: int
    kind: TypeKind
    field_range: IdRange
    variant_range: IdRange
    generic_arity: int


@dataclass(frozen=True, slots=True)
class ImportRecord:
    id: int
    source_module_id: ModuleId
    target_module_id: ModuleId
    imported_symbol_id: int
    alias_symbol_id: int
    span: tuple[int, int, int] | None


@dataclass(frozen=True, slots=True)
class ExportRecord:
    id: int
    module_id: ModuleId
    symbol_id: int
    kind: str


@dataclass(frozen=True, slots=True)
class ProgramRegistryCheckpoint:
    modules: int
    functions: int
    parameters: int
    nominal_types: int
    fields: int
    variants: int
    imports: int
    exports: int


class ProgramRegistry:
    """Deterministic indexed registration tables for one program root."""

    def __init__(self, *, capacity: int | None = None) -> None:
        self.capacity = capacity
        self.modules: StableArena[ModuleRecord] = StableArena(capacity)
        self.functions: StableArena[FunctionRecord] = StableArena(capacity)
        self.parameters: StableArena[ParameterRecord] = StableArena(capacity)
        self.nominal_types: StableArena[NominalTypeRecord] = StableArena(capacity)
        self.fields: StableArena[FieldSpec] = StableArena(capacity)
        self.variants: StableArena[VariantSpec] = StableArena(capacity)
        self.imports: StableArena[ImportRecord] = StableArena(capacity)
        self.exports: StableArena[ExportRecord] = StableArena(capacity)
        self._module_by_symbol: dict[int, ModuleId] = {}
        self._function_by_namespace: dict[tuple[int, int], FunctionId] = {}
        self._type_by_namespace: dict[tuple[int, int], NominalTypeId] = {}

    def checkpoint(self) -> ProgramRegistryCheckpoint:
        return ProgramRegistryCheckpoint(
            self.modules.checkpoint(), self.functions.checkpoint(),
            self.parameters.checkpoint(),
            self.nominal_types.checkpoint(), self.fields.checkpoint(),
            self.variants.checkpoint(), self.imports.checkpoint(),
            self.exports.checkpoint(),
        )

    def rollback(self, checkpoint: ProgramRegistryCheckpoint) -> None:
        for arena, cursor in (
            (self.modules, checkpoint.modules),
            (self.functions, checkpoint.functions),
            (self.parameters, checkpoint.parameters),
            (self.nominal_types, checkpoint.nominal_types),
            (self.fields, checkpoint.fields),
            (self.variants, checkpoint.variants),
            (self.imports, checkpoint.imports),
            (self.exports, checkpoint.exports),
        ):
            arena.rollback(cursor)
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        self._module_by_symbol = {record.symbol_id: ModuleId(record.id) for _, record in self.modules.items()}
        self._function_by_namespace = {
            (int(record.module_id), record.name_symbol_id): FunctionId(record.id)
            for _, record in self.functions.items()
        }
        self._type_by_namespace = {
            (int(record.module_id), record.name_symbol_id): NominalTypeId(record.id)
            for _, record in self.nominal_types.items()
        }

    def _validate_import_cycles(self) -> None:
        graph: dict[int, tuple[int, ...]] = {
            module_id: ()
            for module_id, _ in self.modules.items()
        }
        mutable: dict[int, list[int]] = {
            module_id: []
            for module_id in graph
        }
        for _, record in self.imports.items():
            mutable[int(record.source_module_id)].append(int(record.target_module_id))
        graph = {
            module_id: tuple(sorted(set(targets)))
            for module_id, targets in mutable.items()
        }

        visiting: set[int] = set()
        visited: set[int] = set()

        def visit(module_id: int) -> None:
            if module_id in visited:
                return
            if module_id in visiting:
                raise RegistrationError(
                    "S3E_MODULE_CYCLE: module import cycle"
                )
            visiting.add(module_id)
            for target in graph.get(module_id, ()):
                visit(target)
            visiting.remove(module_id)
            visited.add(module_id)

        for module_id in sorted(graph):
            visit(module_id)

    @staticmethod
    def _module_key(spec: ModuleSpec) -> tuple[int, int, int, int]:
        return (spec.manifest_ordinal, spec.source_file_id, spec.module_symbol_id, spec.root_node_id)

    def register(self, specs: Iterable[ModuleSpec]) -> tuple[ModuleRecord, ...]:
        checkpoint = self.checkpoint()
        ordered = tuple(sorted(specs, key=self._module_key))
        try:
            for spec in ordered:
                _integer(spec.module_symbol_id, "module symbol ID")
                _integer(spec.source_file_id, "source file ID")
                _integer(spec.root_node_id, "module root node ID")
                if spec.module_symbol_id in self._module_by_symbol:
                    raise RegistrationError("S3E_MODULE_DUPLICATE: duplicate module identity")
                module_id = ModuleId(self.modules.checkpoint())
                function_specs = tuple(sorted(spec.functions, key=lambda item: (item.ordinal, item.name_symbol_id, item.syntax_node_id)))
                nominal_specs = tuple(sorted(spec.nominal_types, key=lambda item: (item.ordinal, item.name_symbol_id, item.syntax_node_id)))
                function_first = self.functions.checkpoint()
                nominal_first = self.nominal_types.checkpoint()
                for function in function_specs:
                    key = (int(module_id), function.name_symbol_id)
                    if key in self._function_by_namespace or key in self._type_by_namespace:
                        raise RegistrationError("S3E_SEMANTIC_INVALID_PROGRAM: duplicate function or namespace conflict")
                    parameter_first = self.parameters.checkpoint()
                    for parameter in sorted(function.parameters, key=lambda item: (item.ordinal, item.symbol_id)):
                        self.parameters.append(ParameterRecord(
                            self.parameters.checkpoint(), FunctionId(self.functions.checkpoint()),
                            parameter.symbol_id, parameter.type_syntax_id, parameter.ordinal,
                        ))
                    if function.generic_arity < 0:
                        raise RegistrationError(
                            "S3E_SEMANTIC_INVALID_PROGRAM: invalid function generic arity"
                        )
                    record = FunctionRecord(
                        FunctionId(self.functions.checkpoint()), module_id,
                        function.name_symbol_id, function.syntax_node_id,
                        IdRange(parameter_first, self.parameters.checkpoint() - parameter_first),
                        function.declared_result_type_syntax_id,
                        function.exported, function.external,
                        function.generic_arity,
                    )
                    self.functions.append(record)
                    self._function_by_namespace[key] = record.id
                for nominal in nominal_specs:
                    key = (int(module_id), nominal.name_symbol_id)
                    if key in self._type_by_namespace or key in self._function_by_namespace:
                        raise RegistrationError("S3E_TYPE_DUPLICATE: duplicate nominal type or namespace conflict")
                    if nominal.generic_arity < 0:
                        raise RegistrationError("S3E_SEMANTIC_INVALID_PROGRAM: invalid generic arity")
                    type_id = NominalTypeId(self.nominal_types.checkpoint())
                    nominal_field_first = self.fields.checkpoint()
                    nominal_variant_first = self.variants.checkpoint()
                    seen_fields: set[int] = set()
                    for field in sorted(nominal.fields, key=lambda item: (item.ordinal, item.symbol_id)):
                        if field.symbol_id in seen_fields:
                            raise RegistrationError("S3E_RECORD_FIELD_DUPLICATE: duplicate record field")
                        seen_fields.add(field.symbol_id)
                        self.fields.append(field)
                    seen_variants: set[int] = set()
                    for variant in sorted(nominal.variants, key=lambda item: (item.ordinal, item.symbol_id)):
                        if variant.symbol_id in seen_variants:
                            raise RegistrationError("S3E_ENUM_VARIANT_DUPLICATE: duplicate enum variant")
                        seen_variants.add(variant.symbol_id)
                        self.variants.append(variant)
                    record = NominalTypeRecord(
                        type_id, module_id, nominal.name_symbol_id, nominal.syntax_node_id,
                        nominal.kind,
                        IdRange(
                            nominal_field_first,
                            self.fields.checkpoint() - nominal_field_first,
                        ),
                        IdRange(
                            nominal_variant_first,
                            self.variants.checkpoint() - nominal_variant_first,
                        ),
                        nominal.generic_arity,
                    )
                    self.nominal_types.append(record)
                    self._type_by_namespace[key] = record.id
                module = ModuleRecord(
                    module_id, spec.module_symbol_id, spec.source_file_id, spec.root_node_id,
                    IdRange(function_first, self.functions.checkpoint() - function_first),
                    IdRange(nominal_first, self.nominal_types.checkpoint() - nominal_first),
                    IdRange(self.imports.checkpoint(), 0), IdRange(self.exports.checkpoint(), 0),
                )
                self.modules.append(module)
                self._module_by_symbol[spec.module_symbol_id] = module_id
            module_specs = tuple(zip(ordered, tuple(self.modules.items())[-len(ordered):])) if ordered else ()
            declared_exports: dict[int, set[int]] = {}
            for _, existing_export in self.exports.items():
                declared_exports.setdefault(
                    int(existing_export.module_id), set()
                ).add(existing_export.symbol_id)
            for spec, (_, module) in module_specs:
                declared_exports.setdefault(int(module.id), set()).update(
                    item.symbol_id for item in spec.exports
                )
            for spec, (_, module) in module_specs:
                import_first = self.imports.checkpoint()
                export_first = self.exports.checkpoint()
                aliases: set[int] = set()
                for item in sorted(spec.imports, key=lambda value: (value.ordinal, value.target_module_symbol_id, value.imported_symbol_id, value.alias_symbol_id)):
                    target = self._module_by_symbol.get(item.target_module_symbol_id)
                    if target is None:
                        raise RegistrationError("S3E_MODULE_NOT_FOUND: import target is not registered")
                    alias = item.alias_symbol_id if item.alias_symbol_id >= 0 else item.imported_symbol_id
                    if alias in aliases:
                        raise RegistrationError("S3E_IMPORT_DUPLICATE: duplicate import alias")
                    aliases.add(alias)
                    target_key = (int(target), item.imported_symbol_id)
                    if (
                        target_key not in self._function_by_namespace
                        and target_key not in self._type_by_namespace
                    ):
                        raise RegistrationError(
                            "S3E_IMPORT_UNKNOWN_SYMBOL: imported symbol is not registered"
                        )
                    if item.imported_symbol_id not in declared_exports.get(
                        int(target), set()
                    ):
                        raise RegistrationError(
                            "S3E_IMPORT_PRIVATE_SYMBOL: imported symbol is private"
                        )
                    if (
                        item.alias_symbol_id >= 0
                        and target_key in self._type_by_namespace
                    ):
                        raise RegistrationError(
                            "S3E_SEMANTIC_INVALID_PROGRAM: type import aliases are not supported yet"
                        )
                    self.imports.append(ImportRecord(self.imports.checkpoint(), module.id, target, item.imported_symbol_id, alias, item.span))
                exported: set[int] = set()
                for item in sorted(spec.exports, key=lambda value: (value.ordinal, value.symbol_id, value.kind)):
                    if item.symbol_id in exported:
                        raise RegistrationError("S3E_IMPORT_CONFLICT: duplicate export")
                    if (int(module.id), item.symbol_id) not in self._function_by_namespace and (int(module.id), item.symbol_id) not in self._type_by_namespace:
                        raise RegistrationError("S3E_IMPORT_UNKNOWN_SYMBOL: exported symbol is not registered")
                    exported.add(item.symbol_id)
                    self.exports.append(ExportRecord(self.exports.checkpoint(), module.id, item.symbol_id, item.kind))
                self.modules._items[module.id] = ModuleRecord(
                    module.id, module.symbol_id, module.source_file_id, module.root_node_id,
                    module.function_range, module.nominal_type_range,
                    IdRange(import_first, self.imports.checkpoint() - import_first),
                    IdRange(export_first, self.exports.checkpoint() - export_first),
                )
            self._validate_import_cycles()
            return tuple(record for _, record in self.modules.items())
        except Exception:
            self.rollback(checkpoint)
            raise

    def function(self, function_id: FunctionId) -> FunctionRecord:
        return self.functions.get(int(function_id))

    def structural_view(self) -> dict[str, object]:
        return {
            "modules": tuple(self.modules.items()),
            "functions": tuple(self.functions.items()),
            "parameters": tuple(self.parameters.items()),
            "nominal_types": tuple(self.nominal_types.items()),
            "imports": tuple(self.imports.items()),
            "exports": tuple(self.exports.items()),
        }

    def structural_digest(self) -> str:
        return _digest(self.structural_view())


@dataclass(frozen=True, slots=True)
class TypeSpec:
    kind: TypeKind
    element_type_id: int = -1
    array_length: int = -1
    mutable: bool = False
    module_id: int = -1
    nominal_declaration_id: int = -1
    type_arguments: tuple[int, ...] = ()
    owner_id: int = -1
    parameter_ordinal: int = -1
    name: str = ""
    owner_kind: str = ""


@dataclass(frozen=True, slots=True)
class TypeInfo:
    id: TypeId
    kind: TypeKind
    element_type_id: TypeId | None = None
    array_length: int | None = None
    mutable: bool = False
    module_id: ModuleId | None = None
    nominal_declaration_id: NominalTypeId | None = None
    type_arguments: tuple[TypeId, ...] = ()
    owner_id: int | None = None
    parameter_ordinal: int | None = None
    name: str = ""
    owner_kind: str = ""


@dataclass(frozen=True, slots=True)
class TypeArenaCheckpoint:
    next_id: int


class TypeArena:
    """Canonical compiler-owned type identity arena."""

    _PRIMITIVES = (TypeKind.TRIT, TypeKind.TRYTE, TypeKind.I64, TypeKind.F64, TypeKind.STRING, TypeKind.BYTES, TypeKind.TEXT)

    def __init__(self, *, capacity: int | None = None) -> None:
        self.capacity = capacity
        self.types: StableArena[TypeInfo] = StableArena(capacity)
        self._keys: dict[tuple[object, ...], TypeId] = {}
        for kind in self._PRIMITIVES:
            self._intern(TypeSpec(kind=kind))

    @property
    def primitive_ids(self) -> dict[TypeKind, TypeId]:
        return {kind: TypeId(index) for index, kind in enumerate(self._PRIMITIVES)}

    def checkpoint(self) -> TypeArenaCheckpoint:
        return TypeArenaCheckpoint(self.types.checkpoint())

    def rollback(self, checkpoint: TypeArenaCheckpoint) -> None:
        self.types.rollback(checkpoint.next_id)
        self._keys = {
            self._key_for_info(info): TypeId(item_id)
            for item_id, info in self.types.items()
        }

    @staticmethod
    def _key_for_spec(spec: TypeSpec) -> tuple[object, ...]:
        return (
            spec.kind.value, spec.element_type_id, spec.array_length, bool(spec.mutable),
            spec.module_id, spec.nominal_declaration_id, tuple(spec.type_arguments),
            spec.owner_id, spec.parameter_ordinal, spec.name, spec.owner_kind,
        )

    @staticmethod
    def _key_for_info(info: TypeInfo) -> tuple[object, ...]:
        return (
            info.kind.value, int(info.element_type_id) if info.element_type_id is not None else -1,
            info.array_length if info.array_length is not None else -1, bool(info.mutable),
            int(info.module_id) if info.module_id is not None else -1,
            int(info.nominal_declaration_id) if info.nominal_declaration_id is not None else -1,
            tuple(int(item) for item in info.type_arguments),
            info.owner_id if info.owner_id is not None else -1,
            info.parameter_ordinal if info.parameter_ordinal is not None else -1,
            info.name, info.owner_kind,
        )

    def _intern(self, spec: TypeSpec) -> TypeId:
        key = self._key_for_spec(spec)
        existing = self._keys.get(key)
        if existing is not None:
            return existing
        if spec.kind in {TypeKind.VECTOR, TypeKind.MAP, TypeKind.SET, TypeKind.ARRAY, TypeKind.REFERENCE, TypeKind.SLICE} and spec.element_type_id < 0:
            raise TypeArenaError("S3E_SEMANTIC_INVALID_PROGRAM: structural type lacks element type")
        if spec.kind is TypeKind.ARRAY and spec.array_length < 0:
            raise TypeArenaError("S3E_SEMANTIC_INVALID_PROGRAM: invalid array size")
        if spec.kind in {TypeKind.RECORD, TypeKind.ENUM, TypeKind.INSTANTIATED} and (spec.module_id < 0 or spec.nominal_declaration_id < 0):
            raise TypeArenaError("S3E_SEMANTIC_INVALID_PROGRAM: nominal type lacks identity")
        if spec.kind is TypeKind.TYPE_PARAMETER:
            if spec.owner_id < 0 or spec.parameter_ordinal < 0:
                raise TypeArenaError("S3E_SEMANTIC_INVALID_PROGRAM: type parameter lacks owner")
            if spec.owner_kind not in {"function", "nominal"}:
                raise TypeArenaError("S3E_SEMANTIC_INVALID_PROGRAM: type parameter owner kind is invalid")
        element = TypeId(spec.element_type_id) if spec.element_type_id >= 0 else None
        info = TypeInfo(
            TypeId(self.types.checkpoint()), spec.kind, element,
            spec.array_length if spec.kind is TypeKind.ARRAY else None,
            spec.mutable,
            ModuleId(spec.module_id) if spec.module_id >= 0 else None,
            NominalTypeId(spec.nominal_declaration_id) if spec.nominal_declaration_id >= 0 else None,
            tuple(TypeId(item) for item in spec.type_arguments),
            spec.owner_id if spec.owner_id >= 0 else None,
            spec.parameter_ordinal if spec.parameter_ordinal >= 0 else None,
            spec.name,
            spec.owner_kind,
        )
        type_id = self.types.append(info)
        self._keys[key] = type_id
        return type_id

    def intern(self, spec: TypeSpec) -> TypeId:
        return self._intern(spec)

    def intern_many(self, specs: Iterable[TypeSpec]) -> tuple[TypeId, ...]:
        ordered = tuple(sorted(specs, key=self._key_for_spec))
        return tuple(self._intern(spec) for spec in ordered)

    def primitive(self, kind: TypeKind) -> TypeId:
        if kind not in self._PRIMITIVES:
            raise TypeArenaError("requested type is not a primitive")
        return self.primitive_ids[kind]

    def nominal(self, kind: TypeKind, module_id: ModuleId, declaration_id: NominalTypeId, *, name: str = "") -> TypeId:
        if kind not in {TypeKind.RECORD, TypeKind.ENUM}:
            raise TypeArenaError("nominal() requires record or enum")
        return self._intern(TypeSpec(kind=kind, module_id=int(module_id), nominal_declaration_id=int(declaration_id), name=name))

    def get(self, type_id: TypeId) -> TypeInfo:
        return self.types.get(int(type_id))

    def structural_digest(self) -> str:
        return _digest(tuple(self.types.items()))


@dataclass(frozen=True, slots=True)
class ScopeRecord:
    id: ScopeId
    parent: ScopeId | None
    function_id: FunctionId | None


@dataclass(frozen=True, slots=True)
class SemanticDeclaration:
    id: DeclarationId
    symbol_id: int
    scope_id: ScopeId
    type_id: TypeId
    storage_id: StorageId | None
    mutable: bool
    kind: str
    span: tuple[int, int, int] | None


@dataclass(frozen=True, slots=True)
class FunctionSignature:
    function_id: FunctionId
    parameter_type_ids: tuple[TypeId, ...]
    result_type_ids: tuple[TypeId, ...]
    external: bool = False


@dataclass(frozen=True, slots=True)
class CallTarget:
    node_id: NodeId
    function_id: FunctionId


@dataclass(frozen=True, slots=True)
class SemanticCheckpoint:
    scopes: int
    declarations: int
    storage: int
    signatures: int
    changes: int


class SemanticState:
    """Explicit semantic associations owned by one whole-program context."""

    def __init__(self, registry: ProgramRegistry, types: TypeArena, *, capacity: int | None = None) -> None:
        self.registry = registry
        self.types = types
        self.scopes: StableArena[ScopeRecord] = StableArena(capacity)
        self.declarations: StableArena[SemanticDeclaration] = StableArena(capacity)
        self.storage: StableArena[tuple[StorageId, DeclarationId, bool]] = StableArena(capacity)
        self.signatures: StableArena[FunctionSignature] = StableArena(capacity)
        self.node_types: dict[int, TypeId] = {}
        self.call_targets: dict[int, FunctionId] = {}
        self.mutability: dict[int, bool] = {}
        self._changes: list[tuple[str, int, object | None]] = []

    def checkpoint(self) -> SemanticCheckpoint:
        return SemanticCheckpoint(len(self.scopes), len(self.declarations), len(self.storage), len(self.signatures), len(self._changes))

    def rollback(self, checkpoint: SemanticCheckpoint) -> None:
        for kind, key, previous in reversed(self._changes[checkpoint.changes:]):
            target = {"node_type": self.node_types, "call": self.call_targets, "mutable": self.mutability}[kind]
            if previous is None:
                target.pop(key, None)
            else:
                target[key] = previous  # type: ignore[assignment]
        del self._changes[checkpoint.changes:]
        self.scopes.rollback(checkpoint.scopes)
        self.declarations.rollback(checkpoint.declarations)
        self.storage.rollback(checkpoint.storage)
        self.signatures.rollback(checkpoint.signatures)

    def new_scope(self, parent: ScopeId | None = None, function_id: FunctionId | None = None) -> ScopeId:
        if parent is not None and int(parent) not in self.scopes:
            raise SemanticStateError("S3E_SEMANTIC_INVALID_PROGRAM: unknown scope parent")
        scope_id = ScopeId(self.scopes.checkpoint())
        self.scopes.append(ScopeRecord(scope_id, parent, function_id))
        return scope_id

    def declare(self, symbol_id: int, scope_id: ScopeId, type_id: TypeId, *, storage_id: StorageId | None = None, mutable: bool = False, kind: str = "local", span: tuple[int, int, int] | None = None) -> DeclarationId:
        if int(scope_id) not in self.scopes or int(type_id) not in self.types.types:
            raise SemanticStateError("S3E_SEMANTIC_INVALID_PROGRAM: declaration association is dangling")
        declaration_id = DeclarationId(self.declarations.checkpoint())
        self.declarations.append(SemanticDeclaration(declaration_id, symbol_id, scope_id, type_id, storage_id, mutable, kind, span))
        if storage_id is not None:
            self.storage.append((storage_id, declaration_id, mutable))
        self.mutability[int(declaration_id)] = mutable
        self._changes.append(("mutable", int(declaration_id), None))
        return declaration_id

    def associate_node_type(self, node_id: NodeId, type_id: TypeId) -> None:
        if int(type_id) not in self.types.types:
            raise SemanticStateError("S3E_SEMANTIC_INVALID_PROGRAM: node type is unknown")
        key = int(node_id)
        self._changes.append(("node_type", key, self.node_types.get(key)))
        self.node_types[key] = type_id

    def associate_call(self, node_id: NodeId, function_id: FunctionId) -> None:
        if int(function_id) not in self.registry.functions:
            raise SemanticStateError("S3E_SEMANTIC_INVALID_PROGRAM: call target is unknown")
        key = int(node_id)
        self._changes.append(("call", key, self.call_targets.get(key)))
        self.call_targets[key] = function_id

    def set_mutability(self, declaration_id: DeclarationId, mutable: bool) -> None:
        if int(declaration_id) not in self.declarations:
            raise SemanticStateError("S3E_SEMANTIC_INVALID_PROGRAM: declaration is unknown")
        key = int(declaration_id)
        self._changes.append(("mutable", key, self.mutability.get(key)))
        self.mutability[key] = mutable

    def add_signature(self, signature: FunctionSignature) -> int:
        if int(signature.function_id) not in self.registry.functions:
            raise SemanticStateError("S3E_SEMANTIC_INVALID_PROGRAM: signature function is unknown")
        for type_id in (*signature.parameter_type_ids, *signature.result_type_ids):
            if int(type_id) not in self.types.types:
                raise SemanticStateError("S3E_SEMANTIC_INVALID_PROGRAM: signature type is unknown")
        return self.signatures.append(signature)

    def structural_digest(self) -> str:
        return _digest({
            "scopes": tuple(self.scopes.items()), "declarations": tuple(self.declarations.items()),
            "storage": tuple(self.storage.items()), "signatures": tuple(self.signatures.items()),
            "node_types": tuple(sorted(self.node_types.items())), "call_targets": tuple(sorted(self.call_targets.items())),
            "mutability": tuple(sorted(self.mutability.items())),
        })


@dataclass(frozen=True, slots=True)
class DiagnosticRecord:
    id: DiagnosticId
    phase: PhaseKind
    code: str
    message: str
    fatal: bool = True
    notes: tuple[str, ...] = ()
    function_id: int | None = None
    block_id: int | None = None
    instruction_id: int | None = None


class DiagnosticArena:
    """Bounded, append-only structured diagnostics with direct IDs."""

    def __init__(self, *, capacity: int = 256) -> None:
        if capacity <= 0:
            raise ValueError("diagnostic capacity must be positive")
        self.capacity = capacity
        self.items: StableArena[DiagnosticRecord] = StableArena(capacity)

    def checkpoint(self) -> int:
        return self.items.checkpoint()

    def rollback(self, checkpoint: int) -> None:
        self.items.rollback(checkpoint)

    def append(self, phase: PhaseKind, code: str, message: str, *, fatal: bool = True, notes: Iterable[str] = (), function_id: int | None = None, block_id: int | None = None, instruction_id: int | None = None) -> DiagnosticId:
        if self.items.checkpoint() >= self.capacity:
            raise CapacityError("diagnostic arena capacity exhausted")
        diagnostic_id = DiagnosticId(self.items.checkpoint())
        self.items.append(DiagnosticRecord(diagnostic_id, phase, code, message, fatal, tuple(notes), function_id, block_id, instruction_id))
        return diagnostic_id

    def digest(self) -> str:
        return _digest(tuple(self.items.items()))

    def ordered(self) -> tuple[DiagnosticRecord, ...]:
        return tuple(item for _, item in self.items.items())


@dataclass(frozen=True, slots=True)
class PhaseRecord:
    id: PhaseId
    kind: PhaseKind
    status: PhaseStatus
    reason: str = ""
    diagnostic_id: DiagnosticId | None = None


class PhaseOrchestrator:
    """Deterministic phase state machine with explicit skip/failure edges."""

    _ORDER = tuple(PhaseKind)

    def __init__(self, diagnostics: DiagnosticArena) -> None:
        self.diagnostics = diagnostics
        self.records: StableArena[PhaseRecord] = StableArena()
        self._active: PhaseId | None = None
        self._next_index = 0

    def begin(self, kind: PhaseKind) -> PhaseId:
        if self._active is not None:
            raise PhaseTransitionError("a phase is already running")
        expected = self._ORDER[self._next_index] if self._next_index < len(self._ORDER) else None
        if expected is not kind:
            raise PhaseTransitionError(f"S3E_PHASE_INVALID_TRANSITION: expected {expected}, got {kind}")
        phase_id = PhaseId(self.records.checkpoint())
        self.records.append(PhaseRecord(phase_id, kind, PhaseStatus.RUNNING))
        self._active = phase_id
        return phase_id

    def _finish(self, status: PhaseStatus, reason: str = "", diagnostic_id: DiagnosticId | None = None) -> None:
        if self._active is None:
            raise PhaseTransitionError("no phase is running")
        record = self.records.get(int(self._active))
        self.records._items[int(self._active)] = PhaseRecord(record.id, record.kind, status, reason, diagnostic_id)
        self._active = None
        self._next_index += 1

    def commit(self) -> None:
        self._finish(PhaseStatus.COMMITTED)

    def skip(self, reason: str) -> None:
        if not reason:
            raise ValueError("skip reason must be explicit")
        self._finish(PhaseStatus.SKIPPED, reason)

    def fail(self, code: str, message: str, *, notes: Iterable[str] = (), function_id: int | None = None, block_id: int | None = None, instruction_id: int | None = None) -> DiagnosticId:
        if self._active is None:
            raise PhaseTransitionError("no phase is running")
        diagnostic_id = self.diagnostics.append(self.records.get(int(self._active)).kind, code, message, notes=notes, function_id=function_id, block_id=block_id, instruction_id=instruction_id)
        self._finish(PhaseStatus.FAILED, message, diagnostic_id)
        while self._next_index < len(self._ORDER):
            phase_id = PhaseId(self.records.checkpoint())
            self.records.append(PhaseRecord(phase_id, self._ORDER[self._next_index], PhaseStatus.SKIPPED, "blocked by failed phase"))
            self._next_index += 1
        return diagnostic_id

    def trace(self) -> tuple[str, ...]:
        return tuple(f"{record.kind.value.upper()}:{record.status.value.upper()}" for _, record in self.records.items())

    @property
    def next_phase(self) -> PhaseKind | None:
        if self._active is not None:
            return self.records.get(int(self._active)).kind
        if self._next_index >= len(self._ORDER):
            return None
        return self._ORDER[self._next_index]

    @property
    def terminal(self) -> bool:
        return self._next_index == len(self._ORDER) and self._active is None


@dataclass(frozen=True, slots=True)
class SemanticSeed:
    node_types: tuple[tuple[int, int], ...] = ()
    calls: tuple[tuple[int, int], ...] = ()
    declarations: tuple[tuple[int, int, int, int, bool, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedProgramArtifacts:
    syntax: object
    modules: tuple[ModuleSpec, ...]
    type_specs: tuple[TypeSpec, ...] = ()
    semantic: SemanticSeed = SemanticSeed()
    ir: IRProgram | None = None
    output: bytes | None = None


@dataclass(frozen=True, slots=True)
class WholeProgramCompileResult:
    success: bool
    output: bytes
    diagnostics: tuple[DiagnosticRecord, ...]
    phase_trace: tuple[str, ...]
    structural_digest: str
    ir_digest: str = ""
    test_artifact_input: bool = False

    @property
    def output_length(self) -> int:
        return len(self.output)


class WholeProgramContext:
    """One isolated, reentrant owner of all composition state."""

    def __init__(self, sources: SourceBundle, *, output_capacity: int = 1 << 20, diagnostic_capacity: int = 256) -> None:
        self.sources = sources
        self.program_id = ProgramId(0)
        self.registry = ProgramRegistry()
        self.types = TypeArena()
        self.semantic = SemanticState(self.registry, self.types)
        self.diagnostics = DiagnosticArena(capacity=diagnostic_capacity)
        self.phases = PhaseOrchestrator(self.diagnostics)
        self.sink = OutputSink(output_capacity)
        self.syntax: object | None = None
        self.ir: IRProgram | None = None

    def structural_digest(self) -> str:
        return _digest({
            "program_id": int(self.program_id), "sources": self.sources.digest(),
            "registry": self.registry.structural_digest(), "types": self.types.structural_digest(),
            "semantic": self.semantic.structural_digest(), "diagnostics": self.diagnostics.digest(),
            "phase_trace": self.phases.trace(), "ir": self.ir.structural_digest() if self.ir is not None else "",
            "output": sha256(self.sink.to_bytes()).hexdigest(),
        })

    def _failure_result(self, *, test_artifact_input: bool = False) -> WholeProgramCompileResult:
        return WholeProgramCompileResult(False, self.sink.to_bytes(), self.diagnostics.ordered(), self.phases.trace(), self.structural_digest(), test_artifact_input=test_artifact_input)

    def compose(self, artifacts: PreparedProgramArtifacts, *, failure_phase: PhaseKind | None = None) -> WholeProgramCompileResult:
        self.syntax = artifacts.syntax
        try:
            self.phases.begin(PhaseKind.INPUT)
            if failure_phase is PhaseKind.INPUT:
                self.phases.fail("S3E_INPUT_INVALID", "injected input failure")
                return self._failure_result(test_artifact_input=True)
            self.phases.commit()
            self.phases.begin(PhaseKind.SYNTAX)
            validator = getattr(artifacts.syntax, "validate", None)
            if validator is not None:
                validator()
            if failure_phase is PhaseKind.SYNTAX:
                self.phases.fail("S3E_SYNTAX_INVALID", "injected syntax failure")
                return self._failure_result(test_artifact_input=True)
            self.phases.commit()
            self.phases.begin(PhaseKind.REGISTRATION)
            self.registry.register(artifacts.modules)
            if failure_phase is PhaseKind.REGISTRATION:
                self.phases.fail("S3E_MODULE_DUPLICATE", "injected registration failure")
                return self._failure_result(test_artifact_input=True)
            self.phases.commit()
            self.phases.begin(PhaseKind.TYPE)
            self.types.intern_many(artifacts.type_specs)
            if failure_phase is PhaseKind.TYPE:
                self.phases.fail("S3E_SEMANTIC_INVALID_PROGRAM", "injected type failure")
                return self._failure_result(test_artifact_input=True)
            self.phases.commit()
            self.phases.begin(PhaseKind.SEMANTIC)
            root_scope = self.semantic.new_scope()
            for node_id, type_id in artifacts.semantic.node_types:
                self.semantic.associate_node_type(NodeId(node_id), TypeId(type_id))
            for node_id, function_id in artifacts.semantic.calls:
                self.semantic.associate_call(NodeId(node_id), FunctionId(function_id))
            for symbol_id, scope_id, type_id, storage_id, mutable, kind in artifacts.semantic.declarations:
                self.semantic.declare(symbol_id, ScopeId(scope_id if scope_id >= 0 else int(root_scope)), TypeId(type_id), storage_id=StorageId(storage_id) if storage_id >= 0 else None, mutable=mutable, kind=kind)
            if failure_phase is PhaseKind.SEMANTIC:
                self.phases.fail("S3E_SEMANTIC_INVALID_PROGRAM", "injected semantic failure")
                return self._failure_result(test_artifact_input=True)
            self.phases.commit()
            self.phases.begin(PhaseKind.LOWERING)
            self.phases.skip("lowering is not implemented; IR is TEST_ARTIFACT_INPUT")
            self.ir = artifacts.ir
            self.phases.begin(PhaseKind.VERIFICATION)
            if artifacts.ir is None:
                self.phases.fail("S3E_VERIFY_INVALID_IR", "no prepared IR artifact was supplied")
                return self._failure_result(test_artifact_input=True)
            verification = verify_ir_program(artifacts.ir)
            if not verification.success:
                self.phases.fail(
                    verification.diagnostic_code or "S3E_VERIFY_INVALID_IR",
                    verification.message or "prepared IR failed verification",
                    function_id=verification.function_id,
                    block_id=verification.block_id,
                    instruction_id=verification.instruction_id,
                )
                return self._failure_result(test_artifact_input=True)
            self.phases.commit()
            self.phases.begin(PhaseKind.EMITTER)
            self.phases.skip("emitter is not implemented; output is TEST_ARTIFACT_INPUT")
            self.phases.begin(PhaseKind.OUTPUT)
            output_checkpoint = self.sink.checkpoint()
            if artifacts.output is None:
                self.phases.fail("S3E_OUTPUT_MISSING", "no prepared output artifact was supplied")
                return self._failure_result(test_artifact_input=True)
            try:
                self.sink.append(artifacts.output)
            except CapacityError:
                self.sink.rollback(output_checkpoint)
                self.phases.fail("S3E_OUTPUT_CAPACITY", "prepared output exceeds the caller-owned sink capacity")
                return self._failure_result(test_artifact_input=True)
            self.phases.commit()
            self.phases.begin(PhaseKind.FINALIZE)
            self.phases.commit()
            return WholeProgramCompileResult(True, self.sink.to_bytes(), self.diagnostics.ordered(), self.phases.trace(), self.structural_digest(), artifacts.ir.structural_digest(), True)
        except (CompositionError, ValueError, KeyError) as error:
            if self.phases._active is not None:
                self.phases.fail(_error_code(error), str(error))
            else:
                self.diagnostics.append(PhaseKind.FINALIZE, _error_code(error), str(error))
            return self._failure_result(test_artifact_input=True)


def compile_program(source_bundle: SourceBundle, output_sink: OutputSink, *, prepared_artifacts: PreparedProgramArtifacts | None = None) -> WholeProgramCompileResult:
    """Whole-program composition root.

    With prepared_artifacts, preserve the explicit test-artifact composition
    path used by the existing architecture tests.

    Without prepared artifacts, real source now executes the independent hosted
    frontend through INPUT, SYNTAX, and REGISTRATION. The root then fails closed
    at TYPE because semantic type resolution, expression semantics, lowering,
    and emission are not implemented by this generic pipeline yet.
    """
    context = WholeProgramContext(source_bundle, output_capacity=output_sink.capacity)
    context.sink = output_sink
    if prepared_artifacts is None:
        from .frontend_control_plane import ingest_source_frontend

        frontend = ingest_source_frontend(context)
        if not frontend.success:
            return context._failure_result(test_artifact_input=False)

        context.phases.begin(PhaseKind.TYPE)
        context.phases.fail(
            "S3E_TYPE_PHASE_UNAVAILABLE",
            "generic source frontend is registered; real TYPE/semantic resolution is not implemented",
        )
        return context._failure_result(test_artifact_input=False)

    return context.compose(prepared_artifacts)


__all__ = [
    "BlockId", "CallTarget", "CompositionError", "DeclarationId", "DiagnosticArena", "DiagnosticId", "DiagnosticRecord",
    "ExportRecord", "ExportSpec", "FieldSpec", "FunctionId", "FunctionRecord", "FunctionSpec", "FunctionSignature",
    "IdRange", "ImportRecord", "ImportSpec", "InstructionId", "ModuleId", "ModuleRecord", "ModuleSpec", "NominalTypeId",
    "NominalTypeRecord", "NominalTypeSpec", "NodeId", "ParameterRecord", "ParameterSpec", "PhaseKind", "PhaseOrchestrator", "PhaseRecord",
    "PhaseStatus", "PreparedProgramArtifacts", "ProgramId", "ProgramRegistry", "ProgramRegistryCheckpoint", "RegistrationError",
    "ScopeId", "SemanticDeclaration", "SemanticSeed", "SemanticState", "SemanticStateError", "StorageId", "TypeArena",
    "TypeArenaCheckpoint", "TypeArenaError", "TypeId", "TypeInfo", "TypeKind", "TypeSpec", "ValueId", "WholeProgramCompileResult",
    "WholeProgramContext", "compile_program",
]