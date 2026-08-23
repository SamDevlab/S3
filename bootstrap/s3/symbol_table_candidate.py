"""M2.71 bounded self-hosted symbol table candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dynamic import DynamicMap
from .lexer import SyntaxMode
from .pipeline import run_source
from .ternary import validate_tryte


M271_MAX_SYMBOLS = 8
M271_MIN_KIND = 1
M271_MAX_KIND = 4
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "semantic"
    / "symbol_table_candidate.s3"
).read_text(encoding="utf-8")


class SymbolTableCandidateError(ValueError):
    """Raised when an M2.71 symbol table input is outside the bounded contract."""


@dataclass(frozen=True, slots=True)
class SymbolTableCandidateEvidence:
    entries: tuple[tuple[int, int], ...]
    query: int
    reference_result: int
    candidate_result: int

    @property
    def match(self) -> bool:
        return self.reference_result == self.candidate_result


def _bounded_entries(entries: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    if not isinstance(entries, (list, tuple)):
        raise TypeError("entries must be a list or tuple")
    if len(entries) > M271_MAX_SYMBOLS:
        raise SymbolTableCandidateError("symbol table exceeds the M2.71 symbol bound")
    normalized: list[tuple[int, int]] = []
    for entry in entries:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("symbol table entries must be (symbol_id, kind) tuples")
        symbol_id, kind = entry
        if isinstance(symbol_id, bool) or not isinstance(symbol_id, int):
            raise TypeError("symbol id must be an integer")
        if isinstance(kind, bool) or not isinstance(kind, int):
            raise TypeError("symbol kind must be an integer")
        validate_tryte(symbol_id)
        validate_tryte(kind)
        normalized.append((symbol_id, kind))
    return tuple(normalized)


def _validate_query(query: int) -> int:
    if isinstance(query, bool) or not isinstance(query, int):
        raise TypeError("symbol query must be an integer")
    return validate_tryte(query)


def _encode_slot(index: int, kind: int) -> int:
    return (index + 1) * 8 + kind


def reference_symbol_lookup(
    entries: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    query: int,
) -> int:
    """Return the deterministic Python reference lookup result."""

    normalized = _bounded_entries(entries)
    query = _validate_query(query)
    table = DynamicMap(M271_MAX_SYMBOLS)
    for index, (symbol_id, kind) in enumerate(normalized):
        if not M271_MIN_KIND <= kind <= M271_MAX_KIND:
            raise SymbolTableCandidateError("symbol kind is outside the M2.71 kind range")
        if table.contains(symbol_id):
            raise SymbolTableCandidateError("duplicate symbol id in M2.71 symbol table")
        table.put(symbol_id, _encode_slot(index, kind))
    if not table.contains(query):
        return 0
    return table.get(query)


def candidate_symbol_lookup(
    entries: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    query: int,
) -> int:
    """Execute the S3-authored symbol table candidate for one lookup."""

    normalized = _bounded_entries(entries)
    query = _validate_query(query)
    symbol_ids = [str(symbol_id) for symbol_id, _kind in normalized]
    kinds = [str(kind) for _symbol_id, kind in normalized]
    symbol_ids.extend(["0"] * (M271_MAX_SYMBOLS - len(symbol_ids)))
    kinds.extend(["0"] * (M271_MAX_SYMBOLS - len(kinds)))
    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    symbol_ids: tryte[{M271_MAX_SYMBOLS}] = [{', '.join(symbol_ids)}]\n"
        + f"    kinds: tryte[{M271_MAX_SYMBOLS}] = [{', '.join(kinds)}]\n"
        + f"    return symbol_table_lookup(symbol_ids, kinds, {len(normalized)}, {query})\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise SymbolTableCandidateError("S3 symbol table candidate execution failed") from error
    if result < 0:
        raise SymbolTableCandidateError("S3 symbol table candidate rejected the input")
    return result


def run_symbol_table_differential(
    entries: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    query: int,
) -> SymbolTableCandidateEvidence:
    """Compare one exact symbol lookup between Python and the S3 candidate."""

    normalized = _bounded_entries(entries)
    query = _validate_query(query)
    reference = reference_symbol_lookup(normalized, query)
    candidate = candidate_symbol_lookup(normalized, query)
    return SymbolTableCandidateEvidence(normalized, query, reference, candidate)
