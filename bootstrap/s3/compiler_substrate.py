"""Deterministic, bounded substrate primitives for future compiler frontends.

This module deliberately stops at representability.  It provides ownership,
stable IDs, source transport, lexical state, and output transactions; it does
not parse S3 source or implement a self-hosted compiler pipeline.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Generic, Iterable, Iterator, TypeVar

from .dynamic import DynamicText, DynamicTextMap, text_i64_map_new


class SubstrateError(RuntimeError):
    """Base error for bounded compiler-substrate state transitions."""


class CapacityError(SubstrateError):
    """A bounded substrate object cannot grow implicitly."""


class InvalidIdError(SubstrateError):
    """A direct stable ID is absent from its arena."""


class ScopeError(SubstrateError):
    """A lexical scope transition is invalid."""


T = TypeVar("T")
StableId = int


class StableArena(Generic[T]):
    """Append-only direct-ID arena with bounded rollback.

    IDs are integers, never pointers.  Rollback removes only entries created
    after the checkpoint; already published IDs are never renumbered.
    """

    def __init__(self, capacity: int | None = None) -> None:
        if capacity is not None and capacity < 0:
            raise ValueError("arena capacity must be non-negative")
        self.capacity = capacity
        self._next_id = 0
        self._items: dict[int, T] = {}

    def append(self, value: T) -> StableId:
        if self.capacity is not None and len(self._items) >= self.capacity:
            raise CapacityError("arena capacity exhausted")
        item_id = self._next_id
        self._next_id += 1
        self._items[item_id] = value
        return item_id

    def get(self, item_id: StableId) -> T:
        try:
            return self._items[item_id]
        except KeyError as error:
            raise InvalidIdError(f"unknown arena id {item_id}") from error

    def __contains__(self, item_id: object) -> bool:
        return item_id in self._items

    def __len__(self) -> int:
        return len(self._items)

    def items(self) -> Iterator[tuple[StableId, T]]:
        yield from self._items.items()

    def checkpoint(self) -> StableId:
        return self._next_id

    def rollback(self, checkpoint: StableId) -> None:
        if checkpoint < 0 or checkpoint > self._next_id:
            raise ValueError("invalid arena checkpoint")
        for item_id in tuple(self._items):
            if item_id >= checkpoint:
                del self._items[item_id]


class SymbolInterner:
    """Stable UTF-8 symbol IDs backed by the deterministic text map."""

    def __init__(self, initial_capacity: int = 16) -> None:
        self._names = text_i64_map_new(initial_capacity)
        self._symbols: StableArena[DynamicText] = StableArena()

    def intern(self, name: str | DynamicText) -> StableId:
        text = name if isinstance(name, DynamicText) else DynamicText.from_static(name)
        existing = self._names.contains(text)
        if existing == -1:
            return self._names.get(text)
        symbol_id = self._symbols.append(text.clone())
        try:
            if self._names.length >= self._names.capacity:
                self._names.reserve(max(1, self._names.capacity * 2))
            self._names.put(text, symbol_id)
        except Exception:
            self._symbols.rollback(symbol_id)
            raise
        return symbol_id

    def name(self, symbol_id: StableId) -> str:
        return self._symbols.get(symbol_id).to_string()

    def checkpoint(self) -> tuple[StableId, int]:
        return self._symbols.checkpoint(), self._names.length

    def rollback(self, checkpoint: tuple[StableId, int]) -> None:
        symbol_checkpoint, _ = checkpoint
        self._symbols.rollback(symbol_checkpoint)
        rebuilt = text_i64_map_new(max(16, len(self._symbols)))
        for symbol_id, name in self._symbols.items():
            rebuilt.put(name, symbol_id)
        self._names = rebuilt

    @property
    def length(self) -> int:
        return len(self._symbols)


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    data: bytes


@dataclass(frozen=True, slots=True)
class SourceCursor:
    file_id: StableId
    offset: int


@dataclass(frozen=True, slots=True)
class SourceSpan:
    file_id: StableId
    start: int
    end: int


class SourceBundle:
    """Canonical source file order and normalized LF byte transport."""

    def __init__(self, files: Iterable[tuple[str, str | bytes]]) -> None:
        normalized: list[SourceFile] = []
        for path, content in files:
            raw = content if isinstance(content, bytes) else content.encode("utf-8")
            normalized.append(SourceFile(path, raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")))
        normalized.sort(key=lambda item: item.path.encode("utf-8"))
        if len({item.path for item in normalized}) != len(normalized):
            raise SubstrateError("source bundle contains duplicate paths")
        self._files = tuple(normalized)

    @property
    def files(self) -> tuple[SourceFile, ...]:
        return self._files

    def view(self, file_id: StableId) -> "SourceView":
        if file_id < 0 or file_id >= len(self._files):
            raise InvalidIdError(f"unknown source file id {file_id}")
        return SourceView(self._files[file_id], file_id)

    def digest(self) -> str:
        digest = sha256()
        for item in self._files:
            path = item.path.encode("utf-8")
            digest.update(len(path).to_bytes(8, "big"))
            digest.update(path)
            digest.update(len(item.data).to_bytes(8, "big"))
            digest.update(item.data)
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SourceView:
    source: SourceFile
    file_id: StableId

    @property
    def length(self) -> int:
        return len(self.source.data)

    def cursor(self, offset: int = 0) -> SourceCursor:
        if offset < 0 or offset > self.length:
            raise IndexError("source cursor is outside the view")
        return SourceCursor(self.file_id, offset)

    def read(self, cursor: SourceCursor) -> int | None:
        if cursor.file_id != self.file_id:
            raise InvalidIdError("cursor belongs to another source view")
        if cursor.offset == self.length:
            return None
        return self.source.data[cursor.offset]

    def advance(self, cursor: SourceCursor, amount: int = 1) -> SourceCursor:
        if cursor.file_id != self.file_id:
            raise InvalidIdError("cursor belongs to another source view")
        next_offset = cursor.offset + amount
        if amount < 0 or next_offset > self.length:
            raise IndexError("source cursor would leave the view")
        return SourceCursor(self.file_id, next_offset)


class OutputSink:
    """Bounded deterministic byte sink with checkpoint/rollback transactions."""

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("sink capacity must be non-negative")
        self.capacity = capacity
        self._data = bytearray()

    def append(self, value: str | bytes) -> None:
        data = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        if len(self._data) + len(data) > self.capacity:
            raise CapacityError("output sink capacity exhausted")
        self._data.extend(data)

    def checkpoint(self) -> int:
        return len(self._data)

    def commit(self, checkpoint: int) -> None:
        self._validate_checkpoint(checkpoint)

    def rollback(self, checkpoint: int) -> None:
        self._validate_checkpoint(checkpoint)
        del self._data[checkpoint:]

    def _validate_checkpoint(self, checkpoint: int) -> None:
        if checkpoint < 0 or checkpoint > len(self._data):
            raise ValueError("invalid output checkpoint")

    def to_bytes(self) -> bytes:
        return bytes(self._data)

    def __len__(self) -> int:
        return len(self._data)


@dataclass(frozen=True, slots=True)
class Declaration:
    symbol_id: StableId
    scope_id: StableId
    kind: str
    type_id: StableId | None = None
    storage_id: StableId | None = None
    mutable: bool = False
    span: SourceSpan | None = None


@dataclass(slots=True)
class _Scope:
    parent: StableId | None
    declarations: dict[StableId, StableId] = field(default_factory=dict)
    function_id: StableId | None = None


@dataclass(frozen=True, slots=True)
class EnvironmentCheckpoint:
    scope_checkpoint: StableId
    declaration_checkpoint: StableId
    scope_stack: tuple[StableId, ...]
    change_checkpoint: int


class SemanticEnvironment:
    """Nearest-scope lookup with explicit shadowing and function isolation."""

    def __init__(self, symbols: SymbolInterner) -> None:
        self.symbols = symbols
        self.scopes: StableArena[_Scope] = StableArena()
        self.declarations: StableArena[Declaration] = StableArena()
        self._scope_stack: list[StableId] = [self.scopes.append(_Scope(None))]
        self._declaration_changes: list[tuple[StableId, StableId]] = []

    @property
    def current_scope(self) -> StableId:
        return self._scope_stack[-1]

    def enter_scope(self) -> StableId:
        return self._enter_scope(function_id=None)

    def enter_function(self, function_id: StableId) -> StableId:
        return self._enter_scope(function_id=function_id)

    def _enter_scope(self, function_id: StableId | None) -> StableId:
        scope_id = self.scopes.append(_Scope(self.current_scope, function_id=function_id))
        self._scope_stack.append(scope_id)
        return scope_id

    def leave_scope(self) -> StableId:
        if len(self._scope_stack) == 1:
            raise ScopeError("cannot leave the root scope")
        return self._scope_stack.pop()

    def declare(
        self,
        name: str | DynamicText,
        kind: str,
        type_id: StableId | None = None,
        *,
        storage_id: StableId | None = None,
        mutable: bool = False,
        span: SourceSpan | None = None,
    ) -> StableId:
        symbol_id = self.symbols.intern(name)
        scope = self.scopes.get(self.current_scope)
        if symbol_id in scope.declarations:
            raise ScopeError("duplicate declaration in one lexical scope")
        declaration_id = self.declarations.append(
            Declaration(
                symbol_id,
                self.current_scope,
                kind,
                type_id,
                storage_id,
                mutable,
                span,
            )
        )
        scope.declarations[symbol_id] = declaration_id
        self._declaration_changes.append((self.current_scope, symbol_id))
        return declaration_id

    def lookup(self, name: str | DynamicText) -> StableId | None:
        symbol_id = self.symbols.intern(name)
        scope_id: StableId | None = self.current_scope
        while scope_id is not None:
            scope = self.scopes.get(scope_id)
            declaration_id = scope.declarations.get(symbol_id)
            if declaration_id is not None:
                return declaration_id
            scope_id = scope.parent
        return None

    def checkpoint(self) -> EnvironmentCheckpoint:
        return EnvironmentCheckpoint(
            self.scopes.checkpoint(),
            self.declarations.checkpoint(),
            tuple(self._scope_stack),
            len(self._declaration_changes),
        )

    def rollback(self, checkpoint: EnvironmentCheckpoint) -> None:
        if checkpoint.change_checkpoint < 0 or checkpoint.change_checkpoint > len(
            self._declaration_changes
        ):
            raise ValueError("invalid environment checkpoint")
        for scope_id, symbol_id in reversed(
            self._declaration_changes[checkpoint.change_checkpoint :]
        ):
            scope = self.scopes.get(scope_id)
            scope.declarations.pop(symbol_id, None)
        del self._declaration_changes[checkpoint.change_checkpoint :]
        self.scopes.rollback(checkpoint.scope_checkpoint)
        self.declarations.rollback(checkpoint.declaration_checkpoint)
        self._scope_stack = list(checkpoint.scope_stack)


@dataclass(frozen=True, slots=True)
class ContextCheckpoint:
    arena_checkpoints: tuple[tuple[str, StableId], ...]
    symbol_checkpoint: tuple[StableId, int]
    environment_checkpoint: EnvironmentCheckpoint
    type_change_checkpoint: int
    function_change_checkpoint: int
    sink_checkpoint: int


@dataclass(slots=True)
class CompileResult:
    output: bytes
    errors: tuple[str, ...] = ()
    error_code: str | None = None
    ir_digest: str = ""
    source_span: SourceSpan | None = None

    @property
    def success(self) -> bool:
        return not self.errors

    @property
    def output_length(self) -> int:
        return len(self.output)


class CompilerContext:
    """Representable compiler-shaped state without compiler semantics."""

    def __init__(self, sources: SourceBundle, output_capacity: int = 1 << 20) -> None:
        self.sources = sources
        self.symbols = SymbolInterner()
        self.environment = SemanticEnvironment(self.symbols)
        self.sink = OutputSink(output_capacity)
        self.type_names = DynamicTextMap(16)
        self.function_names = DynamicTextMap(16)
        self._type_changes: list[tuple[DynamicText, StableId | None]] = []
        self._function_changes: list[tuple[DynamicText, StableId | None]] = []
        self.arenas: dict[str, StableArena[object]] = {
            name: StableArena()
            for name in (
                "File", "Symbol", "Scope", "Declaration", "Type", "Function",
                "Storage", "Node", "Block", "Value", "Instruction",
            )
        }

    def add(self, kind: str, value: object) -> StableId:
        try:
            return self.arenas[kind].append(value)
        except KeyError as error:
            raise SubstrateError(f"unknown compiler arena '{kind}'") from error

    def register_type(self, name: str | DynamicText, type_id: StableId) -> None:
        key = name if isinstance(name, DynamicText) else DynamicText.from_static(name)
        previous = self.lookup_type(key)
        self._type_changes.append((key.clone(), previous))
        self.type_names.put(key, type_id)

    def lookup_type(self, name: str | DynamicText) -> StableId | None:
        key = name if isinstance(name, DynamicText) else DynamicText.from_static(name)
        return self.type_names.get(key) if self.type_names.contains(key) == -1 else None

    def register_function(self, name: str | DynamicText, function_id: StableId) -> None:
        key = name if isinstance(name, DynamicText) else DynamicText.from_static(name)
        previous = self.lookup_function(key)
        self._function_changes.append((key.clone(), previous))
        self.function_names.put(key, function_id)

    def lookup_function(self, name: str | DynamicText) -> StableId | None:
        key = name if isinstance(name, DynamicText) else DynamicText.from_static(name)
        return (
            self.function_names.get(key)
            if self.function_names.contains(key) == -1
            else None
        )

    def checkpoint(self) -> ContextCheckpoint:
        return ContextCheckpoint(
            tuple((name, arena.checkpoint()) for name, arena in sorted(self.arenas.items())),
            self.symbols.checkpoint(),
            self.environment.checkpoint(),
            len(self._type_changes),
            len(self._function_changes),
            self.sink.checkpoint(),
        )

    def rollback(self, checkpoint: ContextCheckpoint) -> None:
        for name, arena_checkpoint in checkpoint.arena_checkpoints:
            self.arenas[name].rollback(arena_checkpoint)
        self.environment.rollback(checkpoint.environment_checkpoint)
        for key, previous in reversed(self._type_changes[checkpoint.type_change_checkpoint :]):
            if previous is None:
                self.type_names.remove(key)
            else:
                self.type_names.put(key, previous)
        del self._type_changes[checkpoint.type_change_checkpoint :]
        for key, previous in reversed(
            self._function_changes[checkpoint.function_change_checkpoint :]
        ):
            if previous is None:
                self.function_names.remove(key)
            else:
                self.function_names.put(key, previous)
        del self._function_changes[checkpoint.function_change_checkpoint :]
        self.symbols.rollback(checkpoint.symbol_checkpoint)
        self.sink.rollback(checkpoint.sink_checkpoint)

    def result(self) -> CompileResult:
        return CompileResult(self.sink.to_bytes())


__all__ = [
    "CapacityError",
    "CompileResult",
    "CompilerContext",
    "ContextCheckpoint",
    "Declaration",
    "EnvironmentCheckpoint",
    "InvalidIdError",
    "OutputSink",
    "SemanticEnvironment",
    "SourceBundle",
    "SourceCursor",
    "SourceFile",
    "SourceSpan",
    "SourceView",
    "StableArena",
    "StableId",
    "SubstrateError",
    "SymbolInterner",
]
