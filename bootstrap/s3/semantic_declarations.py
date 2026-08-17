"""Semantic declaration collection for S3 programs.

Extracts top-level symbol collection and layout validation (enums, records,
function signatures) out of SemanticAnalyzer into a dedicated pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from . import ast
from .diagnostics import DiagnosticCode
from .semantic import (
    EnumType,
    FunctionType,
    RecordType,
    SemanticError,
    TRYTE_MAX,
    _enum_layout,
    _nominal_layout_dependencies,
    _return_classification,
)



def _validate_array_type(type_name: ast.ArrayType) -> None:
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


@dataclass(frozen=True, slots=True)
class CollectedDeclarations:
    enums: Dict[str, EnumType]
    records: Dict[str, RecordType]
    functions: Dict[str, FunctionType]


class DeclarationCollector:
    """Collects and validates top-level types (enums, records) and function signatures."""

    def __init__(self) -> None:
        self.enums: Dict[str, EnumType] = {}
        self.records: Dict[str, RecordType] = {}
        self.functions: Dict[str, FunctionType] = {}

    def collect(self, program: ast.Program) -> CollectedDeclarations:
        self._collect_enums(program)
        self._collect_records(program)
        self._collect_signatures(program)
        return CollectedDeclarations(
            enums=dict(self.enums),
            records=dict(self.records),
            functions=dict(self.functions),
        )

    def _collect_enums(self, program: ast.Program) -> None:
        for enum in program.enums:
            if enum.name in self.enums or enum.name in self.records:
                raise SemanticError(
                    f"duplicate type '{enum.name}'",
                    enum.location,
                    diagnostic_code=DiagnosticCode.TYPE_DUPLICATE,
                )
            if len(enum.variants) > TRYTE_MAX + 1:
                raise SemanticError(
                    f"enum '{enum.name}' has {len(enum.variants)} variants; "
                    f"at most {TRYTE_MAX + 1} fit the tryte discriminant range",
                    enum.location,
                )
            variant_names: Set[str] = set()
            for variant in enum.variants:
                if variant.name in variant_names:
                    raise SemanticError(
                        f"duplicate variant '{variant.name}' in enum '{enum.name}'",
                        variant.location,
                        diagnostic_code=DiagnosticCode.ENUM_VARIANT_DUPLICATE,
                    )
                variant_names.add(variant.name)
                payload_names: Set[str] = set()
                for field in variant.payload_fields:
                    if field.name in payload_names:
                        raise SemanticError(
                            f"duplicate payload field '{field.name}' in enum variant '{enum.name}.{variant.name}'",
                            field.location,
                            diagnostic_code=DiagnosticCode.RECORD_FIELD_DUPLICATE,
                        )
                    payload_names.add(field.name)
            self.enums[enum.name] = EnumType(
                enum.name,
                enum.variants,
                enum.location,
            )

    def _collect_records(self, program: ast.Program) -> None:
        for record in program.records:
            if record.name in self.records or record.name in self.enums:
                raise SemanticError(
                    f"duplicate type '{record.name}'",
                    record.location,
                    diagnostic_code=DiagnosticCode.TYPE_DUPLICATE,
                )
            field_names: Set[str] = set()
            for field in record.fields:
                if field.name in field_names:
                    raise SemanticError(
                        f"duplicate field '{field.name}' in record '{record.name}'",
                        field.location,
                        diagnostic_code=DiagnosticCode.RECORD_FIELD_DUPLICATE,
                    )
                field_names.add(field.name)
            self.records[record.name] = RecordType(
                record.name,
                record.fields,
                record.location,
            )

        for record in program.records:
            for field in record.fields:
                if isinstance(field.type_name, ast.ArrayType):
                    _validate_array_type(field.type_name)
                    continue
                if isinstance(field.type_name, ast.NominalType):
                    if field.type_name.name in self.enums:
                        continue
                    if field.type_name.name in self.records:
                        continue
                    raise SemanticError(
                        f"unknown type '{field.type_name.name}'",
                        field.location,
                    )
        self._validate_record_layouts()
        self._validate_enum_layouts()

    def _validate_enum_layouts(self) -> None:
        for enum in self.enums.values():
            for variant in enum.variants:
                for field in variant.payload_fields:
                    if isinstance(field.type_name, ast.ArrayType):
                        _validate_array_type(field.type_name)
                        continue
                    if isinstance(field.type_name, ast.NominalType):
                        if (
                            field.type_name.name in self.records
                            or field.type_name.name in self.enums
                        ):
                            continue
                        raise SemanticError(
                            f"unknown type '{field.type_name.name}'",
                            field.location,
                        )

        visiting: Set[str] = set()
        visited: Set[str] = set()
        stack: List[str] = []

        def visit(name: str) -> None:
            if name in visiting:
                start = stack.index(name)
                cycle = tuple(stack[start:] + [name])
                raise SemanticError(
                    "recursive enum payload layout cycle: " + " -> ".join(cycle),
                    self.enums[name].location,
                )
            if name in visited:
                return
            visiting.add(name)
            stack.append(name)
            enum = self.enums[name]
            for variant in enum.variants:
                for field in variant.payload_fields:
                    if isinstance(field.type_name, ast.NominalType):
                        for dependency in _nominal_layout_dependencies(
                            self.records,
                            field.type_name,
                        ):
                            if dependency in self.enums:
                                visit(dependency)
            stack.pop()
            visiting.remove(name)
            visited.add(name)

        for name in self.enums:
            visit(name)

        for name in self.enums:
            _enum_layout(self.records, self.enums, name)

    def _validate_record_layouts(self) -> None:
        visiting: Set[str] = set()
        visited: Set[str] = set()
        stack: List[str] = []

        def visit(name: str) -> None:
            if name in visiting:
                start = stack.index(name)
                cycle = tuple(stack[start:] + [name])
                raise SemanticError(
                    "recursive record layout cycle: " + " -> ".join(cycle),
                    self.records[name].location,
                )
            if name in visited:
                return
            visiting.add(name)
            stack.append(name)
            record = self.records[name]
            for field in record.fields:
                if (
                    isinstance(field.type_name, ast.NominalType)
                    and field.type_name.name in self.records
                ):
                    visit(field.type_name.name)
            stack.pop()
            visiting.remove(name)
            visited.add(name)

        for name in self.records:
            visit(name)

    def _collect_signatures(self, program: ast.Program) -> None:
        for function in (*program.functions, *program.foreign_functions):
            if function.name in self.records or function.name in self.enums:
                raise SemanticError(
                    f"function '{function.name}' conflicts with type '{function.name}'",
                    function.location,
                    diagnostic_code=DiagnosticCode.TYPE_DUPLICATE,
                )
            if function.name in self.functions:
                raise SemanticError(
                    f"duplicate function '{function.name}'",
                    function.location,
                )
            parameter_names: Set[str] = set()
            parameter_types: List[ast.DeclaredType] = []
            for parameter in function.parameters:
                if parameter.name in parameter_names:
                    raise SemanticError(
                        f"duplicate parameter '{parameter.name}'",
                        parameter.location,
                    )
                parameter_names.add(parameter.name)
                if isinstance(parameter.type_name, ast.ArrayType):
                    _validate_array_type(parameter.type_name)
                if isinstance(parameter.type_name, ast.NominalType):
                    if (
                        parameter.type_name.name not in self.records
                        and parameter.type_name.name not in self.enums
                    ):
                        raise SemanticError(
                            f"unknown type '{parameter.type_name.name}'",
                            parameter.location,
                        )
                parameter_types.append(parameter.type_name)
            if isinstance(function.return_type, ast.ArrayType):
                _validate_array_type(function.return_type)
                _return_classification(self.records, self.enums, function.return_type)
            if isinstance(function.return_type, ast.NominalType):
                if function.return_type.name in self.records:
                    _return_classification(self.records, self.enums, function.return_type)
                elif function.return_type.name in self.enums:
                    _return_classification(self.records, self.enums, function.return_type)
                else:
                    raise SemanticError(
                        f"unknown type '{function.return_type.name}'",
                        function.signature.location,
                    )
            self.functions[function.name] = FunctionType(
                function.name,
                tuple(parameter_types),
                function.return_type,
                function.signature.location,
            )
