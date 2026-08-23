"""Bounded S3-authored lexer candidate with Python differential evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .differential import DifferentialHarness, DifferentialResult
from .lexer import SyntaxMode, tokenize
from .pipeline import run_source


M261_MAX_SOURCE_UNITS = 96
M261_MODULUS = 301
M261_TOKEN_HASH_BASE = 32
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2] / "selfhost" / "frontend" / "lexer_candidate.s3"
).read_text(encoding="utf-8")


class LexerCandidateError(ValueError):
    """Raised when the bounded S3 lexer candidate cannot certify an input."""


@dataclass(frozen=True, slots=True)
class LexerCandidateEvidence:
    source: str
    reference_fingerprint: int
    candidate_fingerprint: int
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match


def reference_fingerprint(source: str) -> int:
    """Return the Python reference token fingerprint for the bounded subset."""

    checksum = 0
    for token in tokenize(source, mode=SyntaxMode.V0_5):
        checksum = (checksum * M261_TOKEN_HASH_BASE + token.kind.value + len(token.text)) % M261_MODULUS
    return checksum


def candidate_fingerprint(source: str) -> int:
    """Run the S3-authored candidate through the hosted compiler/emulator."""

    units = [str(ord(char)) for char in source]
    if len(units) > M261_MAX_SOURCE_UNITS:
        raise LexerCandidateError("source exceeds the M2.61 bounded candidate")
    if any(ord(char) > 127 for char in source):
        raise LexerCandidateError("M2.61 candidate accepts ASCII source only")
    units.extend(["0"] * (M261_MAX_SOURCE_UNITS - len(units)))
    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    input: tryte[{M261_MAX_SOURCE_UNITS}] = [{', '.join(units)}]\n"
        + f"    return lexer_fingerprint(input, {len(source)})\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise LexerCandidateError("S3 lexer candidate execution failed") from error
    if result < 0:
        raise LexerCandidateError("S3 lexer candidate rejected the bounded input")
    return result


def run_lexer_differential(
    source: str,
    *,
    provenance: dict[str, object] | None = None,
) -> LexerCandidateEvidence:
    """Compare the exact source against the Python reference and S3 candidate."""

    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if not source:
        raise LexerCandidateError("source must be non-empty")
    candidate = candidate_fingerprint(source)
    reference = reference_fingerprint(source)
    result = DifferentialHarness(max_bytes=4096).run(
        "m2.61-lexer-candidate",
        {"source": source, "mode": "V0_5"},
        lambda value: {"fingerprint": reference_fingerprint(value["source"])},
        lambda value: {"fingerprint": candidate_fingerprint(value["source"])},
        provenance=provenance
        or {"component_id": "m2.61-lexer-candidate", "source": "selfhost/frontend/lexer_candidate.s3"},
    )
    return LexerCandidateEvidence(source, reference, candidate, result)
