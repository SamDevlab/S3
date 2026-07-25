"""Typed abstract syntax tree for the initial S3 source language."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import TypeAlias

from .diagnostics import SourceLocation


class TypeName(Enum):
    TRIT = "trit"
    TRYTE = "tryte"


@dataclass(frozen=True, slots=True)
class ArrayType:
    element_type: TypeName | ArrayType
    length: int
    location: SourceLocation


DeclaredType: TypeAlias = TypeName | ArrayType


class UnaryOperator(Enum):
    INVERT = "~"
    NEGATE = "-"


class BinaryOperator(Enum):
    ADD = "+"
    SUBTRACT = "-"
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
    function_name: str
    arguments: tuple[CallArgument, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class IndexExpression:
    array_name: str
    index: Expression
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


@dataclass(frozen=True, slots=True)
class MatchExpressionCase:
    label: int
    expression: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class MatchExpression:
    selector: Expression
    cases: tuple[MatchExpressionCase, ...]
    location: SourceLocation


Expression: TypeAlias = (
    IntegerLiteral
    | StringLiteral
    | Identifier
    | CallExpression
    | IndexExpression
    | UnaryExpression
    | BinaryExpression
    | MatchExpression
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


AssignmentTarget: TypeAlias = VariableTarget | IndexTarget


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
    label: int
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
    body: Block
    location: SourceLocation


Statement: TypeAlias = (
    VariableDeclaration
    | AssignmentStatement
    | ReturnStatement
    | SwitchStatement
    | WhileStatement
    | ForStatement
    | BreakStatement
    | ContinueStatement
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


@dataclass(frozen=True, slots=True)
class FunctionDeclaration:
    signature: FunctionSignature
    body: Block
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
class Program:
    functions: tuple[FunctionDeclaration, ...]
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
