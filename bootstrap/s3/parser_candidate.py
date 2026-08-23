"""Bounded S3-authored parser candidate with Python differential evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .differential import DifferentialHarness, DifferentialResult
from .lexer import SyntaxMode, tokenize
from .parser import parse
from .pipeline import run_source


M262_MAX_TOKENS = 64
M262_TOKEN_HASH_BASE = 32
M262_MODULUS = 301
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2] / "selfhost" / "frontend" / "parser_candidate.s3"
).read_text(encoding="utf-8")


class ParserCandidateError(ValueError):
    """Raised when the bounded S3 parser candidate cannot certify input."""


@dataclass(frozen=True, slots=True)
class ParserCandidateEvidence:
    source: str
    reference_fingerprint: int
    candidate_fingerprint: int
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match


def _tokens(source: str):
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    if len(tokens) > M262_MAX_TOKENS:
        raise ParserCandidateError("source exceeds the M2.62 token bound")
    return tokens


def reference_parser_fingerprint(source: str) -> int:
    """Parse with Python and fingerprint the exact bounded token stream."""

    parse(source, mode=SyntaxMode.V0_6)
    checksum = 0
    for token in _tokens(source):
        checksum = (
            checksum * M262_TOKEN_HASH_BASE + token.kind.value + len(token.text)
        ) % M262_MODULUS
    return checksum


def candidate_parser_fingerprint(source: str) -> int:
    """Run the S3 parser candidate through the hosted compiler/emulator."""

    tokens = _tokens(source)
    kinds = [str(token.kind.value) for token in tokens]
    widths = [str(len(token.text)) for token in tokens]
    kinds.extend(["0"] * (M262_MAX_TOKENS - len(kinds)))
    widths.extend(["0"] * (M262_MAX_TOKENS - len(widths)))
    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    kinds: tryte[{M262_MAX_TOKENS}] = [{', '.join(kinds)}]\n"
        + f"    widths: tryte[{M262_MAX_TOKENS}] = [{', '.join(widths)}]\n"
        + f"    return parser_fingerprint(kinds, widths, {len(tokens)})\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise ParserCandidateError("S3 parser candidate execution failed") from error
    if result < 0:
        raise ParserCandidateError("S3 parser candidate rejected the bounded grammar")
    return result


def run_parser_differential(
    source: str,
    *,
    provenance: dict[str, object] | None = None,
) -> ParserCandidateEvidence:
    """Compare the exact source against Python parsing and the S3 candidate."""

    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if not source:
        raise ParserCandidateError("source must be non-empty")
    candidate = candidate_parser_fingerprint(source)
    reference = reference_parser_fingerprint(source)
    result = DifferentialHarness(max_bytes=4096).run(
        "m2.62-parser-candidate",
        {"source": source, "mode": "V0_6"},
        lambda value: {"fingerprint": reference_parser_fingerprint(value["source"])},
        lambda value: {"fingerprint": candidate_parser_fingerprint(value["source"])},
        provenance=provenance
        or {
            "component_id": "m2.62-parser-candidate",
            "source": "selfhost/frontend/parser_candidate.s3",
        },
    )
    return ParserCandidateEvidence(source, reference, candidate, result)
