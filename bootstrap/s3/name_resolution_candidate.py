"""M2.72 bounded S3-authored lexical name-resolution candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lexer import SyntaxMode
from .pipeline import run_source
from .ternary import validate_tryte


M272_MAX_SYMBOLS = 8
M272_MAX_SCOPES = 8
M272_MIN_KIND = 1
M272_MAX_KIND = 4
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "semantic"
    / "name_resolution_candidate.s3"
).read_text(encoding="utf-8")


class NameResolutionCandidateError(ValueError):
    """Raised when an M2.72 input is outside the bounded resolution contract."""


@dataclass(frozen=True, slots=True)
class NameResolutionEvidence:
    entries: tuple[tuple[int, int, int], ...]
    scope_parents: tuple[int, ...]
    query_symbol: int
    query_scope: int
    reference_result: int
    candidate_result: int

    @property
    def match(self) -> bool:
        return self.reference_result == self.candidate_result


def _validate_kind(kind: int) -> int:
    if isinstance(kind, bool) or not isinstance(kind, int):
        raise TypeError("symbol kind must be an integer")
    validate_tryte(kind)
    if not M272_MIN_KIND <= kind <= M272_MAX_KIND:
        raise NameResolutionCandidateError("symbol kind is outside the M2.72 kind range")
    return kind


def _validate_scope_tree(scope_parents: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(scope_parents, (list, tuple)):
        raise TypeError("scope_parents must be a list or tuple")
    if not 1 <= len(scope_parents) <= M272_MAX_SCOPES:
        raise NameResolutionCandidateError("scope tree exceeds the M2.72 scope bound")
    normalized: list[int] = []
    for parent in scope_parents:
        if isinstance(parent, bool) or not isinstance(parent, int):
            raise TypeError("scope parent must be an integer")
        normalized.append(validate_tryte(parent))
    if normalized[0] != -1:
        raise NameResolutionCandidateError("root scope parent must be -1")
    for scope_id, parent in enumerate(normalized[1:], start=1):
        if parent < 0 or parent >= scope_id:
            raise NameResolutionCandidateError("scope parent must reference an earlier scope")
    return tuple(normalized)


def _validate_entries(
    entries: list[tuple[int, int, int]] | tuple[tuple[int, int, int], ...],
    scope_count: int,
) -> tuple[tuple[int, int, int], ...]:
    if not isinstance(entries, (list, tuple)):
        raise TypeError("entries must be a list or tuple")
    if len(entries) > M272_MAX_SYMBOLS:
        raise NameResolutionCandidateError("symbol table exceeds the M2.72 symbol bound")
    normalized: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    for entry in entries:
        if not isinstance(entry, tuple) or len(entry) != 3:
            raise TypeError("entries must be (symbol_id, kind, scope_id) tuples")
        symbol_id, kind, scope_id = entry
        if isinstance(symbol_id, bool) or not isinstance(symbol_id, int):
            raise TypeError("symbol id must be an integer")
        if isinstance(scope_id, bool) or not isinstance(scope_id, int):
            raise TypeError("scope id must be an integer")
        symbol_id = validate_tryte(symbol_id)
        kind = _validate_kind(kind)
        scope_id = validate_tryte(scope_id)
        if not 0 <= scope_id < scope_count:
            raise NameResolutionCandidateError("declaration scope is outside the scope tree")
        duplicate_key = (symbol_id, scope_id)
        if duplicate_key in seen:
            raise NameResolutionCandidateError("duplicate symbol in one lexical scope")
        seen.add(duplicate_key)
        normalized.append((symbol_id, kind, scope_id))
    return tuple(normalized)


def _validate_query(query_symbol: int, query_scope: int, scope_count: int) -> tuple[int, int]:
    if isinstance(query_symbol, bool) or not isinstance(query_symbol, int):
        raise TypeError("query symbol must be an integer")
    if isinstance(query_scope, bool) or not isinstance(query_scope, int):
        raise TypeError("query scope must be an integer")
    query_symbol = validate_tryte(query_symbol)
    query_scope = validate_tryte(query_scope)
    if not 0 <= query_scope < scope_count:
        raise NameResolutionCandidateError("query scope is outside the scope tree")
    return query_symbol, query_scope


def _encode_slot(index: int, kind: int) -> int:
    return (index + 1) * 8 + kind


def reference_name_resolution(
    entries: list[tuple[int, int, int]] | tuple[tuple[int, int, int], ...],
    scope_parents: list[int] | tuple[int, ...],
    query_symbol: int,
    query_scope: int,
) -> int:
    """Resolve the nearest visible declaration using the Python reference."""

    parents = _validate_scope_tree(scope_parents)
    normalized = _validate_entries(entries, len(parents))
    query_symbol, query_scope = _validate_query(query_symbol, query_scope, len(parents))
    current = query_scope
    while True:
        for index, (symbol_id, kind, scope_id) in enumerate(normalized):
            if scope_id == current and symbol_id == query_symbol:
                return _encode_slot(index, kind)
        if current == 0:
            return 0
        current = parents[current]


def candidate_name_resolution(
    entries: list[tuple[int, int, int]] | tuple[tuple[int, int, int], ...],
    scope_parents: list[int] | tuple[int, ...],
    query_symbol: int,
    query_scope: int,
) -> int:
    """Execute the S3-authored bounded lexical resolver."""

    parents = _validate_scope_tree(scope_parents)
    normalized = _validate_entries(entries, len(parents))
    query_symbol, query_scope = _validate_query(query_symbol, query_scope, len(parents))

    symbol_ids = [str(symbol_id) for symbol_id, _kind, _scope in normalized]
    kinds = [str(kind) for _symbol_id, kind, _scope in normalized]
    declaration_scopes = [str(scope) for _symbol_id, _kind, scope in normalized]
    parent_values = [str(parent) for parent in parents]
    symbol_ids.extend(["0"] * (M272_MAX_SYMBOLS - len(symbol_ids)))
    kinds.extend(["0"] * (M272_MAX_SYMBOLS - len(kinds)))
    declaration_scopes.extend(["0"] * (M272_MAX_SYMBOLS - len(declaration_scopes)))
    parent_values.extend(["0"] * (M272_MAX_SCOPES - len(parent_values)))

    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    symbol_ids: tryte[8] = [{', '.join(symbol_ids)}]\n"
        + f"    kinds: tryte[8] = [{', '.join(kinds)}]\n"
        + f"    declaration_scopes: tryte[8] = [{', '.join(declaration_scopes)}]\n"
        + f"    scope_parents: tryte[8] = [{', '.join(parent_values)}]\n"
        + "    return resolve_visible_symbol(\n"
        + "        symbol_ids, kinds, declaration_scopes, scope_parents,\n"
        + f"        {len(normalized)}, {len(parents)}, {query_symbol}, {query_scope}\n"
        + "    )\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise NameResolutionCandidateError("S3 name-resolution candidate execution failed") from error
    if result < 0:
        raise NameResolutionCandidateError("S3 name-resolution candidate rejected the input")
    return result


def run_name_resolution_differential(
    entries: list[tuple[int, int, int]] | tuple[tuple[int, int, int], ...],
    scope_parents: list[int] | tuple[int, ...],
    query_symbol: int,
    query_scope: int,
) -> NameResolutionEvidence:
    """Compare exact nearest-visible-declaration results."""

    parents = _validate_scope_tree(scope_parents)
    normalized = _validate_entries(entries, len(parents))
    query_symbol, query_scope = _validate_query(query_symbol, query_scope, len(parents))
    reference = reference_name_resolution(normalized, parents, query_symbol, query_scope)
    candidate = candidate_name_resolution(normalized, parents, query_symbol, query_scope)
    return NameResolutionEvidence(
        normalized,
        parents,
        query_symbol,
        query_scope,
        reference,
        candidate,
    )
