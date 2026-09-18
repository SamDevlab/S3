"""Generic indexed syntax representation for the self-host substrate.

This module is deliberately a syntax *data model*, not a parser.  Nodes own
only scalar identity and range metadata; children and kind-specific payloads
live in separate arenas so the representation has the same shape that an
ordinary S3 implementation can reproduce with parallel integer vectors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import TypeAlias

from .compiler_substrate import InvalidIdError, StableArena


class SyntaxValidationError(ValueError):
    """A syntax arena violates its structural contract."""


@dataclass(frozen=True, slots=True)
class SyntaxSpan:
    file_id: int
    start: int
    end: int


class NodeKind(Enum):
    PROGRAM = "program"
    INTEGER_LITERAL = "integer_literal"
    FLOAT_LITERAL = "float_literal"
    STRING_LITERAL = "string_literal"
    IDENTIFIER = "identifier"
    CALL = "call"
    RECORD_CONSTRUCTION = "record_construction"
    GENERIC_TYPE = "generic_type"
    INDEX = "index"
    SLICE = "slice"
    FIELD_ACCESS = "field_access"
    UNARY = "unary"
    BINARY = "binary"
    MATCH = "match"
    LEN = "len"
    ADDRESS_OF = "address_of"
    DEREFERENCE = "dereference"
    VARIABLE_DECLARATION = "variable_declaration"
    ASSIGNMENT = "assignment"
    COMPOUND_ASSIGNMENT = "compound_assignment"
    DISCARD = "discard"
    RETURN = "return"
    SWITCH = "switch"
    SELECT = "select"
    WHILE = "while"
    BREAK = "break"
    CONTINUE = "continue"
    FOR = "for"
    BLOCK = "block"
    PARAMETER = "parameter"
    FUNCTION = "function"
    FOREIGN_FUNCTION = "foreign_function"
    RECORD_DECLARATION = "record_declaration"
    ENUM_DECLARATION = "enum_declaration"
    MODULE_DECLARATION = "module_declaration"
    IMPORT_DECLARATION = "import_declaration"


class PayloadKind(Enum):
    NONE = "none"
    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"
    SYMBOL = "symbol"
    TYPE = "type"
    OPERATOR = "operator"
    DECLARATION = "declaration"
    FUNCTION = "function"


@dataclass(frozen=True, slots=True)
class IntegerPayload:
    value: int


@dataclass(frozen=True, slots=True)
class FloatPayload:
    value: float


@dataclass(frozen=True, slots=True)
class TextPayload:
    value: str


@dataclass(frozen=True, slots=True)
class SymbolPayload:
    symbol_id: int


@dataclass(frozen=True, slots=True)
class TypePayload:
    type_id: int


@dataclass(frozen=True, slots=True)
class OperatorPayload:
    operator_id: int


@dataclass(frozen=True, slots=True)
class DeclarationPayload:
    symbol_id: int
    type_id: int = -1
    flags: int = 0


@dataclass(frozen=True, slots=True)
class FunctionPayload:
    symbol_id: int
    return_type_id: int
    parameter_first: int = 0
    parameter_count: int = 0
    body_id: int = -1


NodePayload: TypeAlias = (
    IntegerPayload
    | FloatPayload
    | TextPayload
    | SymbolPayload
    | TypePayload
    | OperatorPayload
    | DeclarationPayload
    | FunctionPayload
)


@dataclass(frozen=True, slots=True)
class SyntaxNode:
    id: int
    kind: NodeKind
    span: SyntaxSpan
    payload_kind: PayloadKind
    payload_id: int
    first_child: int
    child_count: int


@dataclass(frozen=True, slots=True)
class SyntaxCheckpoint:
    node: int
    child: int
    payloads: tuple[tuple[PayloadKind, int], ...]
    root_id: int | None


_PAYLOAD_AUTHORITY: dict[NodeKind, PayloadKind] = {
    NodeKind.INTEGER_LITERAL: PayloadKind.INTEGER,
    NodeKind.FLOAT_LITERAL: PayloadKind.FLOAT,
    NodeKind.STRING_LITERAL: PayloadKind.TEXT,
    NodeKind.IDENTIFIER: PayloadKind.SYMBOL,
    NodeKind.GENERIC_TYPE: PayloadKind.TYPE,
    NodeKind.UNARY: PayloadKind.OPERATOR,
    NodeKind.BINARY: PayloadKind.OPERATOR,
    NodeKind.VARIABLE_DECLARATION: PayloadKind.DECLARATION,
    NodeKind.ASSIGNMENT: PayloadKind.DECLARATION,
    NodeKind.COMPOUND_ASSIGNMENT: PayloadKind.DECLARATION,
    NodeKind.PARAMETER: PayloadKind.DECLARATION,
    NodeKind.RECORD_DECLARATION: PayloadKind.DECLARATION,
    NodeKind.ENUM_DECLARATION: PayloadKind.DECLARATION,
    NodeKind.MODULE_DECLARATION: PayloadKind.DECLARATION,
    NodeKind.IMPORT_DECLARATION: PayloadKind.DECLARATION,
    NodeKind.FUNCTION: PayloadKind.FUNCTION,
    NodeKind.FOREIGN_FUNCTION: PayloadKind.FUNCTION,
}

_PAYLOAD_TYPES: dict[PayloadKind, type[object]] = {
    PayloadKind.INTEGER: IntegerPayload,
    PayloadKind.FLOAT: FloatPayload,
    PayloadKind.TEXT: TextPayload,
    PayloadKind.SYMBOL: SymbolPayload,
    PayloadKind.TYPE: TypePayload,
    PayloadKind.OPERATOR: OperatorPayload,
    PayloadKind.DECLARATION: DeclarationPayload,
    PayloadKind.FUNCTION: FunctionPayload,
}


def _payload_kind(payload: NodePayload | None) -> PayloadKind:
    if payload is None:
        return PayloadKind.NONE
    for kind, payload_type in _PAYLOAD_TYPES.items():
        if isinstance(payload, payload_type):
            return kind
    raise TypeError(f"unsupported syntax payload {type(payload).__name__}")


class SyntaxArena:
    """Flat, append-only syntax storage with direct IDs and transactions."""

    def __init__(self, *, symbol_count: int = 0, type_count: int = 0) -> None:
        if symbol_count < 0 or type_count < 0:
            raise ValueError("symbol and type counts must be non-negative")
        self.symbol_count = symbol_count
        self.type_count = type_count
        self.nodes: StableArena[SyntaxNode] = StableArena()
        self.children: StableArena[int] = StableArena()
        self.payloads: dict[PayloadKind, StableArena[object]] = {
            kind: StableArena() for kind in _PAYLOAD_TYPES
        }
        self.root_id: int | None = None

    def checkpoint(self) -> SyntaxCheckpoint:
        return SyntaxCheckpoint(
            self.nodes.checkpoint(),
            self.children.checkpoint(),
            tuple((kind, arena.checkpoint()) for kind, arena in self.payloads.items()),
            self.root_id,
        )

    def rollback(self, checkpoint: SyntaxCheckpoint) -> None:
        self.nodes.rollback(checkpoint.node)
        self.children.rollback(checkpoint.child)
        for kind, cursor in checkpoint.payloads:
            self.payloads[kind].rollback(cursor)
        self.root_id = checkpoint.root_id

    def _store_payload(self, payload: NodePayload | None) -> tuple[PayloadKind, int]:
        kind = _payload_kind(payload)
        if payload is None:
            return PayloadKind.NONE, -1
        return kind, self.payloads[kind].append(payload)

    def append_node(
        self,
        kind: NodeKind,
        span: SyntaxSpan,
        *,
        payload: NodePayload | None = None,
        children: tuple[int, ...] = (),
    ) -> int:
        if not isinstance(kind, NodeKind):
            raise TypeError("syntax node kind must be a NodeKind")
        expected = _PAYLOAD_AUTHORITY.get(kind, PayloadKind.NONE)
        actual = _payload_kind(payload)
        if actual is not expected:
            raise SyntaxValidationError(
                f"{kind.value} requires {expected.value} payload, got {actual.value}"
            )
        if not isinstance(span, SyntaxSpan):
            raise TypeError("syntax node span must be a SyntaxSpan")
        payload_kind, payload_id = self._store_payload(payload)
        first_child = self.children.checkpoint()
        for child_id in children:
            if not isinstance(child_id, int):
                raise TypeError("syntax child IDs must be integers")
            self.children.append(child_id)
        node_id = self.nodes.checkpoint()
        self.nodes.append(
            SyntaxNode(
                node_id,
                kind,
                span,
                payload_kind,
                payload_id,
                first_child,
                len(children),
            )
        )
        return node_id

    def set_root(self, node_id: int) -> None:
        if node_id not in self.nodes:
            raise InvalidIdError(f"unknown syntax root {node_id}")
        self.root_id = node_id

    def node(self, node_id: int) -> SyntaxNode:
        return self.nodes.get(node_id)

    def payload(self, node: SyntaxNode) -> NodePayload | None:
        if node.payload_kind is PayloadKind.NONE:
            return None
        return self.payloads[node.payload_kind].get(node.payload_id)  # type: ignore[return-value]

    def child_ids(self, node_id: int) -> tuple[int, ...]:
        node = self.node(node_id)
        return tuple(
            self.children.get(node.first_child + offset)
            for offset in range(node.child_count)
        )

    def validate(self, root_id: int | None = None) -> None:
        root = self.root_id if root_id is None else root_id
        if root is None or root not in self.nodes:
            raise SyntaxValidationError("invalid root node ID")
        for node_id, node in self.nodes.items():
            if node.id != node_id:
                raise SyntaxValidationError(f"node arena identity mismatch for {node_id}")
            self._validate_node(node)
        self._validate_reachable_root(root)

    def _validate_node(self, node: SyntaxNode) -> None:
        if not isinstance(node.kind, NodeKind):
            raise SyntaxValidationError(f"invalid node kind at node {node.id}")
        if (
            not isinstance(node.span, SyntaxSpan)
            or node.span.file_id < 0
            or node.span.start < 0
            or node.span.end < node.span.start
        ):
            raise SyntaxValidationError(f"invalid span at node {node.id}")
        expected = _PAYLOAD_AUTHORITY.get(node.kind, PayloadKind.NONE)
        if node.payload_kind is not expected:
            raise SyntaxValidationError(
                f"wrong payload kind for {node.kind.value} at node {node.id}"
            )
        if expected is PayloadKind.NONE:
            if node.payload_id != -1:
                raise SyntaxValidationError(f"unexpected payload at node {node.id}")
        else:
            try:
                payload = self.payloads[expected].get(node.payload_id)
            except InvalidIdError as error:
                raise SyntaxValidationError(
                    f"dangling payload at node {node.id}"
                ) from error
            self._validate_payload(expected, payload, node.id)
        if node.first_child < 0 or node.child_count < 0:
            raise SyntaxValidationError(f"invalid child range at node {node.id}")
        for offset in range(node.child_count):
            try:
                child_id = self.children.get(node.first_child + offset)
                self.nodes.get(child_id)
            except InvalidIdError as error:
                raise SyntaxValidationError(
                    f"dangling child reference at node {node.id}"
                ) from error

    def _validate_payload(self, kind: PayloadKind, payload: object, node_id: int) -> None:
        if not isinstance(payload, _PAYLOAD_TYPES[kind]):
            raise SyntaxValidationError(f"payload arena type mismatch at node {node_id}")
        if isinstance(payload, FloatPayload) and not math.isfinite(payload.value):
            raise SyntaxValidationError(f"non-finite float payload at node {node_id}")
        if isinstance(payload, (SymbolPayload, DeclarationPayload, FunctionPayload)):
            if not 0 <= payload.symbol_id < self.symbol_count:
                raise SyntaxValidationError(f"dangling symbol ID at node {node_id}")
        if isinstance(payload, (TypePayload, DeclarationPayload)):
            if isinstance(payload, TypePayload):
                type_id = payload.type_id
            else:
                type_id = payload.type_id
            if type_id != -1 and not 0 <= type_id < self.type_count:
                raise SyntaxValidationError(f"dangling type ID at node {node_id}")
        if isinstance(payload, FunctionPayload):
            if not 0 <= payload.return_type_id < self.type_count or payload.parameter_first < 0:
                raise SyntaxValidationError(f"invalid function payload at node {node_id}")
            if payload.parameter_count < 0 or payload.body_id < -1:
                raise SyntaxValidationError(f"invalid function payload at node {node_id}")

    def _validate_reachable_root(self, root_id: int) -> None:
        seen: set[int] = set()
        stack = [root_id]
        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            stack.extend(reversed(self.child_ids(node_id)))
        if root_id not in seen:
            raise SyntaxValidationError("root is not reachable")

    def to_dict(self) -> dict[str, object]:
        def encode(value: object) -> object:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            if is_dataclass(value):
                return {key: encode(item) for key, item in asdict(value).items()}
            return value

        return {
            "symbol_count": self.symbol_count,
            "type_count": self.type_count,
            "root_id": self.root_id,
            "nodes": [encode(node) for _, node in self.nodes.items()],
            "children": [
                {"id": item_id, "node_id": child_id}
                for item_id, child_id in self.children.items()
            ],
            "payloads": {
                kind.value: [
                    {"id": item_id, "payload": encode(payload)}
                    for item_id, payload in self.payloads[kind].items()
                ]
                for kind in self.payloads
            },
        }

    def structural_digest(self) -> str:
        encoded = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


__all__ = [
    "DeclarationPayload",
    "FloatPayload",
    "FunctionPayload",
    "IntegerPayload",
    "NodeKind",
    "OperatorPayload",
    "PayloadKind",
    "SymbolPayload",
    "SyntaxArena",
    "SyntaxCheckpoint",
    "SyntaxNode",
    "SyntaxSpan",
    "SyntaxValidationError",
    "TextPayload",
    "TypePayload",
]
