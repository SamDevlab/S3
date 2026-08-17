"""Typed abstract syntax tree for the initial S3 source language."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import TypeAlias

from .diagnostics import SourceLocation


class TypeName(Enum):
    TRIT = "trit"
    TRYTE = "tryte"
    I64 = "i64"
    F64 = "f64"
    STRING = "string"
    BYTES = "bytes"
    TEXT = "text"
    TRYTE_VECTOR = "tryte_vector"
    I64_VECTOR = "i64_vector"
    F64_VECTOR = "f64_vector"
    I64_MAP = "i64_map"
    I64_SET = "i64_set"
    HOST_CAPABILITY = "host_capability"
    RESOURCE_HANDLE = "resource_handle"


@dataclass(frozen=True, slots=True)
class ArrayType:
    element_type: TypeName | ArrayType | ReferenceType
    length: int
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class NominalType:
    name: str
    location: SourceLocation
    type_arguments: tuple[DeclaredType, ...] = ()


@dataclass(frozen=True, slots=True)
class ReferenceType:
    target: TypeName | ArrayType | NominalType | ReferenceType
    mutable: bool
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class SliceType:
    """A borrowed contiguous view with a runtime i64 length."""

    element_type: TypeName
    mutable: bool
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class TypeParameterType:
    name: str
    location: SourceLocation


DeclaredType: TypeAlias = (
    TypeName
    | ArrayType
    | NominalType
    | ReferenceType
    | SliceType
    | TypeParameterType
)


@dataclass(frozen=True, slots=True)
class TypeParameter:
    name: str
    constraint: str
    location: SourceLocation


class UnaryOperator(Enum):
    INVERT = "~"
    NEGATE = "-"


@dataclass(frozen=True, slots=True)
class AddressOfExpression:
    operand: Expression
    mutable: bool
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class DereferenceExpression:
    operand: Expression
    location: SourceLocation


class BinaryOperator(Enum):
    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    MINIMUM = "&"
    MAXIMUM = "|"
    COMPARE = "<=>"
    EQUAL = "=="
    NOT_EQUAL = "!="
    LESS = "<"
    LESS_EQUAL = "<="
    GREATER = ">"
    GREATER_EQUAL = ">="


@dataclass(frozen=True, slots=True)
class IntegerLiteral:
    value: int
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class FloatLiteral:
    value: float
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class StringLiteral:
    value: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Identifier:
    name: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class CallArgument:
    expression: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class CallExpression:
    callee: Expression
    arguments: tuple[CallArgument, ...]
    location: SourceLocation
    type_arguments: tuple[DeclaredType, ...] = ()

    @property
    def function_name(self) -> str:
        if isinstance(self.callee, Identifier):
            return self.callee.name
        raise AttributeError("non-identifier call expression has no function_name")

    @property
    def simple_function_name(self) -> str | None:
        if isinstance(self.callee, Identifier):
            return self.callee.name
        return None


@dataclass(frozen=True, slots=True)
class RecordFieldValue:
    name: str
    expression: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class RecordExpression:
    type_name: str
    fields: tuple[RecordFieldValue, ...]
    location: SourceLocation
    type_arguments: tuple[DeclaredType, ...] = ()


@dataclass(frozen=True, slots=True)
class GenericTypeExpression:
    target: Expression
    type_arguments: tuple[DeclaredType, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class IndexExpression:
    target: Expression
    index: Expression
    location: SourceLocation

    @property
    def array_name(self) -> str:
        if isinstance(self.target, Identifier):
            return self.target.name
        raise AttributeError("non-identifier index expression has no array_name")


@dataclass(frozen=True, slots=True)
class SliceExpression:
    target: Expression
    start: Expression
    end: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class FieldAccessExpression:
    target: Expression
    field_name: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class MatchPayloadLabel:
    variant: FieldAccessExpression
    bindings: tuple[str, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class UnaryExpression:
    operator: UnaryOperator
    operand: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class BinaryExpression:
    operator: BinaryOperator
    left: Expression
    right: Expression
    location: SourceLocation


MatchCaseLabel: TypeAlias = int | FieldAccessExpression | MatchPayloadLabel | None


@dataclass(frozen=True, slots=True)
class MatchExpressionCase:
    label: MatchCaseLabel
    expression: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class MatchExpression:
    selector: Expression
    cases: tuple[MatchExpressionCase, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class LenExpression:
    argument: Expression
    location: SourceLocation


Expression: TypeAlias = (
    IntegerLiteral
    | FloatLiteral
    | StringLiteral
    | Identifier
    | CallExpression
    | RecordExpression
    | GenericTypeExpression
    | IndexExpression
    | SliceExpression
    | FieldAccessExpression
    | UnaryExpression
    | BinaryExpression
    | MatchExpression
    | LenExpression
    | AddressOfExpression
    | DereferenceExpression
)


@dataclass(frozen=True, slots=True)
class ArrayLiteral:
    elements: tuple[Expression, ...]
    location: SourceLocation


Initializer: TypeAlias = Expression | ArrayLiteral


@dataclass(frozen=True, slots=True)
class VariableDeclaration:
    type_name: DeclaredType
    name: str
    initializer: Initializer
    location: SourceLocation
    mutable: bool = False


@dataclass(frozen=True, slots=True)
class VariableTarget:
    name: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class IndexTarget:
    array_name: str
    index: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class DereferenceTarget:
    reference: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class FieldTarget:
    target: Expression
    field_name: str
    location: SourceLocation


AssignmentTarget: TypeAlias = VariableTarget | IndexTarget | DereferenceTarget | FieldTarget


@dataclass(frozen=True, slots=True)
class AssignmentStatement:
    target: AssignmentTarget
    value: Initializer
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ReturnStatement:
    expression: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class TernaryCase:
    label: MatchCaseLabel
    body: Block
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class SwitchStatement:
    expression: Expression
    cases: tuple[TernaryCase, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class WhileStatement:
    condition: Expression
    body: Block
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class BreakStatement:
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ContinueStatement:
    location: SourceLocation



@dataclass(frozen=True, slots=True)
class ForStatement:
    variable_name: str
    variable_type: TypeName
    start_expression: Expression
    end_expression: Expression
    step_expression: Expression
    body: Block
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class CompoundAssignmentStatement:
    target: AssignmentTarget
    operator: BinaryOperator
    value: Initializer
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class DiscardStatement:
    expression: Expression
    location: SourceLocation


Statement: TypeAlias = (
    VariableDeclaration
    | AssignmentStatement
    | CompoundAssignmentStatement
    | DiscardStatement
    | ReturnStatement
    | SwitchStatement
    | WhileStatement
    | BreakStatement
    | ContinueStatement
    | ForStatement
)



@dataclass(frozen=True, slots=True)
class Block:
    statements: tuple[Statement, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type_name: DeclaredType
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class FunctionSignature:
    name: str
    parameters: tuple[Parameter, ...]
    return_type: DeclaredType
    location: SourceLocation
    type_parameters: tuple[TypeParameter, ...] = ()


@dataclass(frozen=True, slots=True)
class FunctionDeclaration:
    signature: FunctionSignature
    body: Block
    location: SourceLocation
    exported: bool = False

    @property
    def name(self) -> str:
        return self.signature.name

    @property
    def parameters(self) -> tuple[Parameter, ...]:
        return self.signature.parameters

    @property
    def return_type(self) -> DeclaredType:
        return self.signature.return_type


@dataclass(frozen=True, slots=True)
class ForeignFunctionDeclaration:
    """A scalar or borrowed-slice function supplied by the host linker."""

    signature: FunctionSignature
    location: SourceLocation

    @property
    def name(self) -> str:
        return self.signature.name

    @property
    def parameters(self) -> tuple[Parameter, ...]:
        return self.signature.parameters

    @property
    def return_type(self) -> DeclaredType:
        return self.signature.return_type


@dataclass(frozen=True, slots=True)
class RecordField:
    name: str
    type_name: DeclaredType
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class RecordDeclaration:
    name: str
    fields: tuple[RecordField, ...]
    location: SourceLocation
    exported: bool = False
    type_parameters: tuple[TypeParameter, ...] = ()


@dataclass(frozen=True, slots=True)
class EnumVariant:
    name: str
    location: SourceLocation
    payload_fields: tuple[RecordField, ...] = ()


@dataclass(frozen=True, slots=True)
class EnumDeclaration:
    name: str
    variants: tuple[EnumVariant, ...]
    location: SourceLocation
    exported: bool = False
    type_parameters: tuple[TypeParameter, ...] = ()


@dataclass(frozen=True, slots=True)
class Program:
    functions: tuple[FunctionDeclaration, ...]
    location: SourceLocation
    module: ModuleDeclaration | None = None
    imports: tuple[ImportDeclaration, ...] = ()
    records: tuple[RecordDeclaration, ...] = ()
    enums: tuple[EnumDeclaration, ...] = ()
    foreign_functions: tuple[ForeignFunctionDeclaration, ...] = ()


@dataclass(frozen=True, slots=True)
class ModuleDeclaration:
    name: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ImportDeclaration:
    module_name: str
    symbol_name: str
    alias: str | None
    location: SourceLocation


def to_dict(value: object) -> object:
    """Serialize AST values without coupling later stages to AST classes."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [to_dict(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        result: dict[str, object] = {"node": type(value).__name__}
        for field in fields(value):
            result[field.name] = to_dict(getattr(value, field.name))
        return result
    return value
