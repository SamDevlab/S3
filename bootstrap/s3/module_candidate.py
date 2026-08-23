"""Bounded S3-authored module/import candidate with differential evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .differential import DifferentialHarness, DifferentialResult
from .lexer import SyntaxMode, TokenKind, tokenize
from .pipeline import run_source


M264_MAX_TOKENS = 16
M264_MODULUS = 301
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2] / "selfhost" / "frontend" / "module_candidate.s3"
).read_text(encoding="utf-8")


class ModuleCandidateError(ValueError):
    """Raised when a bounded module/import declaration is not recognized."""


@dataclass(frozen=True, slots=True)
class ModuleCandidateEvidence:
    source: str
    reference_fingerprint: int
    candidate_fingerprint: int
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match


def _tokens(source: str):
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    if len(tokens) > M264_MAX_TOKENS:
        raise ModuleCandidateError("source exceeds the M2.64 token bound")
    return tokens


def _symbol_hash(text: str) -> int:
    return sum(ord(char) for char in text) % M264_MODULUS


def _reference_values(source: str) -> tuple[int, list[int], list[int]]:
    tokens = _tokens(source)
    kinds = [token.kind.value for token in tokens]
    symbols = [_symbol_hash(token.text) for token in tokens]
    if kinds == [TokenKind.MODULE.value, TokenKind.IDENTIFIER.value, TokenKind.NEWLINE.value, TokenKind.EOF.value]:
        checksum = (101 + symbols[1]) % M264_MODULUS
        return checksum, kinds, symbols
    if kinds == [
        TokenKind.FROM.value,
        TokenKind.IDENTIFIER.value,
        TokenKind.IMPORT.value,
        TokenKind.IDENTIFIER.value,
        TokenKind.NEWLINE.value,
        TokenKind.EOF.value,
    ]:
        checksum = (102 + symbols[1]) % M264_MODULUS
        checksum = (checksum * 32 + 29 + symbols[3]) % M264_MODULUS
        return checksum, kinds, symbols
    raise ModuleCandidateError("unsupported M2.64 module/import declaration")


def reference_module_fingerprint(source: str) -> int:
    """Return the reference canonical declaration fingerprint."""

    checksum, _, _ = _reference_values(source)
    return checksum


def candidate_module_fingerprint(source: str) -> int:
    """Run the S3 declaration candidate through the hosted emulator."""

    _, kinds, symbols = _reference_values(source)
    kinds_text = [str(kind) for kind in kinds]
    symbols_text = [str(symbol) for symbol in symbols]
    kinds_text.extend(["0"] * (M264_MAX_TOKENS - len(kinds_text)))
    symbols_text.extend(["0"] * (M264_MAX_TOKENS - len(symbols_text)))
    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    kinds: tryte[{M264_MAX_TOKENS}] = [{', '.join(kinds_text)}]\n"
        + f"    symbols: tryte[{M264_MAX_TOKENS}] = [{', '.join(symbols_text)}]\n"
        + f"    return module_import_fingerprint(kinds, symbols, {len(kinds)})\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise ModuleCandidateError("S3 module/import candidate execution failed") from error
    if result < 0:
        raise ModuleCandidateError("S3 module/import candidate rejected the declaration")
    return result


def run_module_differential(
    source: str,
    *,
    provenance: dict[str, object] | None = None,
) -> ModuleCandidateEvidence:
    """Compare a declaration against the Python reference and S3 candidate."""

    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if not source:
        raise ModuleCandidateError("source must be non-empty")
    candidate = candidate_module_fingerprint(source)
    reference = reference_module_fingerprint(source)
    result = DifferentialHarness(max_bytes=4096).run(
        "m2.64-module-import-candidate",
        {"source": source, "mode": "V0_6"},
        lambda value: {"fingerprint": reference_module_fingerprint(value["source"])},
        lambda value: {"fingerprint": candidate_module_fingerprint(value["source"])},
        provenance=provenance
        or {
            "component_id": "m2.64-module-import-candidate",
            "source": "selfhost/frontend/module_candidate.s3",
        },
    )
    return ModuleCandidateEvidence(source, reference, candidate, result)
