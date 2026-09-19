"""Deterministic source-front-end projection into the generic SyntaxArena.

This module is the first bridge from real S3 source text to the generic compiler
data model. It deliberately reuses the production Python lexer/parser as the
reference grammar implementation, but it does not reuse the hosted AST as the
long-lived compiler representation: tokens are materialized into a direct-ID
TokenArena and parsed AST values are projected into the generic SyntaxArena.

The ordinary-S3 parser kernel remains a separate representability boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from . import ast
from .compiler_substrate import SourceBundle, StableArena, SymbolInterner
from .diagnostics import SourceLocation
from .generic_syntax import (
    DeclarationPayload,
    FloatPayload,
    FunctionPayload,
    IntegerPayload,
    NodeKind,
    OperatorPayload,
    SymbolPayload,
    SyntaxArena,
    SyntaxSpan,
    TextPayload,
    TypePayload,
)
from .lexer import SyntaxMode, Token, TokenKind, tokenize
from .parser import parse_tokens


class SourceFrontendError(RuntimeError):
    """The generic source-front-end projection cannot represent an AST value."""


@dataclass(frozen=True, slots=True)
class TokenSpan:
    file_id: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class TokenRecord:
    id: int
    kind: TokenKind
    text: str
    span: TokenSpan
    line: int
    column: int
    source_position: int


class TokenArena:
    """Direct-ID token storage over normalized source text.

    Generic spans are byte offsets into normalized UTF-8 source. The
    source_position field preserves the Python parser's code-point position so
    records can be reconstructed into reference tokens without source rescans.
    """

    POSITION_AUTHORITY = "normalized_utf8_bytes"

    def __init__(self, *, file_id: int, source: str, mode: SyntaxMode) -> None:
        self.file_id = file_id
        self.source = source
        self.mode = mode
        self.tokens: StableArena[TokenRecord] = StableArena()

    @staticmethod
    def normalize_source(source: str) -> str:
        return source.replace("\r\n", "\n").replace("\r", "\n")

    @classmethod
    def from_source(
        cls,
        source: str,
        *,
        file_id: int = 0,
        mode: SyntaxMode = SyntaxMode.V0_6,
    ) -> "TokenArena":
        normalized = cls.normalize_source(source)
        arena = cls(file_id=file_id, source=normalized, mode=mode)
        byte_offsets = _codepoint_to_byte_offsets(normalized)
        for token in tokenize(normalized, mode=mode):
            token_id = arena.tokens.checkpoint()
            start = byte_offsets[token.position]
            end_position = min(len(normalized), token.position + len(token.text))
            end = byte_offsets[end_position]
            arena.tokens.append(
                TokenRecord(
                    token_id,
                    token.kind,
                    token.text,
                    TokenSpan(file_id, start, end),
                    token.line,
                    token.column,
                    token.position,
                )
            )
        return arena

    def __len__(self) -> int:
        return len(self.tokens)

    def token(self, token_id: int) -> TokenRecord:
        return self.tokens.get(token_id)

    def to_reference_tokens(self) -> tuple[Token, ...]:
        return tuple(
            Token(
                record.kind,
                record.text,
                record.line,
                record.column,
                record.source_position,
            )
            for _, record in self.tokens.items()
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "position_authority": self.POSITION_AUTHORITY,
            "file_id": self.file_id,
            "mode": self.mode.name,
            "tokens": [
                {
                    "id": record.id,
                    "kind": record.kind.name,
                    "text": record.text,
                    "span": {
                        "file_id": record.span.file_id,
                        "start": record.span.start,
                        "end": record.span.end,
                    },
                    "line": record.line,
                    "column": record.column,
                }
                for _, record in self.tokens.items()
            ],
        }

    def structural_digest(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceFrontendResult:
    token_arena: TokenArena
    syntax_arena: SyntaxArena
    symbol_names: tuple[str, ...]
    parser_backend: str = "python_reference_recursive_descent"

    @property
    def root_id(self) -> int:
        if self.syntax_arena.root_id is None:
            raise SourceFrontendError("syntax arena has no root")
        return self.syntax_arena.root_id

    def structural_digest(self) -> str:
        digest = sha256()
        digest.update(self.token_arena.structural_digest().encode("ascii"))
        digest.update(self.syntax_arena.structural_digest().encode("ascii"))
        for name in self.symbol_names:
            encoded = name.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SourceUnitFrontendResult:
    file_id: int
    path: str
    token_arena: TokenArena
    syntax_arena: SyntaxArena

    @property
    def root_id(self) -> int:
        if self.syntax_arena.root_id is None:
            raise SourceFrontendError("syntax arena has no root")
        return self.syntax_arena.root_id


@dataclass(frozen=True, slots=True)
class SourceBundleFrontendResult:
    units: tuple[SourceUnitFrontendResult, ...]
    symbol_names: tuple[str, ...]
    parser_backend: str = "python_reference_recursive_descent"

    def structural_digest(self) -> str:
        digest = sha256()
        for unit in self.units:
            path = unit.path.encode("utf-8")
            digest.update(len(path).to_bytes(8, "big"))
            digest.update(path)
            digest.update(unit.token_arena.structural_digest().encode("ascii"))
            digest.update(unit.syntax_arena.structural_digest().encode("ascii"))
        for name in self.symbol_names:
            encoded = name.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
        return digest.hexdigest()


_UNARY_OPERATOR_IDS = {
    ast.UnaryOperator.INVERT: 0,
    ast.UnaryOperator.NEGATE: 1,
}

_BINARY_OPERATOR_IDS = {
    ast.BinaryOperator.ADD: 0,
    ast.BinaryOperator.SUBTRACT: 1,
    ast.BinaryOperator.MULTIPLY: 2,
    ast.BinaryOperator.DIVIDE: 3,
    ast.BinaryOperator.MINIMUM: 4,
    ast.BinaryOperator.MAXIMUM: 5,
    ast.BinaryOperator.COMPARE: 6,
    ast.BinaryOperator.EQUAL: 7,
    ast.BinaryOperator.NOT_EQUAL: 8,
    ast.BinaryOperator.LESS: 9,
    ast.BinaryOperator.LESS_EQUAL: 10,
    ast.BinaryOperator.GREATER: 11,
    ast.BinaryOperator.GREATER_EQUAL: 12,
}


def _codepoint_to_byte_offsets(source: str) -> tuple[int, ...]:
    result = [0]
    total = 0
    for character in source:
        total += len(character.encode("utf-8"))
        result.append(total)
    return tuple(result)


class _AstProjector:
    def __init__(
        self,
        tokens: TokenArena,
        interner: SymbolInterner | None = None,
    ) -> None:
        self.tokens = tokens
        self.interner = interner if interner is not None else SymbolInterner()
        self.arena = SyntaxArena(symbol_count=0, type_count=0)
        self._byte_offsets = _codepoint_to_byte_offsets(tokens.source)
        self._token_by_source_position = {
            record.source_position: record for _, record in tokens.tokens.items()
        }

    def finish(self, program: ast.Program) -> tuple[SyntaxArena, tuple[str, ...]]:
        root = self.project(program)
        self.arena.symbol_count = self.interner.length
        self.arena.set_root(root)
        self.arena.validate()
        names = tuple(
            self.interner.name(symbol_id)
            for symbol_id in range(self.interner.length)
        )
        return self.arena, names

    def _symbol(self, value: str) -> int:
        return self.interner.intern(value)

    def _start(self, location: SourceLocation) -> int:
        index = min(max(location.position, 0), len(self.tokens.source))
        return self._byte_offsets[index]

    def _span(
        self,
        location: SourceLocation,
        children: tuple[int, ...] = (),
    ) -> SyntaxSpan:
        start = self._start(location)
        token = self._token_by_source_position.get(location.position)
        end = token.span.end if token is not None else start
        for child_id in children:
            child = self.arena.node(child_id)
            end = max(end, child.span.end)
        return SyntaxSpan(self.tokens.file_id, start, max(start, end))

    def _identifier(self, name: str, location: SourceLocation) -> int:
        return self.arena.append_node(
            NodeKind.IDENTIFIER,
            self._span(location),
            payload=SymbolPayload(self._symbol(name)),
        )

    def _type_parameter(self, value: ast.TypeParameter) -> int:
        constraint = self._identifier(value.constraint, value.location)
        children = (constraint,)
        return self.arena.append_node(
            NodeKind.TYPE_PARAMETER,
            self._span(value.location, children),
            payload=DeclarationPayload(self._symbol(value.name), -1, 0),
            children=children,
        )

    def project_type(self, value: ast.DeclaredType) -> int:
        if isinstance(value, ast.TypeName):
            return self.arena.append_node(
                NodeKind.TYPE_NAME,
                SyntaxSpan(self.tokens.file_id, 0, 0),
                payload=SymbolPayload(self._symbol(value.value)),
            )
        if isinstance(value, ast.ArrayType):
            child = self.project_type(value.element_type)
            return self.arena.append_node(
                NodeKind.ARRAY_TYPE,
                self._span(value.location, (child,)),
                payload=IntegerPayload(value.length),
                children=(child,),
            )
        if isinstance(value, ast.VectorType):
            child = self.project_type(value.element_type)
            return self.arena.append_node(
                NodeKind.VECTOR_TYPE,
                self._span(value.location, (child,)),
                children=(child,),
            )
        if isinstance(value, ast.NominalType):
            arguments = tuple(
                self.project_type(item) for item in value.type_arguments
            )
            return self.arena.append_node(
                NodeKind.NOMINAL_TYPE,
                self._span(value.location, arguments),
                payload=SymbolPayload(self._symbol(value.name)),
                children=arguments,
            )
        if isinstance(value, ast.ReferenceType):
            child = self.project_type(value.target)
            return self.arena.append_node(
                NodeKind.REFERENCE_TYPE,
                self._span(value.location, (child,)),
                payload=IntegerPayload(1 if value.mutable else 0),
                children=(child,),
            )
        if isinstance(value, ast.SliceType):
            child = self.project_type(value.element_type)
            return self.arena.append_node(
                NodeKind.SLICE_TYPE,
                self._span(value.location, (child,)),
                payload=IntegerPayload(1 if value.mutable else 0),
                children=(child,),
            )
        if isinstance(value, ast.TypeParameterType):
            return self.arena.append_node(
                NodeKind.TYPE_PARAMETER_TYPE,
                self._span(value.location),
                payload=SymbolPayload(self._symbol(value.name)),
            )
        raise SourceFrontendError(
            f"unsupported declared type {type(value).__name__}"
        )

    def project(self, value: object) -> int:
        if isinstance(value, ast.Program):
            children: list[int] = []
            if value.module is not None:
                children.append(self.project(value.module))
            children.extend(self.project(item) for item in value.imports)
            children.extend(self.project(item) for item in value.records)
            children.extend(self.project(item) for item in value.enums)
            children.extend(
                self.project(item) for item in value.foreign_functions
            )
            children.extend(self.project(item) for item in value.functions)
            result = tuple(children)
            return self.arena.append_node(
                NodeKind.PROGRAM,
                self._span(value.location, result),
                children=result,
            )

        if isinstance(value, ast.ModuleDeclaration):
            return self.arena.append_node(
                NodeKind.MODULE_DECLARATION,
                self._span(value.location),
                payload=DeclarationPayload(
                    self._symbol(value.name), -1, 0
                ),
            )

        if isinstance(value, ast.ImportDeclaration):
            module = self._identifier(value.module_name, value.location)
            symbol = self._identifier(value.symbol_name, value.location)
            children = [module, symbol]
            alias_flag = 0
            if value.alias is not None:
                alias_flag = 1
                children.append(
                    self._identifier(value.alias, value.location)
                )
            child_ids = tuple(children)
            return self.arena.append_node(
                NodeKind.IMPORT_DECLARATION,
                self._span(value.location, child_ids),
                payload=DeclarationPayload(
                    self._symbol(value.module_name), -1, alias_flag
                ),
                children=child_ids,
            )

        if isinstance(value, ast.TypeParameter):
            return self._type_parameter(value)

        if isinstance(value, ast.RecordField):
            type_node = self.project_type(value.type_name)
            return self.arena.append_node(
                NodeKind.RECORD_FIELD,
                self._span(value.location, (type_node,)),
                payload=DeclarationPayload(
                    self._symbol(value.name), -1, 0
                ),
                children=(type_node,),
            )

        if isinstance(value, ast.EnumVariant):
            fields = tuple(
                self.project(item) for item in value.payload_fields
            )
            return self.arena.append_node(
                NodeKind.ENUM_VARIANT,
                self._span(value.location, fields),
                payload=DeclarationPayload(
                    self._symbol(value.name), -1, 0
                ),
                children=fields,
            )

        if isinstance(value, ast.RecordDeclaration):
            type_parameters = tuple(
                self.project(item) for item in value.type_parameters
            )
            fields = tuple(self.project(item) for item in value.fields)
            children = type_parameters + fields
            return self.arena.append_node(
                NodeKind.RECORD_DECLARATION,
                self._span(value.location, children),
                payload=DeclarationPayload(
                    self._symbol(value.name),
                    -1,
                    1 if value.exported else 0,
                ),
                children=children,
            )

        if isinstance(value, ast.EnumDeclaration):
            type_parameters = tuple(
                self.project(item) for item in value.type_parameters
            )
            variants = tuple(self.project(item) for item in value.variants)
            children = type_parameters + variants
            return self.arena.append_node(
                NodeKind.ENUM_DECLARATION,
                self._span(value.location, children),
                payload=DeclarationPayload(
                    self._symbol(value.name),
                    -1,
                    1 if value.exported else 0,
                ),
                children=children,
            )

        if isinstance(value, ast.Parameter):
            type_node = self.project_type(value.type_name)
            return self.arena.append_node(
                NodeKind.PARAMETER,
                self._span(value.location, (type_node,)),
                payload=DeclarationPayload(
                    self._symbol(value.name), -1, 0
                ),
                children=(type_node,),
            )

        if isinstance(value, ast.FunctionDeclaration):
            type_parameters = tuple(
                self.project(item)
                for item in value.signature.type_parameters
            )
            parameters = tuple(
                self.project(item) for item in value.parameters
            )
            return_type = self.project_type(value.return_type)
            body = self.project(value.body)
            children = type_parameters + parameters + (return_type, body)
            first_parameter = parameters[0] if parameters else 0
            return self.arena.append_node(
                NodeKind.FUNCTION,
                self._span(value.location, children),
                payload=FunctionPayload(
                    self._symbol(value.name),
                    -1,
                    first_parameter,
                    len(parameters),
                    body,
                ),
                children=children,
            )

        if isinstance(value, ast.ForeignFunctionDeclaration):
            type_parameters = tuple(
                self.project(item)
                for item in value.signature.type_parameters
            )
            parameters = tuple(
                self.project(item) for item in value.parameters
            )
            return_type = self.project_type(value.return_type)
            children = type_parameters + parameters + (return_type,)
            first_parameter = parameters[0] if parameters else 0
            return self.arena.append_node(
                NodeKind.FOREIGN_FUNCTION,
                self._span(value.location, children),
                payload=FunctionPayload(
                    self._symbol(value.name),
                    -1,
                    first_parameter,
                    len(parameters),
                    -1,
                ),
                children=children,
            )

        if isinstance(value, ast.Block):
            children = tuple(
                self.project(item) for item in value.statements
            )
            return self.arena.append_node(
                NodeKind.BLOCK,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.IntegerLiteral):
            return self.arena.append_node(
                NodeKind.INTEGER_LITERAL,
                self._span(value.location),
                payload=IntegerPayload(value.value),
            )
        if isinstance(value, ast.FloatLiteral):
            return self.arena.append_node(
                NodeKind.FLOAT_LITERAL,
                self._span(value.location),
                payload=FloatPayload(value.value),
            )
        if isinstance(value, ast.StringLiteral):
            return self.arena.append_node(
                NodeKind.STRING_LITERAL,
                self._span(value.location),
                payload=TextPayload(value.value),
            )
        if isinstance(value, ast.Identifier):
            return self._identifier(value.name, value.location)

        if isinstance(value, ast.CallArgument):
            child = self.project(value.expression)
            return self.arena.append_node(
                NodeKind.CALL_ARGUMENT,
                self._span(value.location, (child,)),
                children=(child,),
            )

        if isinstance(value, ast.CallExpression):
            callee = self.project(value.callee)
            type_arguments = tuple(
                self.project_type(item) for item in value.type_arguments
            )
            arguments = tuple(
                self.project(item) for item in value.arguments
            )
            children = (callee,) + type_arguments + arguments
            return self.arena.append_node(
                NodeKind.CALL,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.RecordFieldValue):
            child = self.project(value.expression)
            return self.arena.append_node(
                NodeKind.RECORD_FIELD_VALUE,
                self._span(value.location, (child,)),
                payload=DeclarationPayload(
                    self._symbol(value.name), -1, 0
                ),
                children=(child,),
            )

        if isinstance(value, ast.RecordExpression):
            type_arguments = tuple(
                self.project_type(item) for item in value.type_arguments
            )
            fields = tuple(self.project(item) for item in value.fields)
            children = type_arguments + fields
            return self.arena.append_node(
                NodeKind.RECORD_CONSTRUCTION,
                self._span(value.location, children),
                payload=SymbolPayload(self._symbol(value.type_name)),
                children=children,
            )

        if isinstance(value, ast.GenericTypeExpression):
            target = self.project(value.target)
            arguments = tuple(
                self.project_type(item) for item in value.type_arguments
            )
            children = (target,) + arguments
            return self.arena.append_node(
                NodeKind.GENERIC_TYPE,
                self._span(value.location, children),
                payload=TypePayload(-1),
                children=children,
            )

        if isinstance(value, ast.IndexExpression):
            children = (
                self.project(value.target),
                self.project(value.index),
            )
            return self.arena.append_node(
                NodeKind.INDEX,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.SliceExpression):
            children = (
                self.project(value.target),
                self.project(value.start),
                self.project(value.end),
            )
            return self.arena.append_node(
                NodeKind.SLICE,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.FieldAccessExpression):
            child = self.project(value.target)
            return self.arena.append_node(
                NodeKind.FIELD_ACCESS,
                self._span(value.location, (child,)),
                payload=SymbolPayload(self._symbol(value.field_name)),
                children=(child,),
            )

        if isinstance(value, ast.MatchPayloadLabel):
            variant = self.project(value.variant)
            bindings = tuple(
                self._identifier(name, value.location)
                for name in value.bindings
            )
            children = (variant,) + bindings
            return self.arena.append_node(
                NodeKind.MATCH_PAYLOAD_LABEL,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.UnaryExpression):
            child = self.project(value.operand)
            return self.arena.append_node(
                NodeKind.UNARY,
                self._span(value.location, (child,)),
                payload=OperatorPayload(
                    _UNARY_OPERATOR_IDS[value.operator]
                ),
                children=(child,),
            )

        if isinstance(value, ast.BinaryExpression):
            children = (
                self.project(value.left),
                self.project(value.right),
            )
            return self.arena.append_node(
                NodeKind.BINARY,
                self._span(value.location, children),
                payload=OperatorPayload(
                    _BINARY_OPERATOR_IDS[value.operator]
                ),
                children=children,
            )

        if isinstance(value, ast.MatchExpressionCase):
            label = self._project_match_label(
                value.label, value.location
            )
            expression = self.project(value.expression)
            children = (
                ((label,) if label is not None else ())
                + (expression,)
            )
            return self.arena.append_node(
                NodeKind.MATCH_CASE,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.MatchExpression):
            selector = self.project(value.selector)
            cases = tuple(self.project(item) for item in value.cases)
            children = (selector,) + cases
            return self.arena.append_node(
                NodeKind.MATCH,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.LenExpression):
            child = self.project(value.argument)
            return self.arena.append_node(
                NodeKind.LEN,
                self._span(value.location, (child,)),
                children=(child,),
            )

        if isinstance(value, ast.AddressOfExpression):
            child = self.project(value.operand)
            return self.arena.append_node(
                NodeKind.ADDRESS_OF,
                self._span(value.location, (child,)),
                payload=IntegerPayload(1 if value.mutable else 0),
                children=(child,),
            )

        if isinstance(value, ast.DereferenceExpression):
            child = self.project(value.operand)
            return self.arena.append_node(
                NodeKind.DEREFERENCE,
                self._span(value.location, (child,)),
                children=(child,),
            )

        if isinstance(value, ast.ArrayLiteral):
            children = tuple(
                self.project(item) for item in value.elements
            )
            return self.arena.append_node(
                NodeKind.ARRAY_LITERAL,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.VariableTarget):
            return self.arena.append_node(
                NodeKind.ASSIGNMENT_TARGET,
                self._span(value.location),
                payload=DeclarationPayload(
                    self._symbol(value.name), -1, 0
                ),
            )

        if isinstance(value, ast.IndexTarget):
            index = self.project(value.index)
            return self.arena.append_node(
                NodeKind.INDEX_TARGET,
                self._span(value.location, (index,)),
                payload=DeclarationPayload(
                    self._symbol(value.array_name), -1, 0
                ),
                children=(index,),
            )

        if isinstance(value, ast.FieldTarget):
            target = self.project(value.target)
            return self.arena.append_node(
                NodeKind.FIELD_TARGET,
                self._span(value.location, (target,)),
                payload=DeclarationPayload(
                    self._symbol(value.field_name), -1, 0
                ),
                children=(target,),
            )

        if isinstance(value, ast.DereferenceTarget):
            reference = self.project(value.reference)
            return self.arena.append_node(
                NodeKind.DEREFERENCE_TARGET,
                self._span(value.location, (reference,)),
                children=(reference,),
            )

        if isinstance(value, ast.VariableDeclaration):
            type_node = self.project_type(value.type_name)
            initializer = self.project(value.initializer)
            children = (type_node, initializer)
            return self.arena.append_node(
                NodeKind.VARIABLE_DECLARATION,
                self._span(value.location, children),
                payload=DeclarationPayload(
                    self._symbol(value.name),
                    -1,
                    1 if value.mutable else 0,
                ),
                children=children,
            )

        if isinstance(value, ast.AssignmentStatement):
            target = self.project(value.target)
            rhs = self.project(value.value)
            children = (target, rhs)
            return self.arena.append_node(
                NodeKind.ASSIGNMENT,
                self._span(value.location, children),
                payload=DeclarationPayload(
                    self._assignment_symbol(value.target), -1, 0
                ),
                children=children,
            )

        if isinstance(value, ast.CompoundAssignmentStatement):
            target = self.project(value.target)
            rhs = self.project(value.value)
            operator = self.arena.append_node(
                NodeKind.BINARY,
                self._span(value.location),
                payload=OperatorPayload(
                    _BINARY_OPERATOR_IDS[value.operator]
                ),
            )
            children = (target, operator, rhs)
            return self.arena.append_node(
                NodeKind.COMPOUND_ASSIGNMENT,
                self._span(value.location, children),
                payload=DeclarationPayload(
                    self._assignment_symbol(value.target), -1, 0
                ),
                children=children,
            )

        if isinstance(value, ast.DiscardStatement):
            child = self.project(value.expression)
            return self.arena.append_node(
                NodeKind.DISCARD,
                self._span(value.location, (child,)),
                children=(child,),
            )

        if isinstance(value, ast.ReturnStatement):
            child = self.project(value.expression)
            return self.arena.append_node(
                NodeKind.RETURN,
                self._span(value.location, (child,)),
                children=(child,),
            )

        if isinstance(value, ast.TernaryCase):
            label = self._project_match_label(
                value.label, value.location
            )
            body = self.project(value.body)
            children = ((label,) if label is not None else ()) + (body,)
            return self.arena.append_node(
                NodeKind.MATCH_CASE,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.SwitchStatement):
            selector = self.project(value.expression)
            cases = tuple(self.project(item) for item in value.cases)
            children = (selector,) + cases
            return self.arena.append_node(
                NodeKind.SWITCH,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.SelectArm):
            children = (
                self.project(value.operation),
                self.project(value.body),
            )
            return self.arena.append_node(
                NodeKind.SELECT_ARM,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.SelectStatement):
            children = tuple(self.project(item) for item in value.arms)
            return self.arena.append_node(
                NodeKind.SELECT,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.WhileStatement):
            children = (
                self.project(value.condition),
                self.project(value.body),
            )
            return self.arena.append_node(
                NodeKind.WHILE,
                self._span(value.location, children),
                children=children,
            )

        if isinstance(value, ast.BreakStatement):
            return self.arena.append_node(
                NodeKind.BREAK, self._span(value.location)
            )

        if isinstance(value, ast.ContinueStatement):
            return self.arena.append_node(
                NodeKind.CONTINUE, self._span(value.location)
            )

        if isinstance(value, ast.ForStatement):
            type_node = self.project_type(value.variable_type)
            children = (
                type_node,
                self.project(value.start_expression),
                self.project(value.end_expression),
                self.project(value.step_expression),
                self.project(value.body),
            )
            return self.arena.append_node(
                NodeKind.FOR,
                self._span(value.location, children),
                payload=DeclarationPayload(
                    self._symbol(value.variable_name), -1, 0
                ),
                children=children,
            )

        raise SourceFrontendError(
            f"unsupported AST value {type(value).__name__}"
        )

    def _assignment_symbol(self, target: ast.AssignmentTarget) -> int:
        if isinstance(target, ast.VariableTarget):
            return self._symbol(target.name)
        if isinstance(target, ast.IndexTarget):
            return self._symbol(target.array_name)
        if isinstance(target, ast.FieldTarget):
            return self._symbol(target.field_name)
        return self._symbol("*")

    def _project_match_label(
        self,
        label: ast.MatchCaseLabel,
        location: SourceLocation,
    ) -> int | None:
        if label is None:
            return None
        if isinstance(label, int):
            return self.arena.append_node(
                NodeKind.INTEGER_LITERAL,
                self._span(location),
                payload=IntegerPayload(label),
            )
        return self.project(label)


def parse_source_to_syntax(
    source: str,
    *,
    file_id: int = 0,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> SourceFrontendResult:
    """Tokenize and parse real source into the generic SyntaxArena.

    The parser backend is currently the production Python recursive-descent
    parser. This closes the source-to-generic-syntax integration path without
    claiming an S3-native parser implementation.
    """

    token_arena = TokenArena.from_source(
        source, file_id=file_id, mode=mode
    )
    program = parse_tokens(
        token_arena.to_reference_tokens(), mode=mode
    )
    projector = _AstProjector(token_arena)
    syntax_arena, symbols = projector.finish(program)
    return SourceFrontendResult(token_arena, syntax_arena, symbols)


__all__ = [
    "SourceFrontendError",
    "SourceFrontendResult",
    "TokenArena",
    "TokenRecord",
    "TokenSpan",
    "parse_source_to_syntax",
]