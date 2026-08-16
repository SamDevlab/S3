"""Two-phase name, type, scope, mutability, and return-path analysis for S3."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from . import ast
from .large_index import SliceBounds
from .diagnostics import DiagnosticCode, SemanticError, SourceLocation
from .static_text import StaticTextDecodeError, decode_static_text
from .numeric import NumericError, I64_MAX, I64_MIN, validate_f64, validate_i64
from .ternary import (
    TRIT_MAX,
    TRIT_MIN,
    TRYTE_MAX,
    TRYTE_MIN,
    TernaryRangeError,
    TernaryWidth,
    add,
    compare,
    invert,
    tritwise_max,
    tritwise_min,
)


STATIC_TEXT_QUERY_BUILTINS = {
    "contains": ast.TypeName.TRIT,
    "starts_with": ast.TypeName.TRIT,
    "ends_with": ast.TypeName.TRIT,
    "find": ast.TypeName.TRYTE,
}

STATIC_TEXT_TRANSFORM_BUILTINS = {
    "upper": 1,
    "lower": 1,
    "trim": 1,
    "repeat": 2,
    "replace": 3,
}


_DYNAMIC_BUILTIN_LOCATION = SourceLocation(0, 1, 1)
_DYNAMIC_BUILTINS: dict[str, tuple[tuple[ast.DeclaredType, ...], ast.TypeName]] = {
    "bytes_new": ((ast.TypeName.I64,), ast.TypeName.BYTES),
    "bytes_len": ((ast.ReferenceType(ast.TypeName.BYTES, False, _DYNAMIC_BUILTIN_LOCATION),), ast.TypeName.I64),
    "bytes_capacity": ((ast.ReferenceType(ast.TypeName.BYTES, False, _DYNAMIC_BUILTIN_LOCATION),), ast.TypeName.I64),
    "bytes_get": ((ast.ReferenceType(ast.TypeName.BYTES, False, _DYNAMIC_BUILTIN_LOCATION), ast.TypeName.I64), ast.TypeName.TRYTE),
    "bytes_set": ((ast.ReferenceType(ast.TypeName.BYTES, True, _DYNAMIC_BUILTIN_LOCATION), ast.TypeName.I64, ast.TypeName.TRYTE), ast.TypeName.TRYTE),
    "bytes_push": ((ast.ReferenceType(ast.TypeName.BYTES, True, _DYNAMIC_BUILTIN_LOCATION), ast.TypeName.TRYTE), ast.TypeName.TRYTE),
    "bytes_reserve": ((ast.ReferenceType(ast.TypeName.BYTES, True, _DYNAMIC_BUILTIN_LOCATION), ast.TypeName.I64), ast.TypeName.TRYTE),
    "bytes_clone": ((ast.ReferenceType(ast.TypeName.BYTES, False, _DYNAMIC_BUILTIN_LOCATION),), ast.TypeName.BYTES),
    "bytes_concat": ((ast.ReferenceType(ast.TypeName.BYTES, False, _DYNAMIC_BUILTIN_LOCATION), ast.ReferenceType(ast.TypeName.BYTES, False, _DYNAMIC_BUILTIN_LOCATION)), ast.TypeName.BYTES),
    "bytes_slice": ((ast.ReferenceType(ast.TypeName.BYTES, False, _DYNAMIC_BUILTIN_LOCATION), ast.TypeName.I64, ast.TypeName.I64), ast.TypeName.BYTES),
    "bytes_from_text": ((ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION),), ast.TypeName.BYTES),
    "text_new": ((ast.TypeName.I64,), ast.TypeName.TEXT),
    "text_from_static": ((ast.TypeName.STRING,), ast.TypeName.TEXT),
    "text_len": ((ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION),), ast.TypeName.I64),
    "text_capacity": ((ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION),), ast.TypeName.I64),
    "text_reserve": ((ast.ReferenceType(ast.TypeName.TEXT, True, _DYNAMIC_BUILTIN_LOCATION), ast.TypeName.I64), ast.TypeName.TRYTE),
    "text_append": ((ast.ReferenceType(ast.TypeName.TEXT, True, _DYNAMIC_BUILTIN_LOCATION), ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION)), ast.TypeName.TRYTE),
    "text_append_static": ((ast.ReferenceType(ast.TypeName.TEXT, True, _DYNAMIC_BUILTIN_LOCATION), ast.TypeName.STRING), ast.TypeName.TRYTE),
    "text_clone": ((ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION),), ast.TypeName.TEXT),
    "text_concat": ((ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION), ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION)), ast.TypeName.TEXT),
    "text_slice": ((ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION), ast.TypeName.I64, ast.TypeName.I64), ast.TypeName.TEXT),
    "text_find": ((ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION), ast.ReferenceType(ast.TypeName.TEXT, False, _DYNAMIC_BUILTIN_LOCATION)), ast.TypeName.I64),
    "text_from_bytes": ((ast.ReferenceType(ast.TypeName.BYTES, False, _DYNAMIC_BUILTIN_LOCATION),), ast.TypeName.TEXT),
}


@dataclass(frozen=True, slots=True)
class FunctionType:
    name: str
    parameter_types: tuple[ast.DeclaredType, ...]
    return_type: ast.DeclaredType
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class RecordType:
    name: str
    fields: tuple[ast.RecordField, ...]
    location: SourceLocation

    def field(self, name: str) -> ast.RecordField | None:
        for field in self.fields:
            if field.name == name:
                return field
        return None


@dataclass(frozen=True, slots=True)
class RecordLeaf:
    path: tuple[str, ...]
    type_name: ast.TypeName
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class EnumPayloadLeaf:
    variant_name: str
    path: tuple[str, ...]
    type_name: ast.TypeName
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class EnumVariantLayout:
    name: str
    discriminant: int
    payload_fields: tuple[ast.RecordField, ...]
    payload_leaves: tuple[EnumPayloadLeaf, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class EnumLayout:
    name: str
    variants: tuple[EnumVariantLayout, ...]
    cell_count: int
    slot_types: tuple[ast.TypeName, ...]
    tag_type: ast.TypeName
    inactive_slot_policy: str
    location: SourceLocation

    @property
    def payload_cell_count(self) -> int:
        return self.cell_count - 1

    def variant(self, name: str) -> EnumVariantLayout | None:
        for variant in self.variants:
            if variant.name == name:
                return variant
        return None

    def payload_leaves(self, variant_name: str) -> tuple[EnumPayloadLeaf, ...]:
        variant = self.variant(variant_name)
        if variant is None:
            raise SemanticError(
                f"enum '{self.name}' has no variant '{variant_name}'",
                self.location,
                diagnostic_code=DiagnosticCode.ENUM_VARIANT_UNKNOWN,
            )
        return variant.payload_leaves


class ValueLayoutKind(Enum):
    SCALAR = "scalar"
    FIXED_STATIC_TEXT = "fixed_static_text"
    FIXED_ARRAY = "fixed_array"
    RECORD = "record"
    ENUM = "enum"


class ReturnClass(Enum):
    SCALAR_RETURN_COMPATIBLE = "scalar_return_compatible"
    AGGREGATE_FIXED_LAYOUT = "aggregate_fixed_layout"
    NOT_RETURNABLE = "not_returnable"


@dataclass(frozen=True, slots=True)
class ValueCell:
    path: tuple[str, ...]
    type_name: ast.TypeName
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class FixedValueLayout:
    type_name: ast.DeclaredType
    kind: ValueLayoutKind
    cells: tuple[ValueCell, ...]
    location: SourceLocation
    dependencies: tuple[str, ...] = ()

    @property
    def cell_count(self) -> int:
        return len(self.cells)


@dataclass(frozen=True, slots=True)
class EnumType:
    name: str
    variants: tuple[ast.EnumVariant, ...]
    location: SourceLocation

    def variant(self, name: str) -> ast.EnumVariant | None:
        for variant in self.variants:
            if variant.name == name:
                return variant
        return None

    def discriminant(self, name: str) -> int:
        for index, variant in enumerate(self.variants):
            if variant.name == name:
                return index
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class Binding:
    type_name: ast.DeclaredType
    mutable: bool
    parameter: bool
    location: SourceLocation
    static_text: str | None = None
    constant_value: int | None = None
    scope_depth: int = 0
    reference_origin: tuple[int, int, bool] | None = None


@dataclass(frozen=True, slots=True)
class PlaceInfo:
    type_name: ast.DeclaredType
    readable: bool
    writable: bool
    addressable: bool
    storage_symbol: str | None
    declaration_scope: int
    initialized: bool


@dataclass(frozen=True, slots=True)
class ReferenceProvenance:
    root_storage: object
    projection: object
    target_type: ast.DeclaredType
    mutable: bool


@dataclass(frozen=True, slots=True)
class BlockFlow:
    terminates: bool
    definitely_returns: bool


@dataclass(frozen=True, slots=True)
class SemanticModel:
    """Expression types and the complete file-level function table."""

    expression_types: dict[int, ast.DeclaredType]
    functions: dict[str, FunctionType]
    records: dict[str, RecordType]
    enums: dict[str, EnumType]
    static_text_values: dict[int, str]
    constant_values: dict[int, int | float]
    simplified_expressions: dict[int, ast.Expression]
    place_info: dict[int, PlaceInfo] = field(default_factory=dict)
    reference_origins: dict[int, tuple[int, int, bool]] = field(default_factory=dict)
    contains_references: bool = False
    reference_provenance: dict[int, ReferenceProvenance] = field(default_factory=dict)
    contains_dynamic: bool = False

    def type_of(self, expression: ast.Expression) -> ast.TypeName:
        try:
            result = self.expression_types[id(expression)]
            assert isinstance(result, ast.TypeName)
            return result
        except (KeyError, AssertionError) as error:
            raise SemanticError(
                "internal error: expression has no scalar semantic type",
                expression.location,
            ) from error

    def declared_type_of(self, expression: ast.Expression) -> ast.DeclaredType:
        try:
            return self.expression_types[id(expression)]
        except KeyError as error:
            raise SemanticError(
                "internal error: expression has no semantic type",
                expression.location,
            ) from error

    def array_type_of(self, expression: ast.Expression) -> ast.ArrayType:
        try:
            result = self.expression_types[id(expression)]
            assert isinstance(result, ast.ArrayType)
            return result
        except (KeyError, AssertionError) as error:
            raise SemanticError(
                "internal error: expression has no array semantic type",
                expression.location,
            ) from error

    def static_text_of(self, expression: ast.Expression) -> str | None:
        return self.static_text_values.get(id(expression))

    def constant_value_of(self, expression: ast.Expression) -> int | float | None:
        return self.constant_values.get(id(expression))

    def provenance_of(self, expression: ast.Expression) -> ReferenceProvenance | None:
        return self.reference_provenance.get(id(expression))

    def simplified_expression_of(self, expression: ast.Expression) -> ast.Expression | None:
        current = expression
        target = None
        while id(current) in self.simplified_expressions:
            current = self.simplified_expressions[id(current)]
            target = current
        return target

    def function(self, name: str) -> FunctionType:
        try:
            return self.functions[name]
        except KeyError as error:
            raise SemanticError(f"unknown function '{name}'") from error

    def record(self, name: str) -> RecordType:
        try:
            return self.records[name]
        except KeyError as error:
            raise SemanticError(f"unknown record type '{name}'") from error

    def enum(self, name: str) -> EnumType:
        try:
            return self.enums[name]
        except KeyError as error:
            raise SemanticError(f"unknown enum type '{name}'") from error

    def is_enum_type(self, type_name: ast.DeclaredType) -> bool:
        return isinstance(type_name, ast.NominalType) and type_name.name in self.enums

    def is_record_type(self, type_name: ast.DeclaredType) -> bool:
        return isinstance(type_name, ast.NominalType) and type_name.name in self.records

    def fixed_value_layout(self, type_name: ast.DeclaredType) -> FixedValueLayout:
        return _fixed_value_layout(self.records, self.enums, type_name)

    def return_classification(self, type_name: ast.DeclaredType) -> ReturnClass:
        return _return_classification(self.records, self.enums, type_name)

    def record_leaves(self, name: str) -> tuple[RecordLeaf, ...]:
        layout = self.fixed_value_layout(ast.NominalType(name, self.record(name).location))
        assert layout.kind is ValueLayoutKind.RECORD
        return tuple(
            RecordLeaf(cell.path, cell.type_name, cell.location) for cell in layout.cells
        )

    def record_leaf_count(self, name: str) -> int:
        return len(self.record_leaves(name))

    def enum_layout(self, name: str) -> EnumLayout:
        self.fixed_value_layout(ast.NominalType(name, self.enum(name).location))
        return _enum_layout(self.records, self.enums, name)

    def enum_payload_leaves(
        self,
        name: str,
        variant_name: str,
    ) -> tuple[EnumPayloadLeaf, ...]:
        return self.enum_layout(name).payload_leaves(variant_name)

    def enum_cell_count(self, name: str) -> int:
        return self.enum_layout(name).cell_count


def _record_leaves(
    records: dict[str, RecordType],
    enums: dict[str, EnumType],
    name: str,
    prefix: tuple[str, ...] = (),
) -> tuple[RecordLeaf, ...]:
    leaves: list[RecordLeaf] = []
    record = records[name]
    for field in record.fields:
        path = (*prefix, field.name)
        if isinstance(field.type_name, ast.TypeName):
            leaves.append(RecordLeaf(path, field.type_name, field.location))
        elif isinstance(field.type_name, ast.ArrayType):
            assert isinstance(field.type_name.element_type, ast.TypeName)
            leaves.extend(
                RecordLeaf(
                    (*path, f"index{index}"),
                    field.type_name.element_type,
                    field.location,
                )
                for index in range(field.type_name.length)
            )
        elif isinstance(field.type_name, ast.NominalType):
            if field.type_name.name in enums:
                layout = _enum_layout(records, enums, field.type_name.name)
                if layout.cell_count == 1:
                    leaves.append(RecordLeaf(path, ast.TypeName.TRYTE, field.location))
                else:
                    for index in range(layout.cell_count):
                        leaves.append(
                            RecordLeaf(
                                (*path, f"cell{index}"),
                                ast.TypeName.TRYTE,
                                field.location,
                            )
                        )
            elif field.type_name.name in records:
                leaves.extend(
                    _record_leaves(records, enums, field.type_name.name, path)
                )
            else:
                raise SemanticError(
                    f"unknown type '{field.type_name.name}'",
                    field.location,
                )
        else:
            raise SemanticError("unsupported record field type", field.location)
    return tuple(leaves)


def _fixed_value_layout(
    records: dict[str, RecordType],
    enums: dict[str, EnumType],
    type_name: ast.DeclaredType,
) -> FixedValueLayout:
    if isinstance(type_name, ast.ArrayType):
        if not isinstance(type_name.element_type, ast.TypeName) or (
            type_name.element_type not in (ast.TypeName.TRIT, ast.TypeName.TRYTE)
        ):
            raise SemanticError(
                "fixed array value layout requires trit or tryte elements",
                type_name.location,
            )
        if not 1 <= type_name.length <= TRYTE_MAX + 1:
            raise SemanticError(
                f"fixed array length must be in [1, {TRYTE_MAX + 1}]",
                type_name.location,
            )
        return FixedValueLayout(
            type_name,
            ValueLayoutKind.FIXED_ARRAY,
            tuple(
                ValueCell(
                    (f"index{index}",),
                    type_name.element_type,
                    type_name.location,
                )
                for index in range(type_name.length)
            ),
            type_name.location,
        )
    if isinstance(type_name, ast.TypeName):
        location = SourceLocation(0, 1, 1)
        kind = (
            ValueLayoutKind.FIXED_STATIC_TEXT
            if type_name is ast.TypeName.STRING
            else ValueLayoutKind.SCALAR
        )
        return FixedValueLayout(
            type_name,
            kind,
            (ValueCell((), type_name, location),),
            location,
        )
    if type_name.name in records:
        record = records[type_name.name]
        leaves = _record_leaves(records, enums, type_name.name)
        return FixedValueLayout(
            type_name,
            ValueLayoutKind.RECORD,
            tuple(ValueCell(leaf.path, leaf.type_name, leaf.location) for leaf in leaves),
            record.location,
            _nominal_layout_dependencies(records, type_name),
        )
    if type_name.name in enums:
        enum = enums[type_name.name]
        layout = _enum_layout(records, enums, type_name.name)
        cells = [
            ValueCell(("tag",), layout.tag_type, enum.location),
            *(
                ValueCell(("payload", f"cell{index}"), slot_type, enum.location)
                for index, slot_type in enumerate(layout.slot_types[1:])
            ),
        ]
        return FixedValueLayout(
            type_name,
            ValueLayoutKind.ENUM,
            tuple(cells),
            enum.location,
            (type_name.name,),
        )
    raise SemanticError(f"unknown type '{type_name.name}'", type_name.location)


def _return_classification(
    records: dict[str, RecordType],
    enums: dict[str, EnumType],
    type_name: ast.DeclaredType,
) -> ReturnClass:
    layout = _fixed_value_layout(records, enums, type_name)
    if layout.cell_count == 1:
        return ReturnClass.SCALAR_RETURN_COMPATIBLE
    return ReturnClass.AGGREGATE_FIXED_LAYOUT


def _nominal_layout_dependencies(
    records: dict[str, RecordType],
    type_name: ast.NominalType,
) -> tuple[str, ...]:
    record = records.get(type_name.name)
    if record is None:
        return (type_name.name,)
    dependencies: list[str] = []
    for field in record.fields:
        if isinstance(field.type_name, ast.NominalType):
            dependencies.extend(_nominal_layout_dependencies(records, field.type_name))
    return tuple(dependencies)


def _enum_payload_leaves(
    records: dict[str, RecordType],
    enums: dict[str, EnumType],
    variant_name: str,
    fields: tuple[ast.RecordField, ...],
    prefix: tuple[str, ...] = (),
) -> tuple[EnumPayloadLeaf, ...]:
    leaves: list[EnumPayloadLeaf] = []
    for field in fields:
        path = (*prefix, field.name)
        if isinstance(field.type_name, ast.TypeName):
            leaves.append(
                EnumPayloadLeaf(variant_name, path, field.type_name, field.location)
            )
        elif isinstance(field.type_name, ast.ArrayType):
            assert isinstance(field.type_name.element_type, ast.TypeName)
            leaves.extend(
                EnumPayloadLeaf(
                    variant_name,
                    (*path, f"index{index}"),
                    field.type_name.element_type,
                    field.location,
                )
                for index in range(field.type_name.length)
            )
        elif isinstance(field.type_name, ast.NominalType):
            if field.type_name.name in enums:
                layout = _enum_layout(records, enums, field.type_name.name)
                for index in range(layout.cell_count):
                    leaves.append(
                        EnumPayloadLeaf(
                            variant_name,
                            (*path, f"cell{index}"),
                            ast.TypeName.TRYTE,
                            field.location,
                        )
                    )
            elif field.type_name.name in records:
                for leaf in _record_leaves(records, enums, field.type_name.name, path):
                    leaves.append(
                        EnumPayloadLeaf(
                            variant_name,
                            leaf.path,
                            leaf.type_name,
                            leaf.location,
                        )
                    )
            else:
                raise SemanticError(
                    f"unknown type '{field.type_name.name}'",
                    field.location,
                )
        else:
            raise SemanticError("unsupported enum payload field type", field.location)
    return tuple(leaves)


def _enum_layout(
    records: dict[str, RecordType],
    enums: dict[str, EnumType],
    name: str,
) -> EnumLayout:
    enum = enums[name]
    variants: list[EnumVariantLayout] = []
    payload_slot_types: list[ast.TypeName | None] = []
    for discriminant, variant in enumerate(enum.variants):
        leaves = _enum_payload_leaves(
            records,
            enums,
            variant.name,
            variant.payload_fields,
        )
        for index, leaf in enumerate(leaves):
            if index == len(payload_slot_types):
                payload_slot_types.append(leaf.type_name)
                continue
            current = payload_slot_types[index]
            if current is not leaf.type_name:
                raise SemanticError(
                    (
                        f"enum '{enum.name}' payload slot {index + 1} has "
                        f"incompatible types {current.value} and {leaf.type_name.value}"
                    ),
                    leaf.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
                )
        variants.append(
            EnumVariantLayout(
                variant.name,
                discriminant,
                variant.payload_fields,
                leaves,
                variant.location,
            )
        )
    return EnumLayout(
        name,
        tuple(variants),
        1 + len(payload_slot_types),
        (ast.TypeName.TRYTE, *tuple(slot for slot in payload_slot_types if slot is not None)),
        ast.TypeName.TRYTE,
        "zero-equivalent scalar cells",
        enum.location,
    )


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.expression_types: dict[int, ast.DeclaredType] = {}
        self.static_text_values: dict[int, str] = {}
        self.constant_values: dict[int, int | float] = {}
        self.simplified_expressions: dict[int, ast.Expression] = {}
        self.functions: dict[str, FunctionType] = {}
        self.records: dict[str, RecordType] = {}
        self.enums: dict[str, EnumType] = {}
        self.scopes: list[dict[str, Binding]] = []
        self.parameter_names: set[str] = set()
        self.return_type: ast.DeclaredType = ast.TypeName.TRYTE
        self.loop_depth = 0
        self.place_info: dict[int, PlaceInfo] = {}
        self.reference_origins: dict[int, tuple[int, int, bool]] = {}
        self.reference_provenance: dict[int, ReferenceProvenance] = {}
        self.contains_references = False
        self.contains_dynamic = False
        self.moved_bindings: set[int] = set()
        self.active_borrows: dict[int, tuple[int, bool]] = {}

    def analyze(self, program: ast.Program) -> SemanticModel:
        from .semantic_declarations import DeclarationCollector

        collected = DeclarationCollector().collect(program)
        self.enums = collected.enums
        self.records = collected.records
        self.functions = collected.functions
        for name, (parameter_types, return_type) in _DYNAMIC_BUILTINS.items():
            if name in self.functions:
                raise SemanticError(
                    f"function '{name}' conflicts with reserved dynamic builtin",
                    _DYNAMIC_BUILTIN_LOCATION,
                )
            self.functions[name] = FunctionType(
                name,
                parameter_types,
                return_type,
                _DYNAMIC_BUILTIN_LOCATION,
            )
        for record in self.records.values():
            for field in record.fields:
                self._validate_declared_type(field.type_name, aggregate=True)
        for enum in self.enums.values():
            for variant in enum.variants:
                for field in variant.payload_fields:
                    self._validate_declared_type(field.type_name, aggregate=True)

        if "main" not in self.functions:
            raise SemanticError("program must declare a 'main' function", program.location)
        main = self.functions["main"]
        if main.parameter_types:
            raise SemanticError(
                "entry function 'main' must not declare parameters",
                main.location,
            )
        if main.return_type is ast.TypeName.STRING:
            raise SemanticError(
                "entry function 'main' cannot return string",
                main.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE,
            )
        if isinstance(main.return_type, ast.ArrayType):
            raise SemanticError(
                "entry function 'main' must return one scalar cell",
                main.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE,
            )
        if self._return_classification(main.return_type) is ReturnClass.AGGREGATE_FIXED_LAYOUT:
            raise SemanticError(
                "entry function 'main' must return one scalar cell",
                main.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE,
            )
        for function in program.functions:
            self._validate_declared_type(function.return_type, return_type=True)
            for parameter in function.parameters:
                self._validate_declared_type(parameter.type_name)
            try:
                self._analyze_function(function)
            except SemanticError as error:
                error.add_diagnostic_context(function=function.name)
                raise
        return SemanticModel(
            dict(self.expression_types),
            dict(self.functions),
            dict(self.records),
            dict(self.enums),
            dict(self.static_text_values),
            dict(self.constant_values),
            dict(self.simplified_expressions),
            dict(self.place_info),
            dict(self.reference_origins),
            self.contains_references,
            dict(self.reference_provenance),
            self.contains_dynamic,
        )

    def _record_leaf_count(self, name: str) -> int:
        layout = _fixed_value_layout(
            self.records,
            self.enums,
            ast.NominalType(name, self.records[name].location),
        )
        return layout.cell_count

    def _enum_cell_count(self, name: str) -> int:
        layout = _fixed_value_layout(
            self.records,
            self.enums,
            ast.NominalType(name, self.enums[name].location),
        )
        return layout.cell_count

    def _return_classification(self, type_name: ast.DeclaredType) -> ReturnClass:
        return _return_classification(self.records, self.enums, type_name)


    def _analyze_function(self, function: ast.FunctionDeclaration) -> None:
        signature = self.functions[function.name]
        self.return_type = signature.return_type
        self.parameter_names = {parameter.name for parameter in function.parameters}
        self.moved_bindings = set()
        self.active_borrows = {}
        self.scopes = [
            {
                parameter.name: Binding(
                    parameter.type_name,
                    mutable=False,
                    parameter=True,
                    location=parameter.location,
                    scope_depth=0,
                    reference_origin=(id(parameter), 0, parameter.type_name.mutable)
                    if isinstance(parameter.type_name, ast.ReferenceType)
                    else None,
                )
                for parameter in function.parameters
            }
        ]
        flow = self._analyze_block(function.body, create_scope=False)
        if not flow.definitely_returns:
            raise SemanticError(
                f"function '{function.name}' has a path without returning "
                f"{_type_display(self.return_type)}",
                function.location,
            )

    def _analyze_block(self, block: ast.Block, *, create_scope: bool) -> BlockFlow:
        borrow_snapshot = dict(self.active_borrows)
        if create_scope:
            self.scopes.append({})
        block_terminates = False
        definitely_returns = False
        try:
            for statement in block.statements:
                if block_terminates:
                    raise SemanticError(
                        "unreachable statement after return or terminating switch",
                        statement.location,
                    )
                flow = self._analyze_statement(statement)
                if flow.terminates:
                    block_terminates = True
                if flow.definitely_returns:
                    definitely_returns = True
            return BlockFlow(terminates=block_terminates, definitely_returns=definitely_returns)
        finally:
            self.active_borrows = borrow_snapshot
            if create_scope:
                self.scopes.pop()

    def _analyze_statement(self, statement: ast.Statement) -> BlockFlow:
        if isinstance(statement, ast.VariableDeclaration):
            self._analyze_declaration(statement)
            return BlockFlow(terminates=False, definitely_returns=False)
        if isinstance(statement, ast.AssignmentStatement):
            self._analyze_assignment(statement)
            return BlockFlow(terminates=False, definitely_returns=False)
        if isinstance(statement, ast.ReturnStatement):
            actual = self._analyze_expression(statement.expression, self.return_type)
            self._require_type(
                actual,
                self.return_type,
                statement.expression.location,
                "returned expression",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE,
            )
            if self._is_dynamic_type(self.return_type):
                self._consume_owner(statement.expression)
            return BlockFlow(terminates=True, definitely_returns=True)
        if isinstance(statement, ast.BreakStatement):
            if self.loop_depth == 0:
                raise SemanticError("break outside loop", statement.location)
            return BlockFlow(terminates=True, definitely_returns=False)
        if isinstance(statement, ast.ContinueStatement):
            if self.loop_depth == 0:
                raise SemanticError("continue outside loop", statement.location)
            return BlockFlow(terminates=True, definitely_returns=False)
        if isinstance(statement, ast.AssignmentStatement):
            return self._analyze_assignment(statement)
        if isinstance(statement, ast.CompoundAssignmentStatement):
            return self._analyze_compound_assignment(statement)
        if isinstance(statement, ast.DiscardStatement):
            self._analyze_expression(statement.expression, None)
            return BlockFlow(definitely_returns=False, terminates=False)
        if isinstance(statement, ast.SwitchStatement):
            return self._analyze_switch(statement)
        if isinstance(statement, ast.WhileStatement):
            return self._analyze_while(statement)
        if isinstance(statement, ast.ForStatement):
            return self._analyze_for(statement)
        raise SemanticError("unsupported statement", statement.location)

    def _analyze_for(self, statement: ast.ForStatement) -> BlockFlow:
        start_type = self._analyze_expression(
            statement.start_expression,
            ast.TypeName.TRYTE,
        )
        self._require_type(
            start_type,
            ast.TypeName.TRYTE,
            statement.start_expression.location,
            "for loop range start bound",
        )
        end_type = self._analyze_expression(
            statement.end_expression,
            ast.TypeName.TRYTE,
        )
        self._require_type(
            end_type,
            ast.TypeName.TRYTE,
            statement.end_expression.location,
            "for loop range end bound",
        )
        step_type = self._analyze_expression(
            statement.step_expression,
            ast.TypeName.TRYTE,
        )
        self._require_type(
            step_type,
            ast.TypeName.TRYTE,
            statement.step_expression.location,
            "for loop range step",
        )
        if isinstance(statement.step_expression, ast.IntegerLiteral) and statement.step_expression.value == 0:
            raise SemanticError(
                "range step cannot be zero",
                statement.step_expression.location,
            )
        self._require_type(
            statement.variable_type,
            ast.TypeName.TRYTE,
            statement.location,
            "for loop variable type",
        )
        self.scopes.append({})
        current_scope = self.scopes[-1]
        current_scope[statement.variable_name] = Binding(
            statement.variable_type,
            mutable=False,
            parameter=False,
            location=statement.location,
        )
        self.loop_depth += 1
        try:
            self._analyze_block(statement.body, create_scope=False)
        finally:
            self.loop_depth -= 1
            self.scopes.pop()
        return BlockFlow(definitely_returns=False, terminates=False)

    def _analyze_while(self, statement: ast.WhileStatement) -> BlockFlow:
        condition_type = self._analyze_expression(
            statement.condition,
            ast.TypeName.TRIT,
        )
        self._require_type(
            condition_type,
            ast.TypeName.TRIT,
            statement.condition.location,
            "while condition",
        )
        self.loop_depth += 1
        try:
            self._analyze_block(statement.body, create_scope=True)
        finally:
            self.loop_depth -= 1
        return BlockFlow(terminates=False, definitely_returns=False)

    def _analyze_switch(self, statement: ast.SwitchStatement) -> BlockFlow:
        selector_known = self._known_expression_type(statement.expression)
        if isinstance(selector_known, ast.NominalType) and self._is_enum_type(
            selector_known,
        ):
            selector_type = self._analyze_expression(
                statement.expression,
                selector_known,
            )
            assert isinstance(selector_type, ast.NominalType)
            return self._analyze_enum_switch(statement, selector_type)

        selector_type = self._analyze_expression(statement.expression, ast.TypeName.TRIT)
        self._require_type(
            selector_type,
            ast.TypeName.TRIT,
            statement.expression.location,
            "switch expression",
        )
        explicit_cases: dict[int, ast.TernaryCase] = {}
        fallback_case: ast.TernaryCase | None = None
        for i, case in enumerate(statement.cases):
            if case.label is None:
                if fallback_case is not None:
                    raise SemanticError(
                        "duplicate fallback arm in match statement",
                        case.location,
                    )
                if i != len(statement.cases) - 1:
                    raise SemanticError(
                        "fallback arm must be the last arm in match statement",
                        case.location,
                    )
                fallback_case = case
            else:
                if fallback_case is not None:
                    raise SemanticError(
                        "explicit case arm after fallback arm in match statement",
                        case.location,
                    )
                if case.label not in {-1, 0, 1}:
                    raise SemanticError(
                        f"invalid ternary case {case.label}; expected -1, 0, or 1",
                        case.location,
                    )
                if case.label in explicit_cases:
                    raise SemanticError(
                        f"duplicate ternary case {case.label}",
                        case.location,
                    )
                explicit_cases[case.label] = case

        if fallback_case is not None and len(explicit_cases) == 3:
            raise SemanticError(
                "redundant fallback arm in match statement",
                fallback_case.location,
            )

        cases_by_label: dict[int, ast.TernaryCase] = {}
        for label in (-1, 0, 1):
            if label in explicit_cases:
                cases_by_label[label] = explicit_cases[label]
            elif fallback_case is not None:
                cases_by_label[label] = fallback_case
            else:
                missing = sorted({-1, 0, 1} - explicit_cases.keys())
                rendered = ", ".join(str(lbl) for lbl in missing)
                raise SemanticError(
                    f"ternary switch is missing case(s): {rendered}",
                    statement.location,
                )

        case_flows = [
            self._analyze_block(cases_by_label[label].body, create_scope=True)
            for label in (-1, 0, 1)
        ]
        return BlockFlow(
            terminates=all(flow.terminates for flow in case_flows),
            definitely_returns=all(flow.definitely_returns for flow in case_flows),
        )

    def _analyze_enum_switch(
        self,
        statement: ast.SwitchStatement,
        selector_type: ast.NominalType,
    ) -> BlockFlow:
        enum = self.enums[selector_type.name]
        explicit_cases: dict[int, ast.TernaryCase] = {}
        fallback_case: ast.TernaryCase | None = None
        for i, case in enumerate(statement.cases):
            if case.label is None:
                if fallback_case is not None:
                    raise SemanticError(
                        "duplicate fallback arm in enum match statement",
                        case.location,
                    )
                if i != len(statement.cases) - 1:
                    raise SemanticError(
                        "fallback arm must be the last arm in enum match statement",
                        case.location,
                    )
                fallback_case = case
                continue
            discriminant = self._enum_case_discriminant(
                case.label,
                selector_type,
                case.location,
                "enum match statement",
            )
            if discriminant in explicit_cases:
                raise SemanticError(
                    f"duplicate enum match arm for discriminant {discriminant}",
                    case.location,
                    diagnostic_code=DiagnosticCode.MATCH_DUPLICATE_ARM,
                )
            explicit_cases[discriminant] = case

        if fallback_case is not None and len(explicit_cases) == len(enum.variants):
            raise SemanticError(
                "redundant fallback arm in enum match statement",
                fallback_case.location,
            )

        cases_by_label: dict[int, ast.TernaryCase] = {}
        missing: list[str] = []
        for variant in enum.variants:
            discriminant = enum.discriminant(variant.name)
            if discriminant in explicit_cases:
                cases_by_label[discriminant] = explicit_cases[discriminant]
            elif fallback_case is not None:
                cases_by_label[discriminant] = fallback_case
            else:
                missing.append(f"{enum.name}.{variant.name}")
        if missing:
            raise SemanticError(
                "enum match statement is missing case(s): " + ", ".join(missing),
                statement.location,
                diagnostic_code=DiagnosticCode.MATCH_NON_EXHAUSTIVE,
            )

        case_flows = [
            self._analyze_enum_match_case_block(
                cases_by_label[enum.discriminant(variant.name)],
                variant,
            )
            for variant in enum.variants
        ]
        return BlockFlow(
            terminates=all(flow.terminates for flow in case_flows),
            definitely_returns=all(flow.definitely_returns for flow in case_flows),
        )

    def _enum_case_discriminant(
        self,
        label: ast.MatchCaseLabel,
        selector_type: ast.NominalType,
        location: SourceLocation,
        context: str,
    ) -> int:
        if isinstance(label, int):
            raise SemanticError(
                f"{context} requires enum variant labels",
                location,
                diagnostic_code=DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
            )
        variant_label = label.variant if isinstance(label, ast.MatchPayloadLabel) else label
        assert isinstance(variant_label, ast.FieldAccessExpression)
        label_type = self._analyze_expression(variant_label, selector_type)
        self._require_type(
            label_type,
            selector_type,
            variant_label.location,
            f"{context} label",
        )
        discriminant = self.constant_values.get(id(variant_label))
        assert discriminant is not None
        enum = self.enums[selector_type.name]
        variant = enum.variants[discriminant]
        self._validate_match_payload_label(label, enum, variant, context)
        return discriminant

    def _validate_match_payload_label(
        self,
        label: ast.MatchCaseLabel,
        enum: EnumType,
        variant: ast.EnumVariant,
        context: str,
    ) -> None:
        expected = tuple(field.name for field in variant.payload_fields)
        if not expected:
            if isinstance(label, ast.MatchPayloadLabel):
                raise SemanticError(
                    f"{context} variant '{enum.name}.{variant.name}' has no payload bindings",
                    label.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
                )
            return
        if not isinstance(label, ast.MatchPayloadLabel):
            raise SemanticError(
                (
                    f"{context} variant '{enum.name}.{variant.name}' requires "
                    "payload binding(s): " + ", ".join(expected)
                ),
                variant.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
            )
        seen: set[str] = set()
        for binding in label.bindings:
            if binding in seen:
                raise SemanticError(
                    f"duplicate payload binding '{binding}'",
                    label.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_DUPLICATE,
                )
            seen.add(binding)
        if label.bindings != expected:
            raise SemanticError(
                (
                    f"{context} payload bindings for {enum.name}.{variant.name} "
                    "must be: " + ", ".join(expected)
                ),
                label.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
            )

    def _analyze_enum_match_case_block(
        self,
        case: ast.TernaryCase,
        variant: ast.EnumVariant,
    ) -> BlockFlow:
        self.scopes.append({})
        try:
            self._bind_match_payload(case.label, variant)
            return self._analyze_block(case.body, create_scope=False)
        finally:
            self.scopes.pop()

    def _analyze_enum_match_case_expression(
        self,
        case: ast.MatchExpressionCase,
        variant: ast.EnumVariant,
        expected: ast.DeclaredType | None,
    ) -> ast.DeclaredType:
        self.scopes.append({})
        try:
            self._bind_match_payload(case.label, variant)
            return self._analyze_expression(case.expression, expected)
        finally:
            self.scopes.pop()

    def _bind_match_payload(
        self,
        label: ast.MatchCaseLabel,
        variant: ast.EnumVariant,
    ) -> None:
        if not isinstance(label, ast.MatchPayloadLabel):
            return
        fields_by_name = {field.name: field for field in variant.payload_fields}
        current_scope = self.scopes[-1]
        for binding in label.bindings:
            field = fields_by_name[binding]
            current_scope[binding] = Binding(
                field.type_name,
                mutable=False,
                parameter=False,
                location=label.location,
            )

    def _analyze_declaration(self, declaration: ast.VariableDeclaration) -> None:
        current_scope = self.scopes[-1]
        if declaration.name in current_scope:
            if declaration.name in self.parameter_names and len(self.scopes) == 1:
                raise SemanticError(
                    f"local variable '{declaration.name}' conflicts with parameter "
                    f"'{declaration.name}'",
                    declaration.location,
                )
            raise SemanticError(
                f"duplicate declaration of variable '{declaration.name}'",
                declaration.location,
            )

        static_text: str | None = None
        constant_value: int | None = None
        reference_origin = None
        self._validate_declared_type(declaration.type_name)
        if isinstance(declaration.type_name, ast.ArrayType):
            self._validate_array_type(declaration.type_name)
            if isinstance(declaration.initializer, ast.ArrayLiteral):
                self._analyze_array_literal(
                    declaration.initializer,
                    declaration.type_name,
                )
            else:
                initializer_type = self._analyze_expression(
                    declaration.initializer,
                    declaration.type_name,
                )
                self._require_type(
                    initializer_type,
                    declaration.type_name,
                    declaration.initializer.location,
                    f"initializer for '{declaration.name}'",
                )
        else:
            if isinstance(declaration.initializer, ast.ArrayLiteral):
                raise SemanticError(
                    f"scalar '{declaration.name}' cannot use an array initializer",
                    declaration.initializer.location,
                )
            initializer_type = self._analyze_expression(
                declaration.initializer,
                declaration.type_name,
            )
            self._require_type(
                initializer_type,
                declaration.type_name,
                declaration.initializer.location,
                f"initializer for '{declaration.name}'",
            )
            if self._is_dynamic_type(declaration.type_name):
                self._consume_owner(declaration.initializer)
            if isinstance(declaration.type_name, ast.ReferenceType):
                reference_origin = self._reference_origin_of(declaration.initializer)
            if (
                declaration.type_name is ast.TypeName.STRING
                and not declaration.mutable
                and self._is_constant_static_text_expression(declaration.initializer)
            ):
                static_text = self._constant_static_text_value(
                    declaration.initializer,
                    "string initializer requires a compile-time static text expression",
                )
            elif (
                declaration.type_name in (ast.TypeName.TRIT, ast.TypeName.TRYTE)
                and not declaration.mutable
            ):
                constant_value = self.constant_values.get(id(declaration.initializer))
        current_scope[declaration.name] = Binding(
            declaration.type_name,
            declaration.mutable,
            parameter=False,
            location=declaration.location,
            static_text=static_text,
            constant_value=constant_value,
            scope_depth=len(self.scopes) - 1,
            reference_origin=reference_origin,
        )

    def _reference_origin_of(
        self,
        expression: ast.Expression | ast.ArrayLiteral,
    ) -> tuple[int, int, bool] | None:
        if isinstance(expression, ast.AddressOfExpression):
            if isinstance(expression.operand, ast.Identifier):
                binding = self._lookup_binding(expression.operand.name)
                if binding is not None:
                    return (
                        id(binding),
                        binding.scope_depth,
                        expression.mutable,
                    )
            return None
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_binding(expression.name)
            return None if binding is None else binding.reference_origin
        if isinstance(expression, ast.DereferenceExpression):
            return None
        return None

    def _replace_binding_reference_origin(
        self,
        name: str,
        binding: Binding,
        origin: tuple[int, int, bool] | None,
    ) -> None:
        for scope in reversed(self.scopes):
            if scope.get(name) is binding:
                scope[name] = Binding(
                    binding.type_name,
                    binding.mutable,
                    binding.parameter,
                    binding.location,
                    binding.static_text,
                    binding.constant_value,
                    binding.scope_depth,
                    origin,
                )
                return

    @staticmethod
    def _is_dynamic_type(type_name: ast.DeclaredType) -> bool:
        return type_name in (ast.TypeName.BYTES, ast.TypeName.TEXT)

    def _consume_owner(self, expression: ast.Expression) -> None:
        if not isinstance(expression, ast.Identifier):
            return
        binding = self._lookup_binding(expression.name)
        if binding is None or not self._is_dynamic_type(binding.type_name):
            return
        if id(binding) in self.moved_bindings:
            raise SemanticError(
                f"use of moved dynamic binding '{expression.name}'",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_USE_AFTER_MOVE,
            )
        if id(binding) in self.active_borrows:
            raise SemanticError(
                f"cannot move dynamic binding '{expression.name}' while borrowed",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_BORROWED_OWNER,
            )
        self.moved_bindings.add(id(binding))

    def _validate_declared_type(
        self,
        type_name: ast.DeclaredType,
        *,
        return_type: bool = False,
        aggregate: bool = False,
    ) -> None:
        if isinstance(type_name, ast.TypeName) and type_name in {
            ast.TypeName.BYTES,
            ast.TypeName.TEXT,
        }:
            self.contains_dynamic = True
            if aggregate:
                raise SemanticError(
                    "dynamic buffers cannot be stored in records, arrays, or enums",
                    type_name.location if hasattr(type_name, "location") else _DYNAMIC_BUILTIN_LOCATION,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
            return
        if isinstance(type_name, ast.ReferenceType):
            if type_name.target in (ast.TypeName.BYTES, ast.TypeName.TEXT):
                self.contains_dynamic = True
            self.contains_references = True
            if isinstance(type_name.target, ast.ReferenceType):
                raise SemanticError(
                    "nested reference types are not supported",
                    type_name.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_NESTED,
                )
            if not isinstance(type_name.target, ast.TypeName):
                raise SemanticError(
                    "reference target must be a scalar type",
                    type_name.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_AGGREGATE,
                )
            if return_type:
                raise SemanticError(
                    "reference return types are not supported",
                    type_name.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_RETURN,
                )
            if aggregate:
                raise SemanticError(
                    "references cannot be stored in aggregate types",
                    type_name.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_AGGREGATE,
                )
            return
        if isinstance(type_name, ast.ArrayType):
            if isinstance(type_name.element_type, ast.ReferenceType):
                raise SemanticError(
                    "references cannot be stored in arrays",
                    type_name.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_AGGREGATE,
                )
        if (
            isinstance(type_name, ast.NominalType)
            and type_name.name not in self.records
            and type_name.name not in self.enums
        ):
            raise SemanticError(
                f"unknown type '{type_name.name}'",
                type_name.location,
            )

    def _validate_array_type(self, type_name: ast.ArrayType) -> None:
        if isinstance(type_name.element_type, ast.ArrayType):
            raise SemanticError(
                "nested arrays are not supported",
                type_name.location,
            )
        if type_name.element_type is ast.TypeName.STRING:
            raise SemanticError(
                "arrays of string are not supported in milestone 0.53",
                type_name.location,
            )
        if type_name.element_type in {ast.TypeName.BYTES, ast.TypeName.TEXT}:
            raise SemanticError(
                "dynamic text and buffer values cannot be stored in arrays",
                type_name.location,
            )
        if isinstance(type_name.element_type, ast.NominalType):
            raise SemanticError(
                "arrays of nominal types are not supported",
                type_name.location,
            )
        if type_name.length <= 0:
            raise SemanticError(
                f"array length must be positive, got {type_name.length}",
                type_name.location,
            )
        if type_name.length > TRYTE_MAX + 1:
            raise SemanticError(
                f"array length {type_name.length} exceeds tryte-indexed "
                f"maximum {TRYTE_MAX + 1}",
                type_name.location,
            )

    def _analyze_array_literal(
        self,
        literal: ast.ArrayLiteral,
        type_name: ast.ArrayType,
    ) -> None:
        assert isinstance(type_name.element_type, ast.TypeName)
        if len(literal.elements) != type_name.length:
            raise SemanticError(
                f"array initializer has {len(literal.elements)} element(s); "
                f"expected {type_name.length}",
                literal.location,
            )
        for index, element in enumerate(literal.elements):
            actual = self._analyze_expression(element, type_name.element_type)
            self._require_type(
                actual,
                type_name.element_type,
                element.location,
                f"array element {index}",
            )

    def _analyze_assignment(self, statement: ast.AssignmentStatement) -> None:
        if isinstance(statement.target, ast.DereferenceTarget):
            reference_type = self._analyze_expression(statement.target.reference)
            if not isinstance(reference_type, ast.ReferenceType):
                raise SemanticError(
                    "dereference assignment target must be a reference",
                    statement.target.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
                )
            if not reference_type.mutable:
                raise SemanticError(
                    "cannot write through a shared reference",
                    statement.target.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_SHARED_WRITE,
                )
            if isinstance(statement.value, ast.ArrayLiteral):
                raise SemanticError(
                    "dereference assignment requires a scalar expression",
                    statement.value.location,
                )
            actual = self._analyze_expression(statement.value, reference_type.target)
            self._require_type(actual, reference_type.target, statement.value.location, "dereference assignment")
            return
        if isinstance(statement.target, ast.VariableTarget):
            binding = self._assignment_binding(
                statement.target.name,
                statement.target.location,
            )
            if isinstance(binding.type_name, ast.ArrayType):
                self._require_mutable(binding, statement.target.location)
                if isinstance(statement.value, ast.ArrayLiteral):
                    self._analyze_array_literal(statement.value, binding.type_name)
                else:
                    actual = self._analyze_expression(
                        statement.value,
                        binding.type_name,
                    )
                    self._require_type(
                        actual,
                        binding.type_name,
                        statement.value.location,
                        "assigned array value",
                    )
                return
            self._require_mutable(binding, statement.target.location)
            if isinstance(statement.value, ast.ArrayLiteral):
                raise SemanticError(
                    "scalar assignment requires a scalar expression",
                    statement.value.location,
                )
            actual = self._analyze_expression(statement.value, binding.type_name)
            self._require_type(
                actual,
                binding.type_name,
                statement.value.location,
                "assigned value",
            )
            if isinstance(binding.type_name, ast.ReferenceType):
                origin = self._reference_origin_of(statement.value)
                if origin is not None and origin[1] > binding.scope_depth:
                    raise SemanticError(
                        "reference escapes its referent scope",
                        statement.value.location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_ESCAPE,
                    )
                self._replace_binding_reference_origin(statement.target.name, binding, origin)
            return

        binding = self._assignment_binding(
            statement.target.array_name,
            statement.target.location,
        )
        if not isinstance(binding.type_name, ast.ArrayType):
            if binding.type_name is ast.TypeName.STRING:
                raise SemanticError(
                    "string indexing is not supported",
                    statement.target.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            raise SemanticError(
                f"variable '{statement.target.array_name}' is not an array",
                statement.target.location,
            )
        self._require_mutable(binding, statement.target.location)
        self._analyze_index(
            statement.target.array_name,
            statement.target.index,
            binding.type_name,
        )
        if isinstance(statement.value, ast.ArrayLiteral):
            raise SemanticError(
                "array element assignment requires a scalar expression",
                statement.value.location,
            )
        assert isinstance(binding.type_name.element_type, ast.TypeName)
        actual = self._analyze_expression(
            statement.value,
            binding.type_name.element_type,
        )
        self._require_type(
            actual,
            binding.type_name.element_type,
            statement.value.location,
            "array element assignment",
        )

    def _analyze_compound_assignment(
        self,
        statement: ast.CompoundAssignmentStatement,
    ) -> BlockFlow:
        if isinstance(statement.target, ast.VariableTarget):
            binding = self._assignment_binding(
                statement.target.name,
                statement.target.location,
            )
            if isinstance(binding.type_name, ast.ArrayType):
                raise SemanticError(
                    "whole-array assignment is not supported",
                    statement.target.location,
                )
            self._require_mutable(binding, statement.target.location)
            if isinstance(statement.value, ast.ArrayLiteral):
                raise SemanticError(
                    "scalar assignment requires a scalar expression",
                    statement.value.location,
                )
            assert isinstance(binding.type_name, ast.TypeName)
            self._reject_string_operation(
                binding.type_name,
                statement.location,
                "compound assignment is not supported for string values",
            )
            actual = self._analyze_expression(statement.value, binding.type_name)
            self._require_type(
                actual,
                binding.type_name,
                statement.value.location,
                "assigned value",
            )
            return BlockFlow(definitely_returns=False, terminates=False)

        binding = self._assignment_binding(
            statement.target.array_name,
            statement.target.location,
        )
        if not isinstance(binding.type_name, ast.ArrayType):
            if binding.type_name is ast.TypeName.STRING:
                raise SemanticError(
                    "string indexing is not supported",
                    statement.target.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            raise SemanticError(
                f"variable '{statement.target.array_name}' is not an array",
                statement.target.location,
            )
        self._require_mutable(binding, statement.target.location)
        self._analyze_index(
            statement.target.array_name,
            statement.target.index,
            binding.type_name,
        )
        if isinstance(statement.value, ast.ArrayLiteral):
            raise SemanticError(
                "array element assignment requires a scalar expression",
                statement.value.location,
            )
        assert isinstance(binding.type_name.element_type, ast.TypeName)
        actual = self._analyze_expression(
            statement.value,
            binding.type_name.element_type,
        )
        self._require_type(
            actual,
            binding.type_name.element_type,
            statement.value.location,
            "array element assignment",
        )
        return BlockFlow(definitely_returns=False, terminates=False)

    def _assignment_binding(self, name: str, location: SourceLocation) -> Binding:
        binding = self._lookup_binding(name)
        if binding is not None:
            return binding
        if name in self.functions:
            raise SemanticError(
                f"function '{name}' cannot be an assignment target",
                location,
            )
        raise SemanticError(f"undeclared variable '{name}'", location)

    @staticmethod
    def _require_mutable(binding: Binding, location: SourceLocation) -> None:
        if binding.parameter:
            raise SemanticError("cannot assign to a parameter", location)
        if not binding.mutable:
            raise SemanticError("cannot assign to immutable variable", location)

    def _analyze_expression(
        self,
        expression: ast.Expression,
        expected: ast.DeclaredType | None = None,
    ) -> ast.DeclaredType:
        if isinstance(expression, ast.IntegerLiteral):
            result = (
                expected
                if expected in (ast.TypeName.TRIT, ast.TypeName.TRYTE, ast.TypeName.I64)
                else ast.TypeName.TRYTE
            )
            self._validate_literal(expression, result)
            self.constant_values[id(expression)] = expression.value
        elif isinstance(expression, ast.FloatLiteral):
            result = ast.TypeName.F64
            self._validate_float_literal(expression)
            self.constant_values[id(expression)] = expression.value
            if expected is not None:
                self._require_type(result, expected, expression.location, "float literal")
        elif isinstance(expression, ast.StringLiteral):
            self._validate_static_string_literal(expression)
            self.static_text_values[id(expression)] = decode_static_text(
                expression.value
            )
            result = ast.TypeName.STRING
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    "string literal",
                )
        elif isinstance(expression, ast.Identifier):
            result = self._identifier_type(
                expression,
                allow_array=isinstance(expected, ast.ArrayType),
            )
            binding = self._lookup_binding(expression.name)
            if binding is not None and self._is_dynamic_type(binding.type_name) and id(binding) in self.moved_bindings:
                raise SemanticError(
                    f"use of moved dynamic binding '{expression.name}'",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_USE_AFTER_MOVE,
                )
            if binding is not None and binding.static_text is not None:
                self.static_text_values[id(expression)] = binding.static_text
            if binding is not None and binding.constant_value is not None:
                self.constant_values[id(expression)] = binding.constant_value
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"variable '{expression.name}'",
                )
            binding = self._lookup_binding(expression.name)
            if binding is not None:
                self.place_info[id(expression)] = PlaceInfo(
                    result,
                    True,
                    binding.mutable and not binding.parameter,
                    True,
                    expression.name,
                    binding.scope_depth,
                    True,
                )
                if binding.reference_origin is not None:
                    self.reference_origins[id(expression)] = binding.reference_origin
        elif isinstance(expression, ast.IndexExpression):
            array_binding = self._index_expression_array_binding(expression)
            if array_binding is not None:
                self.expression_types[id(expression.target)] = array_binding.type_name
                result = self._analyze_index(
                    expression.array_name,
                    expression.index,
                    array_binding.type_name,
                )
                self.place_info[id(expression)] = PlaceInfo(
                    result,
                    True,
                    array_binding.mutable and not array_binding.parameter,
                    True,
                    expression.array_name,
                    array_binding.scope_depth,
                    True,
                )
            else:
                target_type = self._known_expression_type(expression.target)
                if target_type is ast.TypeName.STRING:
                    text = self._constant_static_text_value(
                        expression,
                        "string indexing requires a compile-time static text expression",
                    )
                    self.static_text_values[id(expression)] = text
                    result = ast.TypeName.STRING
                elif isinstance(expression.target, ast.Identifier):
                    raise SemanticError(
                        f"variable '{expression.target.name}' is not an array",
                        expression.location,
                    )
                else:
                    result = self._analyze_expression(expression.target)
                    if isinstance(result, ast.ArrayType):
                        result = self._analyze_index(
                            "array value",
                            expression.index,
                            result,
                        )
                    else:
                        raise SemanticError(
                            "indexed target has type "
                            f"{_type_display(result)}; expected array or "
                            "compile-time static text",
                            expression.target.location,
                        )
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    "index expression",
                )
        elif isinstance(expression, ast.SliceExpression):
            if isinstance(expression.target, ast.Identifier):
                binding = self._lookup_binding(expression.target.name)
                if binding is not None and isinstance(binding.type_name, ast.ArrayType):
                    raise SemanticError(
                        "array slicing is not supported",
                        expression.location,
                    )
            text = self._constant_static_text_value(
                expression,
                "static text slicing requires a compile-time static text expression",
            )
            self.static_text_values[id(expression)] = text
            result = ast.TypeName.STRING
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    "slice expression",
                )
        elif isinstance(expression, ast.CallExpression):
            result = self._analyze_call(expression)
            if expected is not None:
                call_context = "call expression"
                if expression.simple_function_name is not None:
                    call_context = f"call to '{expression.function_name}'"
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    call_context,
                )
        elif isinstance(expression, ast.RecordExpression):
            result = self._analyze_record_or_enum_expression(expression)
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"nominal literal '{expression.type_name}'",
                )
        elif isinstance(expression, ast.FieldAccessExpression):
            result = self._analyze_field_access(expression)
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"field '{expression.field_name}'",
                )
        elif isinstance(expression, ast.AddressOfExpression):
            result = self._analyze_address_of(expression)
            if expected is not None:
                self._require_type(result, expected, expression.location, "address-of expression")
        elif isinstance(expression, ast.DereferenceExpression):
            result = self._analyze_dereference(expression)
            if expected is not None:
                self._require_type(result, expected, expression.location, "dereference expression")
        elif isinstance(expression, ast.UnaryExpression):
            result = self._analyze_expression(expression.operand, expected)
            self._reject_string_operation(
                result,
                expression.location,
                f"operator '{expression.operator.value}' is not supported for string values",
            )
            self._fold_unary_constant(expression, result)
            self._simplify_unary_expression(expression)
        elif isinstance(expression, ast.BinaryExpression):
            result = self._analyze_binary(expression, expected)
        elif isinstance(expression, ast.MatchExpression):
            result = self._analyze_match_expression(expression, expected)
        elif isinstance(expression, ast.LenExpression):
            result = self._analyze_len(expression, expected)
        else:
            raise SemanticError("unsupported expression", expression.location)
        self.expression_types[id(expression)] = result
        return result

    def _analyze_address_of(self, expression: ast.AddressOfExpression) -> ast.ReferenceType:
        if isinstance(expression.operand, ast.DereferenceExpression):
            reference_type = self._analyze_expression(expression.operand.operand)
            if not isinstance(reference_type, ast.ReferenceType):
                raise SemanticError(
                    "reborrow operand must be a reference",
                    expression.operand.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
                )
            if expression.mutable and not reference_type.mutable:
                raise SemanticError(
                    "mutable reborrow requires a mutable reference",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
                )
            self._analyze_dereference(expression.operand)
            self.reference_origins[id(expression)] = self.reference_origins.get(
                id(expression.operand.operand),
                (id(expression.operand.operand), len(self.scopes) - 1, expression.mutable),
            )
            prior = self.reference_provenance.get(id(expression.operand.operand))
            if prior is not None:
                self.reference_provenance[id(expression)] = ReferenceProvenance(
                    prior.root_storage,
                    prior.projection,
                    prior.target_type,
                    expression.mutable,
                )
            self.contains_references = True
            return ast.ReferenceType(reference_type.target, expression.mutable, expression.location)
        if isinstance(expression.operand, ast.IndexExpression):
            target_type = self._analyze_expression(expression.operand)
            place = self.place_info.get(id(expression.operand))
            if place is None or not place.addressable:
                raise SemanticError(
                    "array element is not addressable",
                    expression.operand.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
                )
            if expression.mutable and not place.writable:
                raise SemanticError(
                    "mutable reference target is not writable",
                    expression.operand.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
                )
            assert isinstance(target_type, ast.TypeName)
            index_value = self._constant_integer(expression.operand.index)
            self.reference_provenance[id(expression)] = ReferenceProvenance(
                expression.operand.target.name
                if isinstance(expression.operand.target, ast.Identifier)
                else "array",
                ("element", index_value),
                target_type,
                expression.mutable,
            )
            self.contains_references = True
            return ast.ReferenceType(target_type, expression.mutable, expression.location)
        if isinstance(expression.operand, ast.FieldAccessExpression):
            target_type = self._analyze_expression(expression.operand)
            place = self.place_info.get(id(expression.operand))
            if place is None or not place.addressable:
                raise SemanticError(
                    "record field is not addressable",
                    expression.operand.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
                )
            if expression.mutable and not place.writable:
                raise SemanticError(
                    "mutable reference target is not writable",
                    expression.operand.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
                )
            assert isinstance(target_type, ast.TypeName)
            root = (
                expression.operand.target.name
                if isinstance(expression.operand.target, ast.Identifier)
                else "record"
            )
            self.reference_provenance[id(expression)] = ReferenceProvenance(
                root,
                ("field", expression.operand.field_name),
                target_type,
                expression.mutable,
            )
            self.contains_references = True
            return ast.ReferenceType(target_type, expression.mutable, expression.location)
        if not isinstance(expression.operand, ast.Identifier):
            raise SemanticError(
                "reference target is not addressable in V1",
                expression.operand.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
            )
        binding = self._lookup_binding(expression.operand.name)
        if binding is None:
            raise SemanticError(
                f"undeclared variable '{expression.operand.name}'",
                expression.operand.location,
            )
        if isinstance(binding.type_name, ast.ReferenceType):
            raise SemanticError(
                "reference-to-reference address-of is not supported",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_NESTED,
            )
        if expression.mutable and (not binding.mutable and not binding.parameter):
            raise SemanticError(
                "mutable reference target is not writable",
                expression.operand.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
            )
        if not isinstance(binding.type_name, ast.TypeName):
            raise SemanticError(
                "reference target must be a scalar local or parameter",
                expression.operand.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_AGGREGATE,
            )
        origin = (id(binding), binding.scope_depth, expression.mutable)
        self.reference_origins[id(expression)] = origin
        self.reference_provenance[id(expression)] = ReferenceProvenance(
            expression.operand.name,
            ("direct",),
            binding.type_name,
            expression.mutable,
        )
        self.contains_references = True
        if self._is_dynamic_type(binding.type_name):
            key = id(binding)
            shared, mutable = self.active_borrows.get(key, (0, False))
            if expression.mutable:
                if mutable or shared:
                    raise SemanticError(
                        "mutable dynamic buffer borrow overlaps an active borrow",
                        expression.location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_BORROW_CONFLICT,
                    )
                self.active_borrows[key] = (shared, True)
            else:
                if mutable:
                    raise SemanticError(
                        "shared dynamic buffer borrow overlaps a mutable borrow",
                        expression.location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_BORROW_CONFLICT,
                    )
                self.active_borrows[key] = (shared + 1, False)
        return ast.ReferenceType(binding.type_name, expression.mutable, expression.location)

    def _analyze_dereference(self, expression: ast.DereferenceExpression) -> ast.DeclaredType:
        reference_type = self._analyze_expression(expression.operand)
        if not isinstance(reference_type, ast.ReferenceType):
            raise SemanticError(
                "dereference operand must be a reference",
                expression.operand.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
            )
        origin = self.reference_origins.get(id(expression.operand))
        self.place_info[id(expression)] = PlaceInfo(
            reference_type.target,
            True,
            reference_type.mutable,
            False,
            None,
            origin[1] if origin else len(self.scopes) - 1,
            True,
        )
        self.contains_references = True
        return reference_type.target

    def _analyze_record_or_enum_expression(
        self,
        expression: ast.RecordExpression,
    ) -> ast.NominalType:
        enum_access = self._enum_constructor(expression)
        if enum_access is not None:
            enum, variant = enum_access
            fields_by_name = {field.name: field for field in variant.payload_fields}
            seen: set[str] = set()
            for value in expression.fields:
                if value.name in seen:
                    raise SemanticError(
                        f"duplicate payload field '{value.name}' in enum literal",
                        value.location,
                        diagnostic_code=DiagnosticCode.RECORD_FIELD_DUPLICATE,
                    )
                seen.add(value.name)
                field = fields_by_name.get(value.name)
                if field is None:
                    raise SemanticError(
                        (
                            f"enum variant '{enum.name}.{variant.name}' has no "
                            f"payload field '{value.name}'"
                        ),
                        value.location,
                        diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
                    )
                actual = self._analyze_expression(value.expression, field.type_name)
                self._require_type(
                    actual,
                    field.type_name,
                    value.location,
                    f"payload field '{value.name}'",
                )
            missing = [
                field.name
                for field in variant.payload_fields
                if field.name not in seen
            ]
            if missing:
                raise SemanticError(
                    (
                        f"enum variant '{enum.name}.{variant.name}' literal is "
                        "missing payload field(s): " + ", ".join(missing)
                    ),
                    expression.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_MISSING,
                )
            return ast.NominalType(enum.name, expression.location)

        record = self.records.get(expression.type_name)
        if record is None:
            raise SemanticError(
                f"unknown record type '{expression.type_name}'",
                expression.location,
            )
        fields_by_name = {field.name: field for field in record.fields}
        seen: set[str] = set()
        for value in expression.fields:
            if value.name in seen:
                raise SemanticError(
                    f"duplicate field '{value.name}' in record literal",
                    value.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_DUPLICATE,
                )
            seen.add(value.name)
            field = fields_by_name.get(value.name)
            if field is None:
                raise SemanticError(
                    f"record '{record.name}' has no field '{value.name}'",
                    value.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
                )
            actual = self._analyze_expression(value.expression, field.type_name)
            self._require_type(
                actual,
                field.type_name,
                value.location,
                f"field '{value.name}'",
            )
        missing = [field.name for field in record.fields if field.name not in seen]
        if missing:
            raise SemanticError(
                (
                    f"record '{record.name}' literal is missing field(s): "
                    + ", ".join(missing)
                ),
                expression.location,
                diagnostic_code=DiagnosticCode.RECORD_FIELD_MISSING,
            )
        return ast.NominalType(record.name, expression.location)

    def _enum_constructor(
        self,
        expression: ast.RecordExpression,
    ) -> tuple[EnumType, ast.EnumVariant] | None:
        if "." not in expression.type_name:
            return None
        enum_name, variant_name = expression.type_name.rsplit(".", 1)
        enum = self.enums.get(enum_name)
        if enum is None:
            return None
        variant = enum.variant(variant_name)
        if variant is None:
            raise SemanticError(
                f"enum '{enum.name}' has no variant '{variant_name}'",
                expression.location,
                diagnostic_code=DiagnosticCode.ENUM_VARIANT_UNKNOWN,
            )
        return enum, variant

    def _analyze_field_access(
        self,
        expression: ast.FieldAccessExpression,
    ) -> ast.DeclaredType:
        enum_access = self._enum_variant_access(expression)
        if enum_access is not None:
            enum, variant = enum_access
            self.constant_values[id(expression)] = enum.discriminant(variant.name)
            return ast.NominalType(enum.name, expression.location)

        if isinstance(expression.target, ast.Identifier):
            binding = self._lookup_binding(expression.target.name)
            if binding is None:
                if expression.target.name in self.records:
                    raise SemanticError(
                        f"type '{expression.target.name}' cannot be used as a value",
                        expression.location,
                    )
                if expression.target.name in self.functions:
                    raise SemanticError(
                        f"function '{expression.target.name}' cannot be used as a value",
                        expression.location,
                    )
            elif isinstance(binding.type_name, ast.ArrayType):
                raise SemanticError(
                    "field access requires a record value",
                    expression.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
                )

        target_type = self._analyze_expression(expression.target)
        if not isinstance(target_type, ast.NominalType):
            raise SemanticError(
                "field access requires a record value",
                expression.location,
                diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
            )
        record = self.records.get(target_type.name)
        if record is None:
            if target_type.name in self.enums:
                raise SemanticError(
                    "field access requires a record value",
                    expression.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
                )
            raise SemanticError(
                f"unknown record type '{target_type.name}'",
                expression.location,
            )
        field = record.field(expression.field_name)
        if field is None:
            raise SemanticError(
                f"record '{record.name}' has no field '{expression.field_name}'",
                expression.location,
                diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
            )
        if isinstance(expression.target, ast.Identifier):
            binding = self._lookup_binding(expression.target.name)
            if binding is not None:
                self.place_info[id(expression)] = PlaceInfo(
                    field.type_name,
                    True,
                    binding.mutable and not binding.parameter,
                    True,
                    f"{expression.target.name}.{expression.field_name}",
                    binding.scope_depth,
                    True,
                )
        return field.type_name

    def _enum_variant_access(
        self,
        expression: ast.FieldAccessExpression,
    ) -> tuple[EnumType, ast.EnumVariant] | None:
        if not isinstance(expression.target, ast.Identifier):
            return None
        if self._lookup_binding(expression.target.name) is not None:
            return None
        enum = self.enums.get(expression.target.name)
        if enum is None:
            return None
        variant = enum.variant(expression.field_name)
        if variant is None:
            raise SemanticError(
                f"enum '{enum.name}' has no variant '{expression.field_name}'",
                expression.location,
                diagnostic_code=DiagnosticCode.ENUM_VARIANT_UNKNOWN,
            )
        return enum, variant

    def _index_expression_array_binding(
        self,
        expression: ast.IndexExpression,
    ) -> Binding | None:
        if not isinstance(expression.target, ast.Identifier):
            return None
        binding = self._lookup_binding(expression.target.name)
        if binding is None:
            raise SemanticError(
                f"undeclared variable '{expression.target.name}'",
                expression.location,
            )
        if isinstance(binding.type_name, ast.ArrayType):
            return binding
        return None

    def _analyze_len(
        self,
        expression: ast.LenExpression,
        expected: ast.TypeName | None = None,
    ) -> ast.TypeName:
        array_length: int | None = None
        if self._is_constant_static_text_expression(expression.argument):
            length = self._constant_static_text_length(expression.argument)
            if length > TRYTE_MAX:
                raise SemanticError(
                    f"static text length {length} exceeds tryte maximum {TRYTE_MAX}",
                    expression.argument.location,
                )
            result = ast.TypeName.TRYTE
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    "len expression",
                )
            self.constant_values[id(expression)] = length
            return result
        if isinstance(expression.argument, ast.Identifier):
            binding = self._lookup_binding(expression.argument.name)
            if binding is None:
                raise SemanticError(
                    f"undeclared variable '{expression.argument.name}'",
                    expression.argument.location,
                )
            if not isinstance(binding.type_name, ast.ArrayType):
                if binding.type_name is ast.TypeName.STRING:
                    raise SemanticError(
                        "len() argument must be a static array or a compile-time static text expression",
                        expression.argument.location,
                        diagnostic_code=(
                            DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                        ),
                    )
                raise SemanticError(
                    "len() argument must be a static array or a compile-time static text expression, "
                    f"got '{_type_display(binding.type_name)}'",
                    expression.argument.location,
                )
            self.expression_types[id(expression.argument)] = binding.type_name
            array_length = binding.type_name.length
        elif isinstance(expression.argument, ast.IndexExpression):
            raise SemanticError(
                "len() argument must be a static array or a compile-time static text expression, not an array element",
                expression.argument.location,
            )
        else:
            known_type = self._known_expression_type(expression.argument)
            if known_type is ast.TypeName.STRING:
                raise SemanticError(
                    "len() argument must be a static array or a compile-time static text expression",
                    expression.argument.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            raise SemanticError(
                "len() argument must be a static array or a compile-time static text expression",
                expression.argument.location,
            )
        result = ast.TypeName.TRYTE
        if expected is not None:
            self._require_type(
                result,
                expected,
                expression.location,
                "len expression",
            )
        assert array_length is not None
        self.constant_values[id(expression)] = array_length
        return result

    def _analyze_index(
        self,
        array_name: str,
        index: ast.Expression,
        type_name: ast.ArrayType,
    ) -> ast.TypeName:
        known_index_type = self._known_expression_type(index)
        expected_index_type = (
            ast.TypeName.I64
            if known_index_type is ast.TypeName.I64
            else ast.TypeName.TRYTE
        )
        index_type = self._analyze_expression(index, expected_index_type)
        if index_type not in {ast.TypeName.TRYTE, ast.TypeName.I64}:
            raise SemanticError(
                f"array index has type {_type_display(index_type)}; expected tryte or i64",
                index.location,
            )
        constant = self._constant_integer(index)
        if constant is not None and not 0 <= constant < type_name.length:
            raise SemanticError(
                f"constant index {constant} is outside array '{array_name}' "
                f"bounds [0, {type_name.length})",
                index.location,
            )
        assert isinstance(type_name.element_type, ast.TypeName)
        return type_name.element_type

    def _analyze_call(self, expression: ast.CallExpression) -> ast.DeclaredType:
        if expression.simple_function_name is None:
            raise SemanticError(
                "call target must be an unqualified function name",
                expression.location,
            )
        if self._lookup_binding(expression.function_name) is not None:
            raise SemanticError(
                f"variable '{expression.function_name}' cannot be called",
                expression.location,
            )
        if expression.function_name in STATIC_TEXT_QUERY_BUILTINS:
            return self._analyze_static_text_query_call(expression)
        if expression.function_name in _DYNAMIC_BUILTINS:
            borrow_snapshot = dict(self.active_borrows)
            signature = self.functions[expression.function_name]
            if len(expression.arguments) != len(signature.parameter_types):
                raise SemanticError(
                    f"builtin '{expression.function_name}' expects {len(signature.parameter_types)} argument(s), got {len(expression.arguments)}",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            for index, (argument, parameter_type) in enumerate(
                zip(expression.arguments, signature.parameter_types, strict=True),
                start=1,
            ):
                actual = self._analyze_expression(argument.expression, parameter_type)
                self._require_type(
                    actual,
                    parameter_type,
                    argument.location,
                    f"argument {index} to '{expression.function_name}'",
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            self.active_borrows = borrow_snapshot
            self.contains_dynamic = True
            return signature.return_type
        if expression.function_name in STATIC_TEXT_TRANSFORM_BUILTINS:
            if expression.function_name not in self.functions or self._is_constant_static_text_transform_call(expression):
                return self._analyze_static_text_transform_call(expression)
        signature = self.functions.get(expression.function_name)
        if signature is None:
            raise SemanticError(
                f"unknown function '{expression.function_name}'",
                expression.location,
            )
        if len(expression.arguments) != len(signature.parameter_types):
            raise SemanticError(
                f"function '{expression.function_name}' expects "
                f"{len(signature.parameter_types)} argument(s), got "
                f"{len(expression.arguments)}",
                expression.location,
            )
        for index, (argument, parameter_type) in enumerate(
            zip(expression.arguments, signature.parameter_types, strict=True),
            start=1,
        ):
            actual = self._analyze_expression(argument.expression, parameter_type)
            self._require_type(
                actual,
                parameter_type,
                argument.location,
                f"argument {index} to '{expression.function_name}'",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
            if isinstance(parameter_type, ast.TypeName) and parameter_type in {
                ast.TypeName.BYTES,
                ast.TypeName.TEXT,
            }:
                self._consume_owner(argument.expression)
        return signature.return_type

    def _analyze_static_text_query_call(
        self,
        expression: ast.CallExpression,
    ) -> ast.TypeName:
        if len(expression.arguments) != 2:
            raise SemanticError(
                f"builtin '{expression.function_name}' expects 2 argument(s), got "
                f"{len(expression.arguments)}",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
        left = self._constant_static_text_value(
            expression.arguments[0].expression,
            f"builtin '{expression.function_name}' requires compile-time static text arguments",
        )
        right = self._constant_static_text_value(
            expression.arguments[1].expression,
            f"builtin '{expression.function_name}' requires compile-time static text arguments",
        )
        if expression.function_name == "contains":
            value = -1 if right in left else 0
        elif expression.function_name == "starts_with":
            value = -1 if left.startswith(right) else 0
        elif expression.function_name == "ends_with":
            value = -1 if left.endswith(right) else 0
        elif expression.function_name == "find":
            value = left.find(right)
            if not TRYTE_MIN <= value <= TRYTE_MAX:
                raise SemanticError(
                    f"find result {value} is outside tryte range [{TRYTE_MIN}, {TRYTE_MAX}]",
                    expression.location,
                )
        else:
            raise SemanticError(
                f"unknown static text builtin '{expression.function_name}'",
                expression.location,
            )
        self.constant_values[id(expression)] = value
        result = STATIC_TEXT_QUERY_BUILTINS[expression.function_name]
        self.expression_types[id(expression)] = result
        return result

    def _is_constant_static_text_transform_call(
        self,
        expression: ast.CallExpression,
    ) -> bool:
        if expression.function_name not in STATIC_TEXT_TRANSFORM_BUILTINS:
            return False
        expected_count = STATIC_TEXT_TRANSFORM_BUILTINS[expression.function_name]
        if len(expression.arguments) != expected_count:
            return False
        if expression.function_name in ("upper", "lower", "trim"):
            return self._is_constant_static_text_expression(expression.arguments[0].expression)
        if expression.function_name == "repeat":
            return (
                self._is_constant_static_text_expression(expression.arguments[0].expression)
                and self._is_constant_tryte_expression(expression.arguments[1].expression)
            )
        if expression.function_name == "replace":
            return all(
                self._is_constant_static_text_expression(argument.expression)
                for argument in expression.arguments
            )
        return False

    def _analyze_static_text_transform_call(
        self,
        expression: ast.CallExpression,
    ) -> ast.TypeName:
        expected_count = STATIC_TEXT_TRANSFORM_BUILTINS[expression.function_name]
        if len(expression.arguments) != expected_count:
            raise SemanticError(
                f"builtin '{expression.function_name}' expects {expected_count} argument(s), got "
                f"{len(expression.arguments)}",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
        name = expression.function_name
        if name in ("upper", "lower", "trim"):
            text = self._constant_static_text_value(
                expression.arguments[0].expression,
                f"builtin '{name}' requires compile-time static text arguments",
            )
            if name == "upper":
                result_text = text.upper()
            elif name == "lower":
                result_text = text.lower()
            else:
                result_text = text.strip()
        elif name == "repeat":
            text = self._constant_static_text_value(
                expression.arguments[0].expression,
                "builtin 'repeat' requires compile-time static text and count arguments",
            )
            count_type = self._analyze_expression(
                expression.arguments[1].expression,
                ast.TypeName.TRYTE,
            )
            self._require_type(
                count_type,
                ast.TypeName.TRYTE,
                expression.arguments[1].expression.location,
                "repeat count argument",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
            count = self._constant_tryte_value(expression.arguments[1].expression)
            if count is None:
                raise SemanticError(
                    "builtin 'repeat' requires compile-time static text and count arguments",
                    expression.arguments[1].expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
                )
            if count < 0:
                raise SemanticError(
                    "repeat count must be non-negative",
                    expression.arguments[1].expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
                )
            result_text = text * count
        elif name == "replace":
            text = self._constant_static_text_value(
                expression.arguments[0].expression,
                "builtin 'replace' requires compile-time static text arguments",
            )
            old = self._constant_static_text_value(
                expression.arguments[1].expression,
                "builtin 'replace' requires compile-time static text arguments",
            )
            new = self._constant_static_text_value(
                expression.arguments[2].expression,
                "builtin 'replace' requires compile-time static text arguments",
            )
            result_text = text.replace(old, new)
        else:
            raise SemanticError(
                f"unknown static text transform builtin '{name}'",
                expression.location,
            )
        self.static_text_values[id(expression)] = result_text
        self.expression_types[id(expression)] = ast.TypeName.STRING
        return ast.TypeName.STRING

    def _analyze_binary(
        self,
        expression: ast.BinaryExpression,
        expected: ast.TypeName | None,
    ) -> ast.TypeName:
        left_known = self._known_expression_type(expression.left)
        right_known = self._known_expression_type(expression.right)
        if isinstance(left_known, ast.ReferenceType) or isinstance(
            right_known, ast.ReferenceType
        ):
            self._analyze_expression(expression.left, left_known)
            self._analyze_expression(expression.right, right_known)
            raise SemanticError(
                "reference arithmetic and identity comparison are not supported",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_REFERENCE_IDENTITY,
            )
        RELATIONAL_OPERATORS = {
            ast.BinaryOperator.COMPARE,
            ast.BinaryOperator.EQUAL,
            ast.BinaryOperator.NOT_EQUAL,
            ast.BinaryOperator.LESS,
            ast.BinaryOperator.LESS_EQUAL,
            ast.BinaryOperator.GREATER,
            ast.BinaryOperator.GREATER_EQUAL,
        }
        if expression.operator in RELATIONAL_OPERATORS:
            left_known = self._known_expression_type(expression.left)
            right_known = self._known_expression_type(expression.right)
            if isinstance(left_known, ast.NominalType) or isinstance(
                right_known,
                ast.NominalType,
            ):
                left_type = self._analyze_expression(expression.left, left_known)
                right_type = self._analyze_expression(expression.right, right_known)
                self._require_type(
                    left_type,
                    right_type,
                    expression.location,
                    "comparison operands",
                )
                if not self._is_enum_type(left_type):
                    raise SemanticError(
                        f"operator '{expression.operator.value}' is not supported for record values",
                        expression.location,
                    )
                if expression.operator not in (
                    ast.BinaryOperator.EQUAL,
                    ast.BinaryOperator.NOT_EQUAL,
                ):
                    raise SemanticError(
                        f"operator '{expression.operator.value}' is not supported for enum values",
                        expression.location,
                    )
                if expected is not None:
                    self._require_type(
                        ast.TypeName.TRIT,
                        expected,
                        expression.location,
                        "enum comparison result",
                    )
                self._fold_binary_constant(expression, ast.TypeName.TRIT)
                return ast.TypeName.TRIT
            if (
                left_known is ast.TypeName.STRING
                or right_known is ast.TypeName.STRING
            ):
                if (
                    self._is_constant_static_text_expression(expression.left)
                    and self._is_constant_static_text_expression(expression.right)
                ):
                    self._validate_constant_static_text_expression(expression.left)
                    self._validate_constant_static_text_expression(expression.right)
                    if expected is not None:
                        self._require_type(
                            ast.TypeName.TRIT,
                            expected,
                            expression.location,
                            "static text comparison result",
                        )
                    left_text = self._constant_static_text_value(
                        expression.left,
                        "string comparison requires compile-time static text expressions",
                    )
                    right_text = self._constant_static_text_value(
                        expression.right,
                        "string comparison requires compile-time static text expressions",
                    )
                    if expression.operator is ast.BinaryOperator.EQUAL:
                        res = left_text == right_text
                    elif expression.operator is ast.BinaryOperator.NOT_EQUAL:
                        res = left_text != right_text
                    elif expression.operator is ast.BinaryOperator.LESS:
                        res = left_text < right_text
                    elif expression.operator is ast.BinaryOperator.LESS_EQUAL:
                        res = left_text <= right_text
                    elif expression.operator is ast.BinaryOperator.GREATER:
                        res = left_text > right_text
                    elif expression.operator is ast.BinaryOperator.GREATER_EQUAL:
                        res = left_text >= right_text
                    else:
                        res = False
                    self.constant_values[id(expression)] = (
                        self._comparison_result(res)
                    )
                    self.expression_types[id(expression)] = ast.TypeName.TRIT
                    return ast.TypeName.TRIT
                if (
                    left_known is not None
                    and right_known is not None
                    and left_known is not right_known
                ):
                    left_type = self._analyze_expression(
                        expression.left,
                        left_known,
                    )
                    right_type = self._analyze_expression(
                        expression.right,
                        right_known,
                    )
                    self._require_type(
                        left_type,
                        right_type,
                        expression.location,
                        "comparison operands",
                    )
                self._analyze_expression(expression.left, left_known)
                self._analyze_expression(expression.right, right_known)
                if expression.operator in (
                    ast.BinaryOperator.EQUAL,
                    ast.BinaryOperator.NOT_EQUAL,
                ):
                    raise SemanticError(
                        "string equality requires compile-time static text expressions",
                        expression.location,
                        diagnostic_code=(
                            DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                        ),
                    )
                raise SemanticError(
                    f"operator '{expression.operator.value}' is not supported for string values",
                    expression.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            operand_type = self._comparison_operand_type(expression)
            self._reject_string_operation(
                operand_type,
                expression.location,
                f"operator '{expression.operator.value}' is not supported for string values",
            )
            if expected is not None:
                self._require_type(
                    ast.TypeName.TRIT,
                    expected,
                    expression.location,
                    "comparison result",
                )
            left_type = self._analyze_expression(expression.left, operand_type)
            right_type = self._analyze_expression(expression.right, operand_type)
            self._require_type(
                left_type,
                right_type,
                expression.location,
                "comparison operands",
            )
            self._fold_binary_constant(expression, ast.TypeName.TRIT)
            return ast.TypeName.TRIT
        if expression.operator is ast.BinaryOperator.ADD:
            left_known = self._known_expression_type(expression.left)
            right_known = self._known_expression_type(expression.right)
            if left_known is ast.TypeName.STRING or right_known is ast.TypeName.STRING:
                if self._is_constant_static_text_expression(expression):
                    self._validate_constant_static_text_expression(expression)
                    if expected is not None:
                        self._require_type(
                            ast.TypeName.STRING,
                            expected,
                            expression.location,
                            "constant static text concatenation",
                        )
                    self.expression_types[id(expression)] = ast.TypeName.STRING
                    return ast.TypeName.STRING
                if (
                    left_known is not None
                    and right_known is not None
                    and left_known is not right_known
                ):
                    left_type = self._analyze_expression(expression.left, left_known)
                    right_type = self._analyze_expression(expression.right, right_known)
                    self._require_type(
                        left_type,
                        right_type,
                        expression.location,
                        "operands of '+'",
                    )
                self._analyze_expression(expression.left, left_known)
                self._analyze_expression(expression.right, right_known)
                raise SemanticError(
                    "string concatenation requires a compile-time static text expression",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
                )
        operand_type = self._binary_operand_type(expression)
        if isinstance(operand_type, ast.NominalType):
            self._analyze_expression(expression.left, operand_type)
            self._analyze_expression(expression.right, operand_type)
            raise SemanticError(
                f"operator '{expression.operator.value}' is not supported for nominal values",
                expression.location,
            )
        self._reject_string_operation(
            operand_type,
            expression.location,
            f"operator '{expression.operator.value}' is not supported for string values",
        )
        if expected is not None:
            operand_type = expected
        left_type = self._analyze_expression(expression.left, operand_type)
        right_type = self._analyze_expression(expression.right, operand_type)
        self._require_type(
            left_type,
            right_type,
            expression.location,
            f"operands of '{expression.operator.value}'",
        )
        result_type = (
            ast.TypeName.TRIT
            if expression.operator in RELATIONAL_OPERATORS
            else left_type
        )
        self._fold_binary_constant(expression, result_type)
        self._simplify_binary_expression(expression)
        return left_type

    def _comparison_operand_type(
        self,
        expression: ast.BinaryExpression,
    ) -> ast.DeclaredType:
        left = self._known_expression_type(expression.left)
        right = self._known_expression_type(expression.right)
        if left is ast.TypeName.STRING or right is ast.TypeName.STRING:
            return ast.TypeName.STRING
        return left or right or ast.TypeName.TRYTE

    def _binary_operand_type(self, expression: ast.BinaryExpression) -> ast.DeclaredType:
        left = self._known_expression_type(expression.left)
        right = self._known_expression_type(expression.right)
        if left is ast.TypeName.STRING or right is ast.TypeName.STRING:
            return ast.TypeName.STRING
        if left is not None and right is not None:
            self._require_type(left, right, expression.location, "binary operands")
        return left or right or ast.TypeName.TRYTE

    def _known_expression_type(
        self,
        expression: ast.Expression,
    ) -> ast.DeclaredType | None:
        if isinstance(expression, ast.IntegerLiteral):
            return ast.TypeName.TRYTE
        if isinstance(expression, ast.FloatLiteral):
            return ast.TypeName.F64
        if isinstance(expression, ast.Identifier):
            return self._identifier_type(expression)
        if isinstance(expression, ast.StringLiteral):
            return ast.TypeName.STRING
        if isinstance(expression, ast.AddressOfExpression):
            target = self._known_expression_type(expression.operand)
            return (
                ast.ReferenceType(target, expression.mutable, expression.location)
                if target is not None
                else None
            )
        if isinstance(expression, ast.DereferenceExpression):
            target = self._known_expression_type(expression.operand)
            return target.target if isinstance(target, ast.ReferenceType) else None
        if isinstance(expression, ast.IndexExpression):
            try:
                binding = self._index_expression_array_binding(expression)
            except SemanticError:
                binding = None
            if binding is not None:
                element = binding.type_name.element_type
                return element if isinstance(element, ast.TypeName) else None
            if self._known_expression_type(expression.target) is ast.TypeName.STRING:
                return ast.TypeName.STRING
        if isinstance(expression, ast.SliceExpression):
            target_type = self._known_expression_type(expression.target)
            if target_type is ast.TypeName.STRING:
                return ast.TypeName.STRING
            return target_type
        if isinstance(expression, ast.CallExpression):
            function_name = expression.simple_function_name
            if function_name is None:
                return None
            if function_name in STATIC_TEXT_QUERY_BUILTINS:
                return STATIC_TEXT_QUERY_BUILTINS[function_name]
            if function_name in STATIC_TEXT_TRANSFORM_BUILTINS:
                return ast.TypeName.STRING
            signature = self.functions.get(function_name)
            return None if signature is None else signature.return_type
        if isinstance(expression, ast.RecordExpression):
            if expression.type_name in self.records:
                return ast.NominalType(expression.type_name, expression.location)
            if "." in expression.type_name:
                enum_name, variant_name = expression.type_name.rsplit(".", 1)
                enum = self.enums.get(enum_name)
                if enum is not None and enum.variant(variant_name) is not None:
                    return ast.NominalType(enum.name, expression.location)
            return None
        if isinstance(expression, ast.FieldAccessExpression):
            enum_access = self._enum_variant_access(expression)
            if enum_access is not None:
                enum, _variant = enum_access
                return ast.NominalType(enum.name, expression.location)
            target_type = self._known_expression_type(expression.target)
            if isinstance(target_type, ast.NominalType):
                record = self.records.get(target_type.name)
                if record is not None:
                    field = record.field(expression.field_name)
                    return None if field is None else field.type_name
            return None
        if isinstance(expression, ast.UnaryExpression):
            return self._known_expression_type(expression.operand)
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator
            in (
                ast.BinaryOperator.ADD,
                ast.BinaryOperator.SUBTRACT,
                ast.BinaryOperator.MINIMUM,
                ast.BinaryOperator.MAXIMUM,
            )
        ):
            left = self._known_expression_type(expression.left)
            right = self._known_expression_type(expression.right)
            if left is ast.TypeName.STRING or right is ast.TypeName.STRING:
                return ast.TypeName.STRING
            if left is not None and right is not None and left is right:
                return left
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator in (
                ast.BinaryOperator.COMPARE,
                ast.BinaryOperator.EQUAL,
                ast.BinaryOperator.NOT_EQUAL,
                ast.BinaryOperator.LESS,
                ast.BinaryOperator.LESS_EQUAL,
                ast.BinaryOperator.GREATER,
                ast.BinaryOperator.GREATER_EQUAL,
            )
        ):
            return ast.TypeName.TRIT
        if isinstance(expression, ast.MatchExpression):
            for case in expression.cases:
                known = self._known_expression_type(case.expression)
                if known is not None:
                    return known
            return None
        return None

    def _analyze_match_expression(
        self,
        expression: ast.MatchExpression,
        expected: ast.DeclaredType | None,
    ) -> ast.DeclaredType:
        selector_known = self._known_expression_type(expression.selector)
        if isinstance(selector_known, ast.NominalType) and self._is_enum_type(
            selector_known,
        ):
            selector_type = self._analyze_expression(
                expression.selector,
                selector_known,
            )
            assert isinstance(selector_type, ast.NominalType)
            return self._analyze_enum_match_expression(
                expression,
                selector_type,
                expected,
            )

        selector_type = self._analyze_expression(expression.selector, ast.TypeName.TRIT)
        self._require_type(
            selector_type,
            ast.TypeName.TRIT,
            expression.selector.location,
            "match expression selector",
        )
        explicit_cases: dict[int, ast.MatchExpressionCase] = {}
        fallback_case: ast.MatchExpressionCase | None = None
        for i, case in enumerate(expression.cases):
            if case.label is None:
                if fallback_case is not None:
                    raise SemanticError(
                        "duplicate fallback arm in match expression",
                        case.location,
                    )
                if i != len(expression.cases) - 1:
                    raise SemanticError(
                        "fallback arm must be the last arm in match expression",
                        case.location,
                    )
                fallback_case = case
            else:
                if fallback_case is not None:
                    raise SemanticError(
                        "explicit case arm after fallback arm in match expression",
                        case.location,
                    )
                if case.label not in {-1, 0, 1}:
                    raise SemanticError(
                        f"invalid ternary case {case.label}; expected -1, 0, or 1",
                        case.location,
                    )
                if case.label in explicit_cases:
                    raise SemanticError(
                        f"duplicate ternary case {case.label}",
                        case.location,
                    )
                explicit_cases[case.label] = case

        if fallback_case is not None and len(explicit_cases) == 3:
            raise SemanticError(
                "redundant fallback arm in match expression",
                fallback_case.location,
            )

        cases_by_label: dict[int, ast.MatchExpressionCase] = {}
        for label in (-1, 0, 1):
            if label in explicit_cases:
                cases_by_label[label] = explicit_cases[label]
            elif fallback_case is not None:
                cases_by_label[label] = fallback_case
            else:
                missing = sorted({-1, 0, 1} - explicit_cases.keys())
                rendered = ", ".join(str(lbl) for lbl in missing)
                raise SemanticError(
                    f"match expression is missing case(s): {rendered}",
                    expression.location,
                )

        arm_types: list[ast.DeclaredType] = []
        for label in (-1, 0, 1):
            case = cases_by_label[label]
            arm_expected = expected or (arm_types[0] if arm_types else None)
            arm_type = self._analyze_expression(case.expression, arm_expected)
            if arm_types:
                self._require_type(
                    arm_type,
                    arm_types[0],
                    case.expression.location,
                    "match expression arm",
                )
            arm_types.append(arm_type)

        result_type = arm_types[0]
        self.expression_types[id(expression)] = result_type
        if expected is not None:
            self._require_type(
                result_type,
                expected,
                expression.location,
                "match expression result",
            )
        selector_val = self.constant_values.get(id(expression.selector))
        if selector_val is not None and selector_val in cases_by_label:
            target_case = cases_by_label[selector_val]
            self.simplified_expressions[id(expression)] = target_case.expression
            val = self.constant_values.get(id(target_case.expression))
            if val is not None:
                self.constant_values[id(expression)] = val
            text = self.static_text_values.get(id(target_case.expression))
            if text is not None:
                self.static_text_values[id(expression)] = text
        return result_type

    def _analyze_enum_match_expression(
        self,
        expression: ast.MatchExpression,
        selector_type: ast.NominalType,
        expected: ast.DeclaredType | None,
    ) -> ast.DeclaredType:
        enum = self.enums[selector_type.name]
        explicit_cases: dict[int, ast.MatchExpressionCase] = {}
        fallback_case: ast.MatchExpressionCase | None = None
        for i, case in enumerate(expression.cases):
            if case.label is None:
                if fallback_case is not None:
                    raise SemanticError(
                        "duplicate fallback arm in enum match expression",
                        case.location,
                    )
                if i != len(expression.cases) - 1:
                    raise SemanticError(
                        "fallback arm must be the last arm in enum match expression",
                        case.location,
                    )
                fallback_case = case
                continue
            discriminant = self._enum_case_discriminant(
                case.label,
                selector_type,
                case.location,
                "enum match expression",
            )
            if discriminant in explicit_cases:
                raise SemanticError(
                    f"duplicate enum match arm for discriminant {discriminant}",
                    case.location,
                    diagnostic_code=DiagnosticCode.MATCH_DUPLICATE_ARM,
                )
            explicit_cases[discriminant] = case

        if fallback_case is not None and len(explicit_cases) == len(enum.variants):
            raise SemanticError(
                "redundant fallback arm in enum match expression",
                fallback_case.location,
            )

        cases_by_label: dict[int, ast.MatchExpressionCase] = {}
        missing: list[str] = []
        for variant in enum.variants:
            discriminant = enum.discriminant(variant.name)
            if discriminant in explicit_cases:
                cases_by_label[discriminant] = explicit_cases[discriminant]
            elif fallback_case is not None:
                cases_by_label[discriminant] = fallback_case
            else:
                missing.append(f"{enum.name}.{variant.name}")
        if missing:
            raise SemanticError(
                "enum match expression is missing case(s): " + ", ".join(missing),
                expression.location,
                diagnostic_code=DiagnosticCode.MATCH_NON_EXHAUSTIVE,
            )

        arm_types: list[ast.DeclaredType] = []
        for variant in enum.variants:
            label = enum.discriminant(variant.name)
            case = cases_by_label[label]
            arm_expected = expected or (arm_types[0] if arm_types else None)
            arm_type = self._analyze_enum_match_case_expression(
                case,
                variant,
                arm_expected,
            )
            if arm_types:
                self._require_type(
                    arm_type,
                    arm_types[0],
                    case.expression.location,
                    "enum match expression arm",
                )
            arm_types.append(arm_type)

        result_type = arm_types[0]
        self.expression_types[id(expression)] = result_type
        if expected is not None:
            self._require_type(
                result_type,
                expected,
                expression.location,
                "enum match expression result",
            )
        selector_val = self.constant_values.get(id(expression.selector))
        if selector_val is not None and selector_val in cases_by_label:
            target_case = cases_by_label[selector_val]
            self.simplified_expressions[id(expression)] = target_case.expression
            val = self.constant_values.get(id(target_case.expression))
            if val is not None:
                self.constant_values[id(expression)] = val
            text = self.static_text_values.get(id(target_case.expression))
            if text is not None:
                self.static_text_values[id(expression)] = text
        return result_type

    def _lookup_binding(self, name: str) -> Binding | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _is_enum_type(self, type_name: ast.DeclaredType) -> bool:
        return isinstance(type_name, ast.NominalType) and type_name.name in self.enums

    def _identifier_type(
        self,
        expression: ast.Identifier,
        *,
        allow_array: bool = False,
    ) -> ast.DeclaredType:
        binding = self._lookup_binding(expression.name)
        if binding is not None:
            if isinstance(binding.type_name, ast.ArrayType) and not allow_array:
                raise SemanticError(
                    f"array '{expression.name}' cannot be used as a scalar value",
                    expression.location,
                )
            return binding.type_name
        if expression.name in self.functions:
            raise SemanticError(
                f"function '{expression.name}' cannot be used as a variable",
                expression.location,
            )
        raise SemanticError(
            f"undeclared variable '{expression.name}'",
            expression.location,
        )

    @staticmethod
    def _constant_integer(expression: ast.Expression) -> int | None:
        if isinstance(expression, ast.IntegerLiteral):
            return expression.value
        if isinstance(expression, ast.UnaryExpression):
            operand = SemanticAnalyzer._constant_integer(expression.operand)
            return None if operand is None else -operand
        if isinstance(expression, ast.BinaryExpression):
            left = SemanticAnalyzer._constant_integer(expression.left)
            right = SemanticAnalyzer._constant_integer(expression.right)
            if left is None or right is None:
                return None
            if expression.operator is ast.BinaryOperator.ADD:
                return left + right
            if expression.operator is ast.BinaryOperator.SUBTRACT:
                return left - right
        return None

    @staticmethod
    def _width(type_name: ast.TypeName) -> TernaryWidth:
        return (
            TernaryWidth.TRIT
            if type_name is ast.TypeName.TRIT
            else TernaryWidth.TRYTE
        )

    @staticmethod
    def _comparison_result(value: bool) -> int:
        return -1 if value else 0

    def _constant_tryte_value(self, expression: ast.Expression) -> int | None:
        if self.expression_types.get(id(expression)) is not ast.TypeName.TRYTE:
            return None
        return self.constant_values.get(id(expression))

    def _is_constant_tryte_expression(self, expression: ast.Expression) -> bool:
        if isinstance(expression, ast.IntegerLiteral):
            return True
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_binding(expression.name)
            return (
                binding is not None
                and binding.type_name is ast.TypeName.TRYTE
                and binding.constant_value is not None
            )
        if isinstance(expression, ast.UnaryExpression):
            return self._is_constant_tryte_expression(expression.operand)
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator
            in (
                ast.BinaryOperator.ADD,
                ast.BinaryOperator.SUBTRACT,
                ast.BinaryOperator.MINIMUM,
                ast.BinaryOperator.MAXIMUM,
            )
        ):
            return (
                self._is_constant_tryte_expression(expression.left)
                and self._is_constant_tryte_expression(expression.right)
            )
        if isinstance(expression, ast.LenExpression):
            if self._is_constant_static_text_expression(expression.argument):
                return True
            if isinstance(expression.argument, ast.Identifier):
                binding = self._lookup_binding(expression.argument.name)
                return binding is not None and isinstance(binding.type_name, ast.ArrayType)
        if isinstance(expression, ast.CallExpression):
            if expression.simple_function_name is None:
                return False
            return (
                expression.function_name == "find"
                and len(expression.arguments) == 2
                and all(
                    self._is_constant_static_text_expression(argument.expression)
                    for argument in expression.arguments
                )
            )
        return False

    def _fold_unary_constant(
        self,
        expression: ast.UnaryExpression,
        result_type: ast.TypeName,
    ) -> None:
        operand = self.constant_values.get(id(expression.operand))
        if operand is None:
            return
        try:
            value = invert(operand, self._width(result_type))
        except TernaryRangeError as error:
            raise SemanticError(str(error), expression.location) from error
        self.constant_values[id(expression)] = value

    def _fold_binary_constant(
        self,
        expression: ast.BinaryExpression,
        result_type: ast.TypeName,
    ) -> None:
        left = self.constant_values.get(id(expression.left))
        right = self.constant_values.get(id(expression.right))
        if left is None or right is None:
            return
        try:
            if expression.operator is ast.BinaryOperator.ADD:
                if result_type is ast.TypeName.I64:
                    value = validate_i64(left + right)
                elif result_type is ast.TypeName.F64:
                    value = validate_f64(left + right)
                else:
                    value = add(left, right, self._width(result_type))
            elif expression.operator is ast.BinaryOperator.SUBTRACT:
                width = self._width(result_type)
                value = add(left, invert(right, width), width)
            elif expression.operator is ast.BinaryOperator.MINIMUM:
                value = tritwise_min(left, right, self._width(result_type))
            elif expression.operator is ast.BinaryOperator.MAXIMUM:
                value = tritwise_max(left, right, self._width(result_type))
            elif expression.operator is ast.BinaryOperator.COMPARE:
                source_type = self.expression_types.get(id(expression.left))
                assert isinstance(source_type, ast.TypeName)
                if source_type in (ast.TypeName.I64, ast.TypeName.F64):
                    value = -1 if left < right else 1 if left > right else 0
                else:
                    value = compare(left, right, self._width(source_type))
            elif expression.operator is ast.BinaryOperator.EQUAL:
                value = self._comparison_result(left == right)
            elif expression.operator is ast.BinaryOperator.NOT_EQUAL:
                value = self._comparison_result(left != right)
            elif expression.operator is ast.BinaryOperator.LESS:
                value = self._comparison_result(left < right)
            elif expression.operator is ast.BinaryOperator.LESS_EQUAL:
                value = self._comparison_result(left <= right)
            elif expression.operator is ast.BinaryOperator.GREATER:
                value = self._comparison_result(left > right)
            elif expression.operator is ast.BinaryOperator.GREATER_EQUAL:
                value = self._comparison_result(left >= right)
            else:
                return
        except (TernaryRangeError, TypeError, ValueError) as error:
            raise SemanticError(str(error), expression.location) from error
        self.constant_values[id(expression)] = value

    def _simplify_binary_expression(self, expression: ast.BinaryExpression) -> None:
        left_const = self.constant_values.get(id(expression.left))
        right_const = self.constant_values.get(id(expression.right))
        if expression.operator is ast.BinaryOperator.ADD:
            if right_const == 0:
                self.simplified_expressions[id(expression)] = expression.left
            elif left_const == 0:
                self.simplified_expressions[id(expression)] = expression.right
        elif expression.operator is ast.BinaryOperator.SUBTRACT:
            if right_const == 0:
                self.simplified_expressions[id(expression)] = expression.left
        elif expression.operator is ast.BinaryOperator.MINIMUM:
            if right_const == TRYTE_MAX:
                self.simplified_expressions[id(expression)] = expression.left
            elif left_const == TRYTE_MAX:
                self.simplified_expressions[id(expression)] = expression.right
        elif expression.operator is ast.BinaryOperator.MAXIMUM:
            if right_const == TRYTE_MIN:
                self.simplified_expressions[id(expression)] = expression.left
            elif left_const == TRYTE_MIN:
                self.simplified_expressions[id(expression)] = expression.right


    def _simplify_unary_expression(self, expression: ast.UnaryExpression) -> None:
        if isinstance(expression.operand, ast.UnaryExpression):
            if expression.operator is expression.operand.operator:
                if expression.operator in (ast.UnaryOperator.INVERT, ast.UnaryOperator.NEGATE):
                    self.simplified_expressions[id(expression)] = expression.operand.operand

    @staticmethod
    def _validate_static_string_literal(literal: ast.StringLiteral) -> None:
        try:
            decode_static_text(literal.value)
        except StaticTextDecodeError as error:
            raise SemanticError(
                str(error),
                literal.location,
            ) from error

    def _validate_constant_static_text_expression(
        self,
        expression: ast.Expression,
    ) -> None:
        self._constant_static_text_value(
            expression,
            "string concatenation requires a compile-time static text expression",
        )

    def _constant_static_text_length(self, expression: ast.Expression) -> int:
        return len(
            self._constant_static_text_value(
                expression,
                "len() argument must be a static array or a compile-time static text expression",
            )
        )

    def _constant_static_text_value(
        self,
        expression: ast.Expression,
        error_message: str,
    ) -> str:
        if isinstance(expression, ast.StringLiteral):
            self._validate_static_string_literal(expression)
            self.expression_types[id(expression)] = ast.TypeName.STRING
            text = decode_static_text(expression.value)
            self.static_text_values[id(expression)] = text
            return text
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_binding(expression.name)
            if binding is not None and binding.static_text is not None:
                self.expression_types[id(expression)] = ast.TypeName.STRING
                self.static_text_values[id(expression)] = binding.static_text
                return binding.static_text
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator is ast.BinaryOperator.ADD
        ):
            left = self._constant_static_text_value(expression.left, error_message)
            right = self._constant_static_text_value(expression.right, error_message)
            self.expression_types[id(expression)] = ast.TypeName.STRING
            text = left + right
            self.static_text_values[id(expression)] = text
            return text
        if isinstance(expression, ast.IndexExpression):
            source = self._constant_static_text_value(expression.target, error_message)
            index_type = self._analyze_expression(expression.index, ast.TypeName.TRYTE)
            self._require_type(
                index_type,
                ast.TypeName.TRYTE,
                expression.index.location,
                "static text index",
            )
            index = self._constant_tryte_value(expression.index)
            if index is None:
                raise SemanticError(
                    "static text index must be a tryte expression known at compile time",
                    expression.index.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            if index < 0:
                raise SemanticError(
                    "static text index must be non-negative",
                    expression.index.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            if index >= len(source):
                raise SemanticError(
                    f"static text index {index} is outside text bounds [0, {len(source)})",
                    expression.index.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            self.expression_types[id(expression)] = ast.TypeName.STRING
            text = source[index]
            self.static_text_values[id(expression)] = text
            return text
        if isinstance(expression, ast.SliceExpression):
            source = self._constant_static_text_value(expression.target, error_message)
            start_type = self._analyze_expression(expression.start, ast.TypeName.TRYTE)
            self._require_type(
                start_type,
                ast.TypeName.TRYTE,
                expression.start.location,
                "static text slice start",
            )
            end_type = self._analyze_expression(expression.end, ast.TypeName.TRYTE)
            self._require_type(
                end_type,
                ast.TypeName.TRYTE,
                expression.end.location,
                "static text slice end",
            )
            start = self._constant_tryte_value(expression.start)
            end = self._constant_tryte_value(expression.end)
            if start is None or end is None:
                raise SemanticError(
                    "static text slice bounds must be tryte expressions known at compile time",
                    expression.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            if start < 0 or end < 0:
                raise SemanticError(
                    "static text slice bounds must be non-negative",
                    expression.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            try:
                bounds = SliceBounds.from_values(start, end)
            except NumericError:
                raise SemanticError(
                    f"static text slice start {start} exceeds end {end}",
                    expression.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                ) from None
            if end > len(source):
                raise SemanticError(
                    f"static text slice end {end} is outside text bounds [0, {len(source)}]",
                    expression.end.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            self.expression_types[id(expression)] = ast.TypeName.STRING
            text = source[
                bounds.start.value : bounds.end.value
            ]
            self.static_text_values[id(expression)] = text
            return text
        if isinstance(expression, ast.CallExpression):
            if (
                expression.simple_function_name is not None
                and expression.function_name in STATIC_TEXT_TRANSFORM_BUILTINS
            ):
                self._analyze_static_text_transform_call(expression)
                text = self.static_text_values.get(id(expression))
                if text is not None:
                    return text
        raise SemanticError(
            error_message,
            expression.location,
            diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
        )

    def _is_constant_static_text_expression(self, expression: ast.Expression) -> bool:
        if isinstance(expression, ast.StringLiteral):
            return True
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_binding(expression.name)
            return binding is not None and binding.static_text is not None
        if isinstance(expression, ast.IndexExpression):
            return (
                self._is_constant_static_text_expression(expression.target)
                and self._is_constant_tryte_expression(expression.index)
            )
        if isinstance(expression, ast.SliceExpression):
            return (
                self._is_constant_static_text_expression(expression.target)
                and self._is_constant_tryte_expression(expression.start)
                and self._is_constant_tryte_expression(expression.end)
            )
        if isinstance(expression, ast.CallExpression):
            if expression.simple_function_name is None:
                return False
            return self._is_constant_static_text_transform_call(expression)
        return (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator is ast.BinaryOperator.ADD
            and self._is_constant_static_text_expression(expression.left)
            and self._is_constant_static_text_expression(expression.right)
        )

    @staticmethod
    def _reject_string_operation(
        type_name: ast.DeclaredType,
        location: SourceLocation,
        message: str,
    ) -> None:
        if type_name is ast.TypeName.STRING:
            raise SemanticError(
                message,
                location,
                diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
            )

    @staticmethod
    def _validate_literal(
        literal: ast.IntegerLiteral,
        type_name: ast.TypeName,
    ) -> None:
        if type_name is ast.TypeName.I64:
            minimum, maximum = I64_MIN, I64_MAX
        else:
            minimum, maximum = (
                (TRIT_MIN, TRIT_MAX)
                if type_name is ast.TypeName.TRIT
                else (TRYTE_MIN, TRYTE_MAX)
            )
        if not minimum <= literal.value <= maximum:
            raise SemanticError(
                f"literal {literal.value} is outside {type_name.value} range "
                f"[{minimum}, {maximum}]",
                literal.location,
            )

    @staticmethod
    def _validate_float_literal(literal: ast.FloatLiteral) -> None:
        try:
            validate_f64(literal.value)
        except (TypeError, ValueError) as error:
            raise SemanticError(str(error), literal.location) from error

    @staticmethod
    def _require_type(
        actual: ast.DeclaredType,
        expected: ast.DeclaredType,
        location: SourceLocation,
        subject: str,
        *,
        diagnostic_code: DiagnosticCode = DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
    ) -> None:
        if not _types_equal(actual, expected):
            raise SemanticError(
                (
                    f"{subject} has type {_type_display(actual)}; "
                    f"expected {_type_display(expected)}"
                ),
                location,
                diagnostic_code=diagnostic_code,
            )


def _types_equal(left: ast.DeclaredType, right: ast.DeclaredType) -> bool:
    if isinstance(left, ast.TypeName) or isinstance(right, ast.TypeName):
        return left is right
    if isinstance(left, ast.NominalType) and isinstance(right, ast.NominalType):
        return left.name == right.name
    if isinstance(left, ast.ArrayType) and isinstance(right, ast.ArrayType):
        return (
            left.length == right.length
            and _types_equal(left.element_type, right.element_type)
        )
    if isinstance(left, ast.ReferenceType) and isinstance(right, ast.ReferenceType):
        return left.mutable == right.mutable and _types_equal(left.target, right.target)
    return False


def _type_display(type_name: ast.DeclaredType) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.NominalType):
        return type_name.name
    if isinstance(type_name, ast.ArrayType):
        return f"{_type_display(type_name.element_type)}[{type_name.length}]"
    if isinstance(type_name, ast.ReferenceType):
        prefix = "&mut " if type_name.mutable else "&"
        return prefix + _type_display(type_name.target)
    raise AssertionError(f"unknown declared type {type_name!r}")


def analyze(program: ast.Program) -> SemanticModel:
    return SemanticAnalyzer().analyze(program)
