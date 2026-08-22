"""Backend-neutral source-to-native debug information foundation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class DebugInfoError(ValueError):
    """Raised for malformed or ambiguous debug mappings."""


@dataclass(frozen=True, slots=True)
class DebugRange:
    source_file: str
    line: int
    column: int
    ir_start: int
    ir_end: int
    native_start: int | None = None
    native_end: int | None = None

    def __post_init__(self) -> None:
        if not self.source_file or self.line < 1 or self.column < 1:
            raise DebugInfoError("debug source location is invalid")
        if self.ir_start < 0 or self.ir_end <= self.ir_start:
            raise DebugInfoError("debug IR range is invalid")
        if (self.native_start is None) != (self.native_end is None):
            raise DebugInfoError("native range must be complete")
        if self.native_start is not None and (self.native_start < 0 or self.native_end <= self.native_start):
            raise DebugInfoError("debug native range is invalid")

    @property
    def payload(self) -> dict[str, object]:
        return {
            "source_file": self.source_file,
            "line": self.line,
            "column": self.column,
            "ir_start": self.ir_start,
            "ir_end": self.ir_end,
            "native_start": self.native_start,
            "native_end": self.native_end,
        }


@dataclass(frozen=True, slots=True)
class DebugSymbol:
    name: str
    function: str
    source_file: str
    line: int
    column: int
    scope: str = "function"

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (self.name, self.function, self.source_file, self.scope)):
            raise DebugInfoError("debug symbol fields must be non-empty")
        if self.line < 1 or self.column < 1:
            raise DebugInfoError("debug symbol source location is invalid")

    @property
    def payload(self) -> dict[str, object]:
        return {"name": self.name, "function": self.function, "source_file": self.source_file, "line": self.line, "column": self.column, "scope": self.scope}


@dataclass(frozen=True, slots=True)
class DebugInfo:
    ranges: tuple[DebugRange, ...] = ()
    symbols: tuple[DebugSymbol, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise DebugInfoError("debug enabled flag must be boolean")
        if tuple(sorted(self.ranges, key=lambda item: (item.source_file, item.line, item.column, item.ir_start))) != self.ranges:
            raise DebugInfoError("debug ranges must be in canonical order")
        if tuple(sorted(self.symbols, key=lambda item: (item.source_file, item.line, item.column, item.name))) != self.symbols:
            raise DebugInfoError("debug symbols must be in canonical order")

    @property
    def payload(self) -> dict[str, object]:
        return {"format": "s3.debug-info.v1", "enabled": self.enabled, "ranges": [item.payload for item in self.ranges], "symbols": [item.payload for item in self.symbols]}

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @property
    def text(self) -> str:
        return json.dumps(self.payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
