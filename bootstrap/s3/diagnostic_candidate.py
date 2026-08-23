"""Bounded S3-authored diagnostic recovery candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .differential import DifferentialHarness, DifferentialResult
from .diagnostics import DiagnosticCode, LexError, ParseError
from .lexer import SyntaxMode, tokenize
from .parser import parse
from .pipeline import run_source


M265_MODULUS = 301
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "frontend"
    / "diagnostic_candidate.s3"
).read_text(encoding="utf-8")


class DiagnosticCandidateError(ValueError):
    """Raised when a diagnostic code is outside the bounded recovery contract."""


@dataclass(frozen=True, slots=True)
class DiagnosticCandidateEvidence:
    code: int
    reference_fingerprint: int
    candidate_fingerprint: int
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match


_CODE_IDS = {
    DiagnosticCode.LEX_INVALID_CHARACTER: 1,
    DiagnosticCode.LEX_UNTERMINATED_STRING_LITERAL: 2,
    DiagnosticCode.LEX_INVALID_DEDENT: 3,
    DiagnosticCode.PARSE_SYNTAX: 4,
    DiagnosticCode.PARSE_OBSOLETE_BRACE: 5,
    DiagnosticCode.SEMANTIC_INVALID_PROGRAM: 6,
}


def _reference_recovery(code: int) -> int:
    categories = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 2}
    actions = {1: 1, 2: 2, 3: 3, 4: 4, 5: 4, 6: 5}
    try:
        return categories[code] * 32 + actions[code]
    except KeyError as error:
        raise DiagnosticCandidateError("unsupported M2.65 diagnostic code") from error


def reference_diagnostic_fingerprint(code: int) -> int:
    """Return the Python reference category/action contract."""

    if not isinstance(code, int) or isinstance(code, bool):
        raise TypeError("diagnostic code must be an integer")
    return _reference_recovery(code)


def candidate_diagnostic_fingerprint(code: int) -> int:
    """Run the S3 diagnostic/recovery classifier through the emulator."""

    if not isinstance(code, int) or isinstance(code, bool):
        raise TypeError("diagnostic code must be an integer")
    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return diagnostic_recovery_contract({code})\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise DiagnosticCandidateError("S3 diagnostic candidate execution failed") from error
    if result < 0:
        raise DiagnosticCandidateError("S3 diagnostic candidate rejected the code")
    return result


def diagnostic_code_for_source(source: str) -> int:
    """Extract a bounded reference diagnostic code from an invalid source."""

    try:
        tokenize(source, mode=SyntaxMode.V0_6)
        parse(source, mode=SyntaxMode.V0_6)
    except (LexError, ParseError) as error:
        try:
            return _CODE_IDS[error.diagnostic_code]
        except KeyError as lookup_error:
            raise DiagnosticCandidateError(
                f"unsupported source diagnostic {error.diagnostic_code}"
            ) from lookup_error
    raise DiagnosticCandidateError("source did not produce a diagnostic")


def run_diagnostic_differential(
    code: int,
    *,
    provenance: dict[str, object] | None = None,
) -> DiagnosticCandidateEvidence:
    """Compare a diagnostic code against Python recovery and S3 classification."""

    candidate = candidate_diagnostic_fingerprint(code)
    reference = reference_diagnostic_fingerprint(code)
    result = DifferentialHarness(max_bytes=4096).run(
        "m2.65-diagnostic-recovery-candidate",
        {"diagnostic_id": code},
        lambda value: {"fingerprint": reference_diagnostic_fingerprint(value["diagnostic_id"])},
        lambda value: {"fingerprint": candidate_diagnostic_fingerprint(value["diagnostic_id"])},
        provenance=provenance
        or {
            "component_id": "m2.65-diagnostic-recovery-candidate",
            "source": "selfhost/frontend/diagnostic_candidate.s3",
        },
    )
    return DiagnosticCandidateEvidence(code, reference, candidate, result)
