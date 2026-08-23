"""Canonical bounded source identities, line mapping, and source spans."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass


class SourceManagerError(RuntimeError):
    """Base class for source identity and span failures."""


class SourceCapacityError(SourceManagerError):
    """Raised when the configured source manager capacity is exhausted."""


class SourceBoundsError(SourceManagerError):
    """Raised when an offset or span is outside its source file."""


SourceId = int


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """An immutable half-open span owned by exactly one source file."""

    source_id: SourceId
    start: int
    end: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.source_id, bool)
            or not isinstance(self.source_id, int)
            or self.source_id < 0
        ):
            raise TypeError("source_id must be a non-negative integer")
        if (
            isinstance(self.start, bool)
            or not isinstance(self.start, int)
            or isinstance(self.end, bool)
            or not isinstance(self.end, int)
        ):
            raise TypeError("span offsets must be integers")
        if self.start < 0 or self.start > self.end:
            raise SourceBoundsError("source span must be ordered and non-negative")


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A source offset with one-based line and column coordinates."""

    source_id: SourceId
    offset: int
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class SourceFile:
    """Immutable source metadata with precomputed line starts."""

    source_id: SourceId
    name: str
    text: str
    line_starts: tuple[int, ...]


class SourceManager:
    """A bounded multi-file source table with canonical offset operations."""

    def __init__(self, *, max_files: int = 256, max_total_bytes: int = 16_777_216) -> None:
        for name, value in (
            ("max_files", max_files),
            ("max_total_bytes", max_total_bytes),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        self.max_files = max_files
        self.max_total_bytes = max_total_bytes
        self._files: dict[SourceId, SourceFile] = {}
        self._ids_by_name: dict[str, SourceId] = {}
        self._total_bytes = 0

    @property
    def file_count(self) -> int:
        return len(self._files)

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    def add(self, name: str, text: str) -> SourceId:
        if not isinstance(name, str) or not name:
            raise ValueError("source name must be a non-empty string")
        if not isinstance(text, str):
            raise TypeError("source text must be a string")
        if name in self._ids_by_name:
            raise SourceManagerError(f"source name already registered: {name}")
        if self.file_count >= self.max_files:
            raise SourceCapacityError("source file capacity reached")
        requested = len(text)
        if self._total_bytes + requested > self.max_total_bytes:
            raise SourceCapacityError("source byte capacity reached")
        source_id = self.file_count
        source = SourceFile(source_id, name, text, _line_starts(text))
        self._files[source_id] = source
        self._ids_by_name[name] = source_id
        self._total_bytes += requested
        return source_id

    def file(self, source_id: SourceId) -> SourceFile:
        self._require_source(source_id)
        return self._files[source_id]

    def id_for_name(self, name: str) -> SourceId:
        try:
            return self._ids_by_name[name]
        except KeyError as exc:
            raise SourceManagerError(f"unknown source name: {name}") from exc

    def span(self, source_id: SourceId, start: int, end: int) -> SourceSpan:
        source = self.file(source_id)
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or start < 0
            or start > end
            or end > len(source.text)
        ):
            raise SourceBoundsError("source span is outside the source file")
        return SourceSpan(source_id, start, end)

    def location(self, source_id: SourceId, offset: int) -> SourceLocation:
        source = self.file(source_id)
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("source offset must be an integer")
        if not 0 <= offset <= len(source.text):
            raise SourceBoundsError("source offset is outside the source file")
        line_index = bisect_right(source.line_starts, offset) - 1
        line_start = source.line_starts[line_index]
        return SourceLocation(source_id, offset, line_index + 1, offset - line_start + 1)

    def text(self, span: SourceSpan) -> str:
        source = self.file(span.source_id)
        self.span(span.source_id, span.start, span.end)
        return source.text[span.start : span.end]

    def line_text(self, source_id: SourceId, line: int) -> str:
        source = self.file(source_id)
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise SourceBoundsError("source line must be positive")
        if line > len(source.line_starts):
            raise SourceBoundsError("source line is outside the source file")
        start = source.line_starts[line - 1]
        end = (
            source.line_starts[line] - 1
            if line < len(source.line_starts)
            else len(source.text)
        )
        if end > start and source.text[end - 1] == "\r":
            end -= 1
        return source.text[start:end]

    def _require_source(self, source_id: SourceId) -> None:
        if isinstance(source_id, bool) or not isinstance(source_id, int):
            raise SourceManagerError("source_id must be an integer")
        if source_id not in self._files:
            raise SourceManagerError(f"unknown source id: {source_id}")


def _line_starts(text: str) -> tuple[int, ...]:
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    return tuple(starts)
